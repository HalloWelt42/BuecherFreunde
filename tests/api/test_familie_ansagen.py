"""Feste Ansagen (BF-78): Texte als Daten mit Zahlwörtern, vorab gesprochen mit einer eingebauten Stimme im Auftrag "Ansagen
erstellen" (nur, was fehlt, im Hintergrund, weiter nach einem Neustart), dauerhaft abgelegt; Ansagen der Dinge (Titel erst
nach der Freigabe, Katze, Ruhezeit, Namen), Stimme je Kind, Probe und Rechte. Der Sprechdienst ist eine Attrappe; alles erfunden."""

from __future__ import annotations

import re

import pytest

from backend.app.core.config import settings
from backend.app.familie import ansagen
from backend.app.familie.ansagelauf import Ansagelauf, ansagelauf, staende
from backend.app.familie.stufen import stufenbuch
from backend.app.services import vorlesen
from tests.api.familie_hilfen import anlegen, familie_anlegen, freigeben, waehlen

KERSTIN, THORSTEN = "katalog:Kerstin", "katalog:Thorsten"
# die Schlüssel, die der Kinderbereich nennt (frontend/src/lib/kind/ansagen.ts)
TASTEN = {"weiter", "zurueck", "pause", "vorlesen", "silben_an", "silben_aus", "zeile_an", "zeile_aus", "mein_regal", "lieblinge",
          "gelesen", "schloss", "zum_regal", "stift_an", "stift_aus", "gemerkt", "lesezeichen_weg", "notiz", "lieblingsbuch",
          "kein_lieblingsbuch", "fertig"}
HINWEISE = {"lesezeit_gleich_um", "lesezeit_um", "frag_eltern", "katze_benennen", "buch_fertig", "regal_leer", "lieblinge_leer",
            "gelesen_leer", "suche_leer", "wer_liest", "bild_pin", "bild_pin_falsch"}


class Sprecher:
    """Statt des Sprechdienstes: merkt sich jeden Auftrag; `bis` lässt ihn nach so vielen Sätzen ausfallen."""

    def __init__(self) -> None:
        self.auftraege: list[tuple[str, str, str]] = []
        self.bis: int | None = None

    async def satz(self, text: str, stimme: str, prioritaet: str = "hoch") -> bytes:
        if self.bis is not None and len(self.auftraege) >= self.bis:
            raise vorlesen.VorlesenFehler("Vorlesen gerade nicht möglich: die Leitstelle schläft")
        self.auftraege.append((text, stimme, prioritaet))
        return b"RIFF" + text.encode()


@pytest.fixture
def sprecher(monkeypatch, tmp_path) -> Sprecher:
    s = Sprecher()
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "texte")
    monkeypatch.setattr(vorlesen, "bereit", lambda: True)
    monkeypatch.setattr(vorlesen, "satz", s.satz)
    return s


async def _stimme(client, f, kind: str, stimme: str) -> None:
    r = await client.patch(f"/api/familie/profile/{f.ids[kind]}", json={"einstellungen": {"lesehilfen": {"stimme": stimme}}}, headers=f.kopf["ada"])
    assert r.status_code == 200, r.text


# -- Texte ----------------------------------------------------------------------------------------------------------------------

def test_texte_vollstaendig():
    t = ansagen.texte()
    assert set(t.tasten) == TASTEN and all(t.tasten.values())
    assert set(t.hinweise) == HINWEISE and all(t.hinweise.values())
    schluessel = [e.schluessel for e in ansagen.allgemeine()]
    assert len(schluessel) == len(set(schluessel))
    for art, bis in (("uhr", 12), ("minute", 59), ("noch", 120), ("heute", 120)):
        assert {f"{art}.{n}" for n in range(1, bis + 1)} <= set(schluessel)
    assert t.probe == "Hallo, ich lese dir vor. Tippe auf ein Buch."


@pytest.mark.parametrize(("n", "form", "wort"), [
    (1, "zahl", "eins"), (1, "vor", "ein"), (1, "weiblich", "eine"), (7, "zahl", "sieben"), (11, "zahl", "elf"), (16, "zahl", "sechzehn"),
    (17, "zahl", "siebzehn"), (21, "weiblich", "einundzwanzig"), (30, "zahl", "dreißig"), (35, "zahl", "fünfunddreißig"),
    (59, "zahl", "neunundfünfzig"), (100, "zahl", "hundert"), (101, "zahl", "hunderteins"), (101, "weiblich", "hunderteine"),
    (112, "zahl", "hundertzwölf"), (120, "zahl", "hundertzwanzig"), (0, "zahl", "null"),
])
def test_zahlwoerter(n, form, wort):
    assert ansagen.zahlwort(n, form) == wort


def test_bausteine_und_uhrzeit_in_worten():
    texte = {e.schluessel: e.text for e in ansagen.allgemeine()}
    assert (texte["uhr.1"], texte["uhr.4"], texte["minute.35"]) == ("Es ist ein Uhr", "Es ist vier Uhr", "fünfunddreißig")
    assert (texte["noch.1"], texte["noch.2"], texte["noch.101"], texte["heute.21"]) == (
        "Noch eine Minute", "Noch zwei Minuten", "Noch hunderteine Minute", "Heute einundzwanzig Minuten")
    assert texte["hinweise.bild_pin"] == "Tippe drei Bilder an." and texte["tasten.zurueck"] == "Zurück"
    assert [ansagen.uhrzeit_wort(u) for u in ("06:30", "07:00", "01:05", "19:45")] == [
        "sechs Uhr dreißig", "sieben Uhr", "ein Uhr fünf", "neunzehn Uhr fünfundvierzig"]


# -- Stimme und Erzeugen ------------------------------------------------------------------------------------------------------------

async def test_ohne_stimme_schweigen_die_ansagen(client, test_db, sprecher):
    f = await familie_anlegen(client, test_db)
    a = (await client.get("/api/familie/ansagen", headers=f.kopf["clara"])).json()
    assert (a["stimme"], a["fertig"], a["eintraege"]) == ("", 0, {}) and a["gesamt"] > 0
    await ansagelauf.runde()
    assert sprecher.auftraege == []


async def test_nur_was_fehlt_im_hintergrund(client, test_db, sprecher):
    f = await familie_anlegen(client, test_db)
    assert (await client.put("/api/familie/stimme", json={"stimme": KERSTIN}, headers=f.kopf["ada"])).status_code == 200
    assert (await client.get("/api/familie", headers=f.kopf["ada"])).json()["stimme"] == KERSTIN
    await ansagelauf.runde()
    bedarf = (await ansagen.bedarf())[KERSTIN]
    assert len(sprecher.auftraege) == len(bedarf) and {p for _t, _s, p in sprecher.auftraege} == {"hintergrund"}
    await ansagelauf.runde()
    assert len(sprecher.auftraege) == len(bedarf)                                           # nichts fehlt, nichts neu
    clara = (await client.get("/api/familie/ansagen", headers=f.kopf["clara"])).json()
    assert clara["stimme"] == KERSTIN and clara["fertig"] == clara["gesamt"] and clara["laeuft"] is False
    assert clara["eintraege"]["tasten.weiter"]["text"] == "Weiter"
    assert clara["eintraege"]["ruhezeit"]["text"] == "Jetzt ist Ruhezeit. Ab sechs Uhr dreißig kannst du wieder lesen."
    assert clara["eintraege"][f"titel.{f.buch['mond']}"]["text"] == "Mondfahrt mit Paula"
    [stand] = (await client.get("/api/familie/ansagen/stand", params={"stimme": KERSTIN}, headers=f.kopf["ada"])).json()
    assert (stand["was"], stand["stand"], stand["fertig"], stand["gesamt"]) == ("Ansagen erstellen", "fertig", len(bedarf), len(bedarf))
    assert stand["fertig_am"] and stand["begonnen"]
    ton = await client.get(clara["eintraege"]["tasten.weiter"]["url"], headers=f.kopf["clara"])
    assert ton.status_code == 200 and ton.content == b"RIFFWeiter" and ton.headers["content-type"] == "audio/wav"
    assert "immutable" in ton.headers["cache-control"]
    assert (await client.get(clara["eintraege"]["tasten.weiter"]["url"], headers=f.kopf["clara"] | {"If-None-Match": ton.headers["etag"]})).status_code == 304
    wer = (await client.get("/api/familie/ansagen")).json()                                 # die Profilwahl, ohne Profil
    assert wer["eintraege"][f"profil.{f.ids['bert']}"]["text"] == "Bert" and "hinweise.wer_liest" in wer["eintraege"]


async def test_textaenderung_spricht_neu_und_raeumt_danach_auf(client, test_db, sprecher, monkeypatch):
    f = await familie_anlegen(client, test_db)
    await _stimme(client, f, "clara", THORSTEN)
    await client.patch("/api/familie/ich/katze", json={"name": "Flocke"}, headers=f.kopf["clara"])
    await ansagelauf.runde()
    ort = ansagen.pfad(THORSTEN)
    vorher = len(sprecher.auftraege)
    await client.patch("/api/familie/ich/katze", json={"name": "Mimi"}, headers=f.kopf["clara"])
    await ansagelauf.runde()
    assert sprecher.auftraege[vorher:] == [("Mimi", THORSTEN, "hintergrund")]
    assert len([d for d in ort.glob("*.wav") if re.fullmatch(r"katze-[0-9a-f]{16}\.wav", d.name)]) == 1   # der alte Ton ist fort
    assert (await client.get("/api/familie/ansagen", headers=f.kopf["clara"])).json()["eintraege"]["katze"]["text"] == "Mimi"
    anzahl = len(list(ort.glob("*.wav")))
    monkeypatch.setattr(ansagen.texte(), "fassung", ansagen.texte().fassung + 1)            # neue Fassung der Texte: alles neu
    await ansagelauf.runde()
    assert len(sprecher.auftraege) == vorher + 1 + anzahl and len(list(ort.glob("*.wav"))) == anzahl


async def test_titel_erst_nach_der_freigabe(client, test_db, sprecher):
    f = await familie_anlegen(client, test_db)
    lena = (await anlegen(client, f.kopf["ada"], name="Lena", rolle="kind", stufe="erstes_lesen",
                          einstellungen={"lesehilfen": {"stimme": KERSTIN}}))["id"]
    titel = lambda: {e.schluessel for e in bedarf if e.schluessel.startswith("titel.")}   # noqa: E731
    bedarf = (await ansagen.bedarf())[KERSTIN]
    assert titel() == set()
    await freigeben(client, f.kopf["ada"], lena, "buch", [f.buch["steuer"]])
    bedarf = (await ansagen.bedarf())[KERSTIN]
    assert titel() == {f"titel.{f.buch['steuer']}"}
    await ansagelauf.runde()
    kopf = await waehlen(client, lena)
    assert (await client.get("/api/familie/ansagen", headers=kopf)).json()["eintraege"][f"titel.{f.buch['steuer']}"]["text"] == "Steuerkram ganz trocken"


async def test_weiter_nach_einem_neustart(client, test_db, sprecher):
    f = await familie_anlegen(client, test_db)
    await _stimme(client, f, "dora", KERSTIN)
    sprecher.bis = 5
    await ansagelauf.runde()
    [stand] = await staende(KERSTIN)
    assert (stand.stand, stand.fertig) == ("fehler", 5) and "schläft" in stand.grund
    begonnen = stand.begonnen
    sprecher.bis = None
    await Ansagelauf().runde()                                                              # wie nach einem Neustart
    [stand] = await staende(KERSTIN)
    assert (stand.stand, stand.fertig) == ("fertig", stand.gesamt) and stand.begonnen == begonnen
    assert len(sprecher.auftraege) == stand.gesamt                                          # jeder Satz genau einmal


async def test_ohne_sprechdienst_steht_der_grund_am_auftrag(client, test_db, sprecher, monkeypatch):
    f = await familie_anlegen(client, test_db)
    await _stimme(client, f, "dora", KERSTIN)
    monkeypatch.setattr(vorlesen, "bereit", lambda: False)
    await ansagelauf.runde()
    [stand] = await staende(KERSTIN)
    assert stand.stand == "fehler" and "Sprechdienst" in stand.grund and sprecher.auftraege == []


async def test_stimme_des_geraets_nur_als_wahl(client, test_db, sprecher):
    f = await familie_anlegen(client, test_db)
    await _stimme(client, f, "clara", "geraet")
    a = (await client.get("/api/familie/ansagen", headers=f.kopf["clara"])).json()
    assert a["stimme"] == "geraet" and a["fertig"] == a["gesamt"] and a["eintraege"]["tasten.pause"] == {"text": "Pause", "url": None}
    await ansagelauf.runde()
    assert sprecher.auftraege == []                                                         # das Gerät spricht selbst
    r = await client.patch(f"/api/familie/profile/{f.ids['clara']}", json={"einstellungen": {"lesehilfen": {"stimme": "Kerstin"}}},
                           headers=f.kopf["ada"])
    assert r.status_code == 422


# -- Probe und Rechte -------------------------------------------------------------------------------------------------------------

async def test_probe_fuer_die_eltern(client, test_db, sprecher):
    f = await familie_anlegen(client, test_db)
    r = await client.post("/api/familie/ansagen/probe", json={"stimme": THORSTEN}, headers=f.kopf["bert"])
    assert r.status_code == 200 and r.json()["text"] == ansagen.texte().probe
    assert sprecher.auftraege == [(ansagen.texte().probe, THORSTEN, "hoch")]
    assert (await client.get(r.json()["url"], headers=f.kopf["bert"])).status_code == 200
    await client.post("/api/familie/ansagen/probe", json={"stimme": THORSTEN}, headers=f.kopf["ada"])
    assert len(sprecher.auftraege) == 1                                                     # abgelegt, nicht noch einmal
    assert (await client.post("/api/familie/ansagen/probe", json={"stimme": "geraet"}, headers=f.kopf["ada"])).json()["url"] is None
    assert (await client.post("/api/familie/ansagen/probe", json={"stimme": THORSTEN}, headers=f.kopf["emil"])).status_code == 403
    assert (await client.get("/api/familie/ansagen/stand", headers=f.kopf["clara"])).status_code == 403


async def test_ein_kind_hoert_nur_seine_stimme(client, test_db, sprecher):
    f = await familie_anlegen(client, test_db)
    await client.put("/api/familie/stimme", json={"stimme": KERSTIN}, headers=f.kopf["ada"])
    await _stimme(client, f, "clara", THORSTEN)
    await ansagelauf.runde()
    dora = (await client.get("/api/familie/ansagen", headers=f.kopf["dora"])).json()      # ohne eigene Wahl: die der Familie
    clara = (await client.get("/api/familie/ansagen", headers=f.kopf["clara"])).json()
    assert (dora["stimme"], clara["stimme"]) == (KERSTIN, THORSTEN)
    assert (await client.get(dora["eintraege"]["tasten.weiter"]["url"], headers=f.kopf["clara"])).status_code == 403
    assert (await client.get(clara["eintraege"]["tasten.weiter"]["url"], headers=f.kopf["clara"])).status_code == 200
    assert (await client.get(clara["eintraege"]["tasten.weiter"]["url"], headers=f.kopf["ada"])).status_code == 200    # Eltern jede
    assert (await client.get(f"/api/familie/ansagen/ton/{ansagen.ordner(THORSTEN)}/unsinn.wav", headers=f.kopf["ada"])).status_code == 404
    assert (await client.put("/api/familie/stimme", json={"stimme": THORSTEN}, headers=f.kopf["bert"])).status_code == 403


async def test_hinweise_sprechen_und_tasten_ansagen_je_stufe(client, test_db):
    f = await familie_anlegen(client, test_db)
    for kind, an in (("clara", True), ("dora", False), ("emil", False)):
        hilfen = (await client.get("/api/familie/ich", headers=f.kopf[kind])).json()["lesehilfen"]
        assert (hilfen["hinweise_sprechen"], hilfen["tasten_ansagen"]) == (an, an), kind
    wahl = {"hinweise_sprechen": False, "tasten_ansagen": True}
    r = await client.patch(f"/api/familie/profile/{f.ids['clara']}", json={"einstellungen": {"lesehilfen": wahl}}, headers=f.kopf["ada"])
    assert r.status_code == 200
    hilfen = r.json()["einstellungen"]["lesehilfen"]
    assert (hilfen["hinweise_sprechen"], hilfen["tasten_ansagen"]) == (False, True)


async def test_den_ton_auf_abruf_gibt_es_nicht_mehr(client, test_db):
    assert (await client.post("/api/vorlesen/ansage", json={"text": "Weiter."})).status_code in (404, 405)


async def test_vorschlaege_fuer_den_katzennamen_im_vorlesealter(client, test_db, sprecher):
    f = await familie_anlegen(client, test_db)
    await _stimme(client, f, "clara", KERSTIN)
    await _stimme(client, f, "dora", THORSTEN)
    await ansagelauf.runde()
    clara = (await client.get("/api/familie/ansagen", headers=f.kopf["clara"])).json()["eintraege"]
    dora = (await client.get("/api/familie/ansagen", headers=f.kopf["dora"])).json()["eintraege"]
    vorschlaege = stufenbuch().katze.vorschlaege
    assert {f"katze.{v}" for v in vorschlaege} <= set(clara) and clara["katze.Pfötchen"]["text"] == "Pfötchen"
    assert not any(k.startswith("katze.") for k in dora)                                   # ab Erstes Lesen tippt das Kind selbst
    assert all(re.fullmatch(r"/api/familie/ansagen/ton/[a-z0-9-]+/[a-z0-9-]+-[0-9a-f]{16}\.wav", e["url"]) for e in clara.values())
