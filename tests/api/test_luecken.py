"""Lücken in Sammlungen (BF-75): Reihen je Sprache mit eigener Zählung, Zahl der Bände aus der Quelle gegen die eigene Angabe,
Ausblenden und Zurückholen, Platzhalter aus, Suchadresse mit Sonderzeichen, die Zeile der Sammlungsvorschläge, Schonung der
Quellen (eine Abfrage je Sammlung und Sprache, Vorrat, keine Wiederholung, Pause), Sichtbarkeit für Kinder und Hochladen in eine
Lücke mit Hinweis. Die Kataloge sind Attrappen (tests/luecken_kataloge.py); alle Reihen, Titel und Namen sind erfunden."""

from __future__ import annotations

import asyncio
import io
import zipfile

import isbnlib
import pytest

from backend.app.core.config import settings
from backend.app.familie.stufen import stufenbuch
from backend.app.luecken import nachschlagen as nachschlagen_modul
from backend.app.luecken.nachschlagen import nachschlagen
from backend.app.quellen import abruf as quellen_abruf
from backend.app.services import vorschlaege
from tests.api.conftest import sammlung_erstellen, verwaltung
from tests.api.familie_hilfen import familie_anlegen
from tests.api.test_annahme_api import warten
from tests.api.test_sammlungen_liste import buch
from tests.api.test_vorschau import bis_bestaetigen, pdf, zeile
from tests.luecken_kataloge import antwort_mit, satz
from tests.quellen_netz import abruf_mit, antwort, feld

DNB, K10 = "services.dnb.de", "sru.k10plus.de"
REIHE, AUTORIN, REIHE_EN = "Leuchtfeuerkai", "Henrike Sandvoss", "Lighthouse Quay"
TITEL_DE = {1: "Nebel am Kai", 2: "Ebbe", 3: "Der Lotse", 4: "Der stille Kai", 5: "Möwen & Nebel/Teil #2+", 6: "Sturmnacht", 7: "Bernsteinwind"}
TITEL_EN = {1: "Fog on the Quay", 2: "Low Tide", 3: "The Pilot", 4: "Gull Call"}


def isbn(vorn: str, n: int) -> str:
    kern = f"{vorn}{n:03d}"
    return kern + isbnlib.check_digit13(kern)


def deutsch() -> bytes:
    """Die Nationalbibliothek kennt 1 bis 7 einzeln (Band 2 in zwei Ausgaben) und 8 und 9 als Doppelband, dazu eine Verlagsreihe."""
    return antwort_mit(*(satz(t, REIHE, f"Bd. {n}", isbn=isbn("978399999", n), jahr=2015 + n) for n, t in TITEL_DE.items()),
                       satz("Ebbe", REIHE, "2", jahr=2012),
                       satz("Doppelband am Deich", REIHE, "8-9", jahr=2024),
                       satz("Krabbenkutter", "Taschenbuch", "22953"))


def englisch() -> bytes:
    """Der Verbundkatalog kennt 1 bis 4 auf Englisch und eine deutsche Ausgabe, die nicht zählt."""
    return antwort_mit(*(satz(t, REIHE_EN, str(n), isbn=isbn("978199999", n), sprache="en") for n, t in TITEL_EN.items()),
                       satz("Ein deutscher Band zwölf", REIHE_EN, "12", sprache="de"))


@pytest.fixture
def ohne_abstand(monkeypatch):
    monkeypatch.setattr(settings, "luecken_abstand_s", 0)


async def reihe_anlegen(test_db, name: str = REIHE) -> int:
    """Deutsch 1, 2, 3, 3a, 5, 7 und ein Sonderband, ein Buch ohne Sprache als Band 6 (zählt zur Hauptsprache), Englisch 1 und 3
    unter dem englischen Namen der Reihe."""
    s = await sammlung_erstellen(test_db, name=name)
    for band in ("1", "2", "3", "3a", "5", "7", "Sonderband"):
        await buch(test_db, f"{name} {band}", autor=AUTORIN, sammlung=s, band=band, language="de")
    await buch(test_db, f"{name} ohne Sprache", autor=AUTORIN, sammlung=s, band="6", language="")
    for band in ("1", "3"):
        await buch(test_db, f"{REIHE_EN}, Book {band}", autor=AUTORIN, sammlung=s, band=band, language="eng")
    return s


async def luecken(client, s: int, kopf: dict | None = None) -> dict:
    r = await client.get(f"/api/collections/{s}/luecken", headers=kopf or {})
    assert r.status_code == 200, r.text
    return r.json()


def reihen(a: dict) -> dict[str, dict]:
    return {r["sprache"]: r for r in a["reihen"]}


async def nachgeschlagen(client, test_db, netz) -> int:
    s = await reihe_anlegen(test_db)
    netz.setze(DNB, antwort(deutsch()))
    netz.setze(K10, antwort(englisch()))
    assert await nachschlagen.runde() == 2
    return s


# -- Lücken je Sprache --------------------------------------------------------------------------------------------------------

async def test_reihen_je_sprache_mit_zahl_aus_der_quelle(client, test_db, netz, ohne_abstand):
    s = await nachgeschlagen(client, test_db, netz)
    assert netz.zahl(DNB) == 1 and netz.zahl(K10) == 1
    fragen = {a.adresse.split("/")[2]: feld(a, "query") for a in netz.anfragen}
    assert fragen == {DNB: f'TIT="{REIHE}" and PER="sandvoss" and MAT=books and SPR=ger',
                      K10: f'pica.tit="{REIHE_EN}" and pica.per="sandvoss"'}                # je Sprache der Name ihrer Titel
    assert {feld(a, "maximumRecords") for a in netz.anfragen} == {"100"}
    a = await luecken(client, s)
    assert (a["name"], a["autor"], a["an"]) == (REIHE, AUTORIN, True)
    de = a["reihen"][0]                                                    # die Hauptsprache zuerst
    assert (de["sprache"], de["name"], de["gesamt"], de["herkunft"], de["quelle_gesamt"]) == ("de", "Deutsch", 9, "quelle", 9)
    assert (de["buecher"], de["belegt"], de["fehlen"], de["zeile"]) == (8, 6, [4, 8, 9], "es fehlen 4, 8 und 9")
    assert [(e["art"], e["band"]) for e in de["eintraege"]] == [
        ("buch", "1"), ("buch", "2"), ("buch", "3"), ("buch", "3a"), ("luecke", "4"), ("buch", "5"), ("buch", "6"), ("buch", "7"),
        ("luecke", "8"), ("luecke", "9"), ("buch", "Sonderband")]
    assert de["eintraege"][3]["zwischen"] and de["eintraege"][0]["buch"]["title"] == f"{REIHE} 1"
    en = a["reihen"][1]
    assert (de["nachschlagen"]["stand"], de["nachschlagen"]["quelle_name"], de["nachschlagen"]["reihe"]) == ("fertig", "Verzeichnis 3", REIHE)
    assert en["nachschlagen"]["reihe"] == REIHE_EN
    vier, acht = de["eintraege"][4]["luecke"], de["eintraege"][8]["luecke"]
    assert (vier["titel"], vier["autor"], vier["isbn"], vier["jahr"], vier["quelle"]) == ("Der stille Kai", AUTORIN, "978-3-99999-004-0", 2019, "dnb")
    assert vier["kopieren"] == f"Der stille Kai, {AUTORIN}, {REIHE} Band 4, ISBN 978-3-99999-004-0"
    assert vier["suchadresse"] is None                                     # ohne Vorlage nur Kopieren
    assert (acht["titel"], acht["kopieren"]) == ("", f"{REIHE} Band 8, {AUTORIN}")     # der Doppelband nennt keinen Titel je Band
    assert (en["sprache"], en["name"], en["gesamt"], en["fehlen"]) == ("en", "Englisch", 4, [2, 4])
    zwei = en["eintraege"][1]["luecke"]
    assert en["nachschlagen"]["quelle"] == "k10plus" and (zwei["titel"], zwei["isbn"].replace("-", "")) == ("Low Tide", isbn("978199999", 2))
    assert (de["reihe"], en["reihe"]) == (REIHE, REIHE_EN) and zwei["kopieren"].startswith(f"Low Tide, {AUTORIN}, {REIHE_EN} Band 2, ISBN")


async def test_eigene_angabe_gewinnt_keine_und_zurueck_zur_quelle(client, test_db, netz, ohne_abstand):
    s = await nachgeschlagen(client, test_db, netz)
    pfad = f"/api/collections/{s}/luecken"
    en = reihen((await client.patch(pfad, json={"gesamt": [{"sprache": "en", "wahl": "eigene", "zahl": 6}]})).json())["en"]
    assert (en["gesamt"], en["herkunft"], en["quelle_gesamt"], en["eigene"], en["fehlen"]) == (6, "eigene", 4, 6, [2, 4, 5, 6])
    en = reihen((await client.patch(pfad, json={"gesamt": [{"sprache": "eng", "wahl": "keine"}]})).json())["en"]
    assert (en["gesamt"], en["herkunft"], en["fehlen"]) == (None, "keine", [2])           # nur zwischen dem ersten und dem letzten
    de = reihen((await client.patch(pfad, json={"gesamt": [{"sprache": "de", "wahl": "eigene", "zahl": 7}]})).json())["de"]
    assert (de["gesamt"], de["fehlen"]) == (7, [4])                                       # eigene Angabe auch kleiner als die Quelle
    en = reihen((await client.patch(pfad, json={"gesamt": [{"sprache": "en", "wahl": "quelle"}]})).json())["en"]
    assert (en["gesamt"], en["herkunft"], en["fehlen"]) == (4, "quelle", [2, 4])
    falsch = await client.patch(pfad, json={"gesamt": [{"sprache": "en", "wahl": "eigene"}]})
    assert falsch.status_code == 422 and falsch.json()["detail"] == "Bände je Sprache, Eintrag 1: die Zahl fehlt, sie gehört zur eigenen Angabe"
    falsch = await client.patch(pfad, json={"gesamt": [{"sprache": "en", "wahl": "eigene", "zahl": 0}]})
    assert falsch.status_code == 422 and "Zahl: mindestens 1" in falsch.json()["detail"]
    assert (await client.patch("/api/collections/999999/luecken", json={"an": False})).status_code == 404


async def test_ohne_zahl_nur_zwischen_vorhandenen(client, test_db):
    s = await sammlung_erstellen(test_db, name="Krabbenhafen")
    for band in ("3", "4", "6", "9"):
        await buch(test_db, f"Krabbenhafen {band}", sammlung=s, band=band, language="de")
    de = (await luecken(client, s))["reihen"][0]
    assert (de["gesamt"], de["herkunft"], de["fehlen"], de["nachschlagen"]["stand"]) == (None, "", [5, 7, 8], "offen")


async def test_ausblenden_und_zurueckholen(client, test_db, netz, ohne_abstand):
    s = await nachgeschlagen(client, test_db, netz)
    pfad = f"/api/collections/{s}/luecken"
    a = (await client.post(f"{pfad}/ausblenden", json={"sprache": "de", "nummer": 8, "grund": "gibt_es_nicht"})).json()
    a = (await client.post(f"{pfad}/ausblenden", json={"sprache": "de", "nummer": 4, "grund": "brauche_ich_nicht"})).json()
    assert reihen(a)["de"]["fehlen"] == [9]
    assert [(x["sprache"], x["nummer"], x["grund"], x["grund_text"], x["titel"]) for x in a["ausgeblendet"]] == [
        ("de", 4, "brauche_ich_nicht", "Brauche ich nicht", "Der stille Kai"), ("de", 8, "gibt_es_nicht", "Gibt es nicht", "")]
    assert reihen(a)["en"]["fehlen"] == [2, 4]                                            # jede Sprache für sich
    a = (await client.post(f"{pfad}/zurueckholen", json={"sprache": "de", "nummer": 4})).json()
    assert reihen(a)["de"]["fehlen"] == [4, 9] and [x["nummer"] for x in a["ausgeblendet"]] == [8]
    nochmal = await client.post(f"{pfad}/zurueckholen", json={"sprache": "de", "nummer": 4})
    assert nochmal.status_code == 404 and nochmal.json()["detail"] == "Diese Lücke ist nicht ausgeblendet"
    falsch = await client.post(f"{pfad}/ausblenden", json={"sprache": "de", "nummer": 4, "grund": "egal"})
    assert falsch.status_code == 422 and falsch.json()["detail"].startswith("Grund: erlaubt ist")


async def test_platzhalter_aus_und_an(client, test_db, netz, ohne_abstand):
    s = await nachgeschlagen(client, test_db, netz)
    a = (await client.patch(f"/api/collections/{s}/luecken", json={"an": False})).json()
    assert a["an"] is False and all(r["fehlen"] == [] and all(e["art"] == "buch" for e in r["eintraege"]) for r in a["reihen"])
    assert reihen(a)["de"]["gesamt"] == 9                                                 # die Zahl bleibt für das Formular
    assert (await client.get(f"/api/collections/{s}")).json()["luecken"] == 0
    aus = await sammlung_erstellen(test_db, name="Stilles Watt")
    await buch(test_db, "Stilles Watt 1", sammlung=aus, band="1")
    await client.patch(f"/api/collections/{aus}/luecken", json={"an": False})
    assert await nachschlagen.runde() == 0                                                 # ohne Platzhalter fragt niemand
    a = (await client.patch(f"/api/collections/{s}/luecken", json={"an": True})).json()
    assert reihen(a)["de"]["fehlen"] == [4, 8, 9]


# -- Schonung der Quellen ---------------------------------------------------------------------------------------------------

async def test_eine_abfrage_je_sammlung_und_sprache_dann_vorrat(client, test_db, netz, ohne_abstand):
    s = await nachgeschlagen(client, test_db, netz)
    assert (await quellen_abruf.abruf().zustaende.von("dnb")).hintergrund == 1             # mit Vorrang Hintergrund
    await luecken(client, s)
    assert await nachschlagen.runde() == 0 and netz.zahl() == 2                             # nie wieder von selbst
    stand = (await client.get("/api/luecken/stand")).json()
    assert (stand["was"], stand["stand"], stand["offen"], stand["gesamt"], stand["fertig"]) == ("Lücken nachschlagen", "fertig", 0, 2, 2)
    a = (await client.post(f"/api/collections/{s}/luecken/nachschlagen")).json()
    assert {r["nachschlagen"]["stand"] for r in a["reihen"]} == {"offen"}
    assert await nachschlagen.runde() == 2 and netz.zahl() == 2                             # die gleiche Frage beantwortet der Vorrat
    assert reihen(await luecken(client, s))["de"]["gesamt"] == 9


async def test_keine_wiederholung_nach_fehler_und_warten_bei_pause(client, test_db, netz, ohne_abstand):
    s = await reihe_anlegen(test_db)
    netz.setze(DNB, antwort(status=500))
    netz.setze(K10, antwort(status=429, retry_after="3600"))
    await nachschlagen.runde()
    assert netz.zahl(DNB) == 1 and netz.zahl(K10) == 1
    r = reihen(await luecken(client, s))
    assert r["de"]["nachschlagen"]["stand"] == "fehler" and "500" in r["de"]["nachschlagen"]["grund"]
    assert r["en"]["nachschlagen"]["stand"] == "offen"                                     # Pause: es wurde nichts beantwortet
    stand = (await client.get("/api/luecken/stand")).json()
    assert (stand["stand"], stand["offen"]) == ("ruht", 1) and stand["grund"]
    await nachschlagen.runde()
    assert netz.zahl(DNB) == 1 and netz.zahl(K10) == 1                                     # weder der Fehler noch die Pause fragt neu


async def test_abstand_nur_zwischen_echten_abfragen(client, test_db, netz, monkeypatch):
    pausen: list[float] = []

    async def schlafen(s: float) -> None:
        pausen.append(s)

    monkeypatch.setattr(nachschlagen_modul.asyncio, "sleep", schlafen)
    monkeypatch.setattr(settings, "luecken_abstand_s", 7)
    await nachgeschlagen(client, test_db, netz)
    assert pausen == [7]                                                                   # zwischen den beiden, nicht danach


async def test_auftrag_geht_beim_start_mit_dem_offenen_weiter(client, test_db, netz, ohne_abstand):
    s = await reihe_anlegen(test_db)
    netz.setze(DNB, antwort(status=429, retry_after="3600"))
    await nachschlagen.runde()                                                             # Pause: die Runde endet, alles bleibt offen
    assert (netz.zahl(DNB), netz.zahl(K10), (await client.get("/api/luecken/stand")).json()["offen"]) == (1, 0, 2)
    await test_db.execute("DELETE FROM quelle_stand")                                      # die Pause ist vorbei
    await test_db.commit()
    quellen_abruf.einsetzen(abruf_mit(netz))                                               # wie nach einem Neustart
    netz.setze(DNB, antwort(deutsch()))
    netz.setze(K10, antwort(englisch()))
    nachschlagen.starten()
    try:
        for _ in range(200):
            if (await client.get("/api/luecken/stand")).json()["stand"] == "fertig":
                break
            await asyncio.sleep(.02)
    finally:
        await nachschlagen.stoppen()
    assert (netz.zahl(DNB), netz.zahl(K10)) == (2, 1)
    assert {r["nachschlagen"]["stand"] for r in (await luecken(client, s))["reihen"]} == {"fertig"}
    assert (await client.get("/api/collections/999999/luecken")).status_code == 404


async def test_private_titel_gehen_nie_an_eine_quelle(client, test_db, netz, ohne_abstand):
    s = await sammlung_erstellen(test_db, name="Nebelpfade")
    await buch(test_db, "Nebelpfade am Morgen", autor="Okke Ahlers", sammlung=s, band="1", language="fr")
    geheim = await buch(test_db, "Geheimbund 2 - Ein Brief", autor="Verena Verborgen", sammlung=s, band="2", language="fr")
    await test_db.execute("INSERT INTO buch_privat (profil_id, book_id) VALUES (?, ?)", (await verwaltung(test_db), geheim))
    await test_db.commit()
    netz.setze(K10, antwort(antwort_mit()))
    assert await nachschlagen.runde() == 1
    assert feld(netz.anfragen[0], "query") == 'pica.tit="Nebelpfade" and pica.per="ahlers"'


# -- Suchadresse -------------------------------------------------------------------------------------------------------------

async def test_suchadresse_mit_sonderzeichen(client, test_db, netz, ohne_abstand):
    s = await nachgeschlagen(client, test_db, netz)
    leer = (await client.get("/api/luecken/einstellungen")).json()
    assert leer["suchadresse"] == "" and [p["name"] for p in leer["platzhalter"]] == ["titel", "autor", "isbn", "band", "reihe", "sprache"]
    falsch = await client.put("/api/luecken/einstellungen", json={"suchadresse": "https://katalog.example/?q={titl}"})
    assert falsch.status_code == 422 and falsch.json()["detail"].startswith("Suchadresse: unbekannter Platzhalter {titl}")
    falsch = await client.put("/api/luecken/einstellungen", json={"suchadresse": "javascript:alert({titel})"})
    assert falsch.status_code == 422
    vorlage = "https://katalog.example/suche?q={titel} {autor}&isbn={isbn}&band={nummer}&reihe={reihe}"
    r = await client.put("/api/luecken/einstellungen", json={"suchadresse": vorlage})
    assert r.status_code == 200 and r.json()["suchadresse"] == vorlage
    await client.patch(f"/api/collections/{s}/luecken", json={"gesamt": [{"sprache": "de", "wahl": "eigene", "zahl": 9}]})
    await test_db.execute("DELETE FROM books WHERE band_nummer = '5' AND language = 'de'")
    await test_db.commit()
    de = reihen(await luecken(client, s))["de"]
    fuenf = next(e["luecke"] for e in de["eintraege"] if e["art"] == "luecke" and e["nummer"] == 5)
    assert fuenf["suchadresse"] == ("https://katalog.example/suche?q=M%C3%B6wen%20%26%20Nebel%2FTeil%20%232%2B%20Henrike%20Sandvoss"
                                    f"&isbn={isbn('978399999', 5)}&band=5&reihe=Leuchtfeuerkai")
    neun = next(e["luecke"] for e in de["eintraege"] if e["nummer"] == 9)
    assert neun["suchadresse"].startswith("https://katalog.example/suche?q=Leuchtfeuerkai%20Band%209%20Henrike%20Sandvoss&isbn=&band=9")
    probe = (await client.post("/api/luecken/suchadresse/probe", json={"suchadresse": "https://andere.example/{band}?t={titel}"})).json()
    assert (probe["sammlung"], probe["luecke"]["nummer"], probe["adresse"]) == (REIHE, 4, "https://andere.example/4?t=Der%20stille%20Kai")
    assert (await client.get("/api/luecken/einstellungen")).json()["suchadresse"] == vorlage     # die Probe merkt nichts


# -- Sammlungsvorschläge --------------------------------------------------------------------------------------------------------

async def test_vorschlaege_mit_lueckenzeile_ohne_quelle(client, test_db):
    baende = [vorschlaege.Bandangabe(buch_id=await buch(test_db, f"Lotsenruf {n} - Teil {n}", autor="Wiebke Ahrens", language="de"), band=str(n))
              for n in (1, 2, 3, 4, 5, 8)]
    englisch = [vorschlaege.Bandangabe(buch_id=await buch(test_db, f"Pilot Call {n}", autor="Wiebke Ahrens", language="en"), band=str(n))
                for n in (1, 3)]
    await vorschlaege.merken([
        vorschlaege.Ergebnis(schluessel=["lotsenruf|ahrens wiebke"], name="Lotsenruf", autor="Wiebke Ahrens", wege=[], ki="", ki_geprueft=False,
                             baende=baende),
        vorschlaege.Ergebnis(schluessel=["gemischt|ahrens wiebke"], name="Gemischt", autor="Wiebke Ahrens", wege=[], ki="", ki_geprueft=False,
                             baende=[*baende[:3], baende[4], *englisch]),
        vorschlaege.Ergebnis(schluessel=["ohne|ahrens wiebke"], name="Ohne Lücke", autor="Wiebke Ahrens", wege=[], ki="", ki_geprueft=False,
                             baende=baende[:3])])
    r = await client.get("/api/collections/vorschlaege")
    assert r.status_code == 200, r.text
    zeilen = {v["name"]: v["luecken"] for v in r.json()}
    assert zeilen == {"Lotsenruf": "vorhanden 1 bis 5 und 8, es fehlen 6 und 7",
                      "Gemischt": "Deutsch: vorhanden 1 bis 3 und 5, es fehlt 4; Englisch: vorhanden 1 und 3, es fehlt 2",
                      "Ohne Lücke": ""}
    # kein Netz: tests/conftest.py ließe keine Anfrage hinaus


# -- Familie ----------------------------------------------------------------------------------------------------------------

async def test_kinder_sehen_keine_luecken_ausser_die_stufe_erlaubt_es(client, test_db, monkeypatch):
    f = await familie_anlegen(client, test_db)
    s = await sammlung_erstellen(test_db, name="Funkelreihe")
    for name, band in (("stern", "1"), ("steuer", "2"), ("mond", "3"), ("zebra", "4")):        # zebra ist privat für Bert
        await test_db.execute("UPDATE books SET sammlung_id = ?, band_nummer = ?, language = 'de' WHERE id = ?", (s, band, f.buch[name]))
    await test_db.commit()
    for kind in ("clara", "dora", "emil"):
        for weg in (f"/api/collections/{s}/luecken", "/api/luecken/einstellungen", "/api/luecken/stand"):
            r = await client.get(weg, headers=f.kopf[kind])
            assert r.status_code == 403 and r.json()["detail"].startswith("Das darf dieses Profil nicht"), (kind, weg)
        r = await client.post("/api/luecken/suchadresse/probe", json={"suchadresse": ""}, headers=f.kopf[kind])
        assert r.status_code == 403
    ada = reihen(await luecken(client, s, f.kopf["ada"]))["de"]
    assert [e["buch_id"] for e in ada["eintraege"]] == [f.buch["stern"], f.buch["steuer"], f.buch["mond"]]   # Berts privates fehlt
    await client.patch(f"/api/collections/{s}/luecken", json={"gesamt": [{"sprache": "de", "wahl": "eigene", "zahl": 4}]}, headers=f.kopf["ada"])
    assert reihen(await luecken(client, s, f.kopf["ada"]))["de"]["fehlen"] == [4]
    assert reihen(await luecken(client, s, f.kopf["bert"]))["de"]["fehlen"] == []
    assert (await client.put("/api/luecken/einstellungen", json={"suchadresse": ""}, headers=f.kopf["bert"])).status_code == 403

    jugend = stufenbuch().stufe("jugend")
    monkeypatch.setattr(jugend, "faehigkeiten", [*jugend.faehigkeiten, "luecken"])         # eine Stufe, die es erlaubt
    emil = reihen(await luecken(client, s, f.kopf["emil"]))["de"]
    assert [e["buch_id"] for e in emil["eintraege"] if e["art"] == "buch"] == [f.buch["stern"], f.buch["mond"]]
    assert emil["fehlen"] == [2, 4]                                                         # nicht Freigegebenes ist nie "vorhanden"
    r = await client.patch(f"/api/collections/{s}/luecken", json={"an": False}, headers=f.kopf["emil"])
    assert r.status_code == 403                                                             # ändern braucht bearbeiten
    leer = await sammlung_erstellen(test_db, name="Nichts für Kinder")
    await test_db.execute("UPDATE books SET sammlung_id = ? WHERE id = ?", (leer, f.buch["steuer"]))
    await test_db.commit()
    assert (await client.get(f"/api/collections/{leer}/luecken", headers=f.kopf["emil"])).status_code == 404


# -- Hochladen in eine Lücke --------------------------------------------------------------------------------------------------

def epub(titel: str, autor: str, sprache: str) -> bytes:
    opf = ('<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">'
           f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">probe-{titel}</dc:identifier>'
           f'<dc:title>{titel}</dc:title><dc:creator>{autor}</dc:creator><dc:language>{sprache}</dc:language></metadata>'
           '<manifest><item id="k1" href="kap1.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="k1"/></spine></package>')
    container = ('<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/kap1.xhtml", f'<html xmlns="http://www.w3.org/1999/xhtml"><body><p>{titel} am Kai, ein Kapitel.</p></body></html>')
    return puffer.getvalue()


async def in_die_luecke(client, kopf, s: int, name: str, inhalt: bytes) -> tuple[str, dict]:
    v = await client.post("/api/annahme/vorschau", headers=kopf, json={"name": "Band 4", "vorgabe": {"sammlung_id": s, "band": "4", "sprache": "de"}})
    assert v.status_code == 200, v.text
    vid = v.json()["id"]
    z = await bis_bestaetigen(client, kopf, name, inhalt, vid)
    ansicht = (await client.get(f"/api/annahme/vorschau/{vid}", headers=kopf)).json()
    return vid, zeile(ansicht, name) | {"aufnahme": z["id"]}


async def test_hochladen_in_die_luecke_mit_hinweis(annahme_dienst, auth_headers, test_db, netz, ohne_abstand):
    s = await nachgeschlagen(annahme_dienst, test_db, netz)
    _, fremd = await in_die_luecke(annahme_dienst, auth_headers, s, "Salt on the Quay.epub", epub("Salt on the Quay", AUTORIN, "en"))
    felder = fremd["felder"]
    assert (felder["sammlung"]["wert"], felder["sammlung"]["herkunft"], felder["band"]["wert"], felder["band"]["herkunft"]) == (s, "luecke", "4", "luecke")
    assert (felder["sprache"]["wert"], felder["sprache"]["herkunft"]) == ("en", "datei")
    assert [(h["text"], h["herkunft"]) for h in felder["hinweise"]] == [
        ("Die Datei ist englisch, die Lücke deutsch", "luecke"), ("Die Datei heißt Salt on the Quay, die Lücke Der stille Kai", "luecke")]

    _, falscher_band = await in_die_luecke(annahme_dienst, auth_headers, s, f"{REIHE} 5 - Der stille Kai.pdf", pdf("Kai", titel="", autor=AUTORIN))
    assert [(h["text"], h["herkunft"]) for h in falscher_band["felder"]["hinweise"]] == [("Die Datei nennt Band 5, die Lücke ist Band 4", "luecke")]

    vid, passend = await in_die_luecke(annahme_dienst, auth_headers, s, "Der stille Kai.pdf", pdf("Kai am Abend", titel="Der stille Kai", autor=AUTORIN))
    assert passend["felder"]["hinweise"] == [] and passend["felder"]["sprache"]["herkunft"] == "luecke"
    r = await annahme_dienst.post(f"/api/annahme/vorschau/{vid}/uebernehmen", headers=auth_headers, json={})
    assert r.status_code == 200, r.text
    fertig = await warten(annahme_dienst, auth_headers, passend["aufnahme"])
    neu = (await annahme_dienst.get(f"/api/books/{fertig['buch_id']}", headers=auth_headers)).json()
    assert (neu["sammlung_id"], neu["band_nummer"], neu["language"]) == (s, "4", "de")
    de = reihen(await luecken(annahme_dienst, s, auth_headers))["de"]
    assert de["fehlen"] == [8, 9] and next(e for e in de["eintraege"] if e["nummer"] == 4)["buch_id"] == fertig["buch_id"]


async def test_stapel_in_die_sammlung_nach_titel_und_nummer(annahme_dienst, auth_headers, test_db, netz, ohne_abstand):
    s = await nachgeschlagen(annahme_dienst, test_db, netz)
    v = await annahme_dienst.post("/api/annahme/vorschau", headers=auth_headers, json={"name": "Stapel", "vorgabe": {"sammlung_id": s, "sprache": "de"}})
    vid = v.json()["id"]
    await bis_bestaetigen(annahme_dienst, auth_headers, "Kai.pdf", pdf("Kai am Abend", titel="Der stille Kai", autor=AUTORIN), vid)
    await bis_bestaetigen(annahme_dienst, auth_headers, f"{REIHE} 8 - Doppelt.pdf", pdf("Deich", autor=AUTORIN), vid)
    await bis_bestaetigen(annahme_dienst, auth_headers, "Unbekannt.pdf", pdf("Watt", titel="Ganz woanders", autor=AUTORIN), vid)
    ansicht = (await annahme_dienst.get(f"/api/annahme/vorschau/{vid}", headers=auth_headers)).json()
    baende = {z["name"]: (z["felder"]["sammlung"]["wert"], z["felder"]["band"]["wert"], z["felder"]["band"]["herkunft"]) for z in ansicht["zeilen"]}
    assert baende == {"Kai.pdf": (s, "4", "luecke"), f"{REIHE} 8 - Doppelt.pdf": (s, "8", "datei"), "Unbekannt.pdf": (s, "", None)}
