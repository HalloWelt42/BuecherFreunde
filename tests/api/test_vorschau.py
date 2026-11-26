"""Hochladen mit Vorschau (BF-80): Halt "Zum Bestätigen" vor dem Regal, auch über einen Neustart, die Vorschau mit Herkunft je
Feld, Ändern einzeln und für mehrere, Übernehmen, die KI ergänzt und überschreibt den Nutzer nie, Doppel und weiteres Format,
Verwerfen mit Folgenvorschau mit und ohne Kellerwolke, Einstellungen. Alle Dateien, Titel und Namen sind erfunden."""

from __future__ import annotations

import hashlib
import json
import os
import time
from urllib.parse import unquote

import fitz
import httpx
import pytest

from backend.app.annahme.dienst import annahme
from backend.app.annahme.ki_vorschau import ki_vorschau
from backend.app.core.config import settings
from tests.api.conftest import buch_erstellen, sammlung_erstellen
from tests.api.katalog_hilfen import katalog_annehmen, nummern
from tests.api.kellerwolke_attrappe import Kellerwolke
from tests.api.test_annahme_api import warten
from tests.api.test_ausfuehren import chat_antwort, leitstelle  # noqa: F401 - Attrappe der Leitstelle


def pdf(worte: str, seiten: int = 2, titel: str = "", autor: str = "") -> bytes:
    d = fitz.open()
    for n in range(seiten):
        d.new_page().insert_text((60, 80), f"{worte} Seite {n + 1}")
    if titel or autor:
        d.set_metadata({"title": titel, "author": autor})
    return d.tobytes()


async def vorschau_von(client, kopf, nr: int) -> dict:
    z = (await client.get(f"/api/annahme/{nr}", headers=kopf)).json()
    r = await client.get(f"/api/annahme/vorschau/{z['vorschau']}", headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()


def zeile(v: dict, name: str) -> dict:
    return next(z for z in v["zeilen"] if z["name"] == name)


async def bis_bestaetigen(client, kopf, name: str, inhalt: bytes, vorschau: str | None = None) -> dict:
    r = await client.post("/api/annahme", headers=kopf, json={"name": name, "groesse": len(inhalt), "sha256": hashlib.sha256(inhalt).hexdigest(),
                                                              **({"vorschau": vorschau} if vorschau else {})})
    assert r.status_code == 200, r.text
    z = r.json()
    while z["stand"] in ("wartet", "laedt") and z["empfangen"] < len(inhalt):
        stueck = inhalt[z["empfangen"]:z["empfangen"] + z["teil_groesse"]]
        r = await client.patch(f"/api/annahme/{z['id']}", headers={**kopf, "Upload-Offset": str(z["empfangen"])}, content=stueck)
        assert r.status_code == 200, r.text
        z = r.json()
    return await warten(client, kopf, z["id"], bestaetigen=False)


# -- Halt vor dem Regal ---------------------------------------------------------------------------------------------------

async def test_hochladen_wartet_und_nichts_ist_im_regal(annahme_dienst, auth_headers):
    z = await bis_bestaetigen(annahme_dienst, auth_headers, "Nebelpfad am Fluss.pdf", pdf("Nebelpfad Wiesenrand"))
    assert z["stand"] == "bestaetigen" and z["buch_id"] is None and z["vorschau"], z
    assert (await annahme_dienst.get("/api/books", headers=auth_headers)).json()["gesamt"] == 0
    assert (await annahme_dienst.get("/api/search", params={"q": "Wiesenrand"}, headers=auth_headers)).json()["gesamt"] == 0
    stats = (await annahme_dienst.get("/api/config/stats", headers=auth_headers)).json()
    assert stats.get("buecher", 0) == 0 and stats.get("gesamt", stats.get("total_books", 0)) == 0, stats
    alle = (await annahme_dienst.get("/api/annahme", headers=auth_headers)).json()
    assert alle["zaehler"]["bestaetigen"] == 1 and alle["quellen"]["hochladen"]["bestaetigen"] == 1
    assert [v["warten"] for v in alle["vorschauen"]] == [1]
    v = await vorschau_von(annahme_dienst, auth_headers, z["id"])
    r = zeile(v, "Nebelpfad am Fluss.pdf")
    assert r["rolle"] == "buch" and r["gelesen"]["seiten"] == 2 and r["felder"]["doppel"]["art"] == "neu"
    assert r["ablage"]["ort"] == "geraet"
    assert (await annahme_dienst.get(f"/api/annahme/{z['id']}/umschlag", headers=auth_headers)).status_code == 200


async def test_halt_uebersteht_den_neustart_dann_uebernehmen(annahme_dienst, auth_headers):
    z = await bis_bestaetigen(annahme_dienst, auth_headers, "Kurzer Aufsatz.pdf", pdf("Kurzer Aufsatz über Moos", seiten=3))
    await annahme.stoppen()
    annahme.starten()
    assert (await annahme_dienst.get(f"/api/annahme/{z['id']}", headers=auth_headers)).json()["stand"] == "bestaetigen"
    r = await annahme_dienst.post(f"/api/annahme/vorschau/{z['vorschau']}/uebernehmen", headers=auth_headers, json={})
    assert r.status_code == 200 and r.json()["weiter"] == 1, r.text
    fertig = await warten(annahme_dienst, auth_headers, z["id"])
    assert fertig["stand"] == "fertig" and fertig["buch_id"]
    buch = (await annahme_dienst.get(f"/api/books/{fertig['buch_id']}", headers=auth_headers)).json()
    assert buch["typ"] == "dokument" and buch["einordnung"] == "regel" and "3 Seiten" in buch["einordnung_grund"]   # die Regel der Vorschau
    assert [d["haupt"] for d in buch["dateien"]] == [True]
    assert (await annahme_dienst.get(f"/api/annahme/vorschau/{z['vorschau']}", headers=auth_headers)).json()["stand"] == "uebernommen"


async def test_herkunft_je_feld_und_aendern_fuer_mehrere(annahme_dienst, auth_headers, test_db):
    katalog = nummern(await katalog_annehmen(annahme_dienst))
    sammlung = await sammlung_erstellen(test_db, name="Sternenfahrer")
    vid = (await annahme_dienst.post("/api/annahme/vorschau", headers=auth_headers, json={"name": "Stapel", "vorgabe": {"sprache": "de"}})).json()["id"]
    eins = await bis_bestaetigen(annahme_dienst, auth_headers, "Sternenfahrer 3 - Der Nebelmond.pdf", pdf("Nebelmond", 60), vid)
    zwei = await bis_bestaetigen(annahme_dienst, auth_headers, "Rechnung Gartenbau 2026.pdf", pdf("Summe"), vid)
    v = (await annahme_dienst.get(f"/api/annahme/vorschau/{vid}", headers=auth_headers)).json()
    a, b = zeile(v, "Sternenfahrer 3 - Der Nebelmond.pdf")["felder"], zeile(v, "Rechnung Gartenbau 2026.pdf")["felder"]
    assert (a["sammlung"]["wert"], a["sammlung"]["herkunft"]) == (sammlung, "datei")
    assert (a["band"]["wert"], a["band"]["herkunft"]) == ("3", "datei")
    assert (a["sprache"]["wert"], a["sprache"]["herkunft"]) == ("de", "luecke")
    assert a["art"]["herkunft"] is None                                   # keine Regel sicher: offen für die KI
    assert (b["art"]["wert"], b["art"]["herkunft"]) == ("dokument", "regel")
    assert (b["kategorien"]["wert"], b["kategorien"]["herkunft"]) == ([katalog["besonderes/belege"]], "regel")
    r = await annahme_dienst.patch(f"/api/annahme/vorschau/{vid}", headers=auth_headers,
                                   json={"ids": [eins["id"], zwei["id"]], "felder": {"art": "heft", "kategorien": [katalog["besonderes/belege"]]}})
    assert r.status_code == 200, r.text
    for z in r.json()["zeilen"]:
        assert (z["felder"]["art"]["wert"], z["felder"]["art"]["herkunft"]) == ("heft", "nutzer")
        assert z["felder"]["kategorien"]["herkunft"] == "nutzer"
    falsch = await annahme_dienst.patch(f"/api/annahme/vorschau/{vid}", headers=auth_headers, json={"ids": [eins["id"]], "felder": {"kategorien": [999999]}})
    assert falsch.status_code == 422 and "Kategorien" in falsch.json()["detail"]
    falsch = await annahme_dienst.patch(f"/api/annahme/vorschau/{vid}", headers=auth_headers, json={"ids": [eins["id"]], "felder": {"art": "material"}})
    assert falsch.status_code == 422 and falsch.json()["detail"].startswith("Ziel")
    r = await annahme_dienst.post(f"/api/annahme/vorschau/{vid}/uebernehmen", headers=auth_headers, json={"ids": [eins["id"]]})
    assert r.json()["weiter"] == 1 and r.json()["vorschau"]["stand"] == "offen"          # zwei wartet weiter
    buch = (await annahme_dienst.get(f"/api/books/{(await warten(annahme_dienst, auth_headers, eins['id']))['buch_id']}", headers=auth_headers)).json()
    assert (buch["typ"], buch["einordnung"], buch["sammlung_id"], buch["band_nummer"], buch["language"]) == ("heft", "hand", sammlung, "3", "de")
    assert [k["id"] for k in buch["categories"] if k["art"] == "kategorie"] == [katalog["besonderes/belege"]]


# -- KI im Hintergrund --------------------------------------------------------------------------------------------------------

@pytest.fixture
def ki_sagt(leitstelle, monkeypatch):  # noqa: F811
    """Die Leitstelle als Attrappe: Art und Kategorie je nach Anfrage, ohne Pausen."""
    monkeypatch.setattr(settings, "einordnen_abstand_s", 0)
    modelle = leitstelle.antwort
    leitstelle.titel = []

    async def antwort(r: httpx.Request) -> httpx.Response:
        if r.url.path == "/v1/models":
            return modelle(r)
        leitstelle.titel.append(r.headers.get("X-Leitstelle-Titel", ""))
        schema = json.loads(r.content)["response_format"]["json_schema"]["name"]
        if schema == "vorschau_art":
            return chat_antwort(json.dumps({"werke": [{"nummer": 1, "art": "dokument", "gattung": ""}, {"nummer": 2, "art": "dokument", "gattung": ""}]}))
        return chat_antwort(json.dumps({"buecher": [{"nummer": 1, "kategorien": [{"schluessel": "besonderes/belege", "sicherheit": 90, "satz": "Ein Beleg"}]},
                                                    {"nummer": 2, "kategorien": [{"schluessel": "besonderes/belege", "sicherheit": 90, "satz": "Ein Beleg"}]}]}))

    leitstelle.antwort = antwort
    return leitstelle


async def test_ki_ergaenzt_und_ueberschreibt_den_nutzer_nie(annahme_dienst, auth_headers, ki_sagt):
    katalog = nummern(await katalog_annehmen(annahme_dienst))
    vid = (await annahme_dienst.post("/api/annahme/vorschau", headers=auth_headers, json={"name": "Zwei"})).json()["id"]
    frei = await bis_bestaetigen(annahme_dienst, auth_headers, "Notizen vom Teich.pdf", pdf("Teich", 12), vid)
    selbst = await bis_bestaetigen(annahme_dienst, auth_headers, "Gedanken am Hang.pdf", pdf("Hang", 12), vid)
    v = (await annahme_dienst.get(f"/api/annahme/vorschau/{vid}", headers=auth_headers)).json()
    assert {z["ki"] for z in v["zeilen"]} == {"offen"} and v["zaehler"]["ki"] == 2
    await annahme_dienst.patch(f"/api/annahme/vorschau/{vid}", headers=auth_headers, json={"ids": [selbst["id"]], "felder": {"art": "heft"}})
    assert await ki_vorschau.runde() == 2
    v = (await annahme_dienst.get(f"/api/annahme/vorschau/{vid}", headers=auth_headers)).json()
    a, b = zeile(v, "Notizen vom Teich.pdf"), zeile(v, "Gedanken am Hang.pdf")
    assert (a["felder"]["art"]["wert"], a["felder"]["art"]["herkunft"], a["ki"]) == ("dokument", "ki", "fertig")
    assert (a["felder"]["kategorien"]["wert"], a["felder"]["kategorien"]["herkunft"]) == ([katalog["besonderes/belege"]], "ki")
    assert (b["felder"]["art"]["wert"], b["felder"]["art"]["herkunft"]) == ("heft", "nutzer")        # die KI fasst es nicht an
    fragen = [unquote(t).split(": ", 1)[1] for t in ki_sagt.titel]
    assert fragen == ["Vorschau, Art: 1 Datei ab Notizen vom Teich.pdf", "Vorschau, Kategorie: 1 Datei", "Vorschau, Kategorie: 1 Datei"]
    # gebündelt: die Art einmal für alle offenen, die Kategorie je Art einmal (Dokument und Heft)
    assert await ki_vorschau.runde() == 0                                                               # nichts mehr offen
    await annahme_dienst.post(f"/api/annahme/vorschau/{vid}/uebernehmen", headers=auth_headers, json={})
    buch = (await annahme_dienst.get(f"/api/books/{(await warten(annahme_dienst, auth_headers, frei['id']))['buch_id']}", headers=auth_headers)).json()
    assert (buch["typ"], buch["einordnung"]) == ("dokument", "ki")


# -- Doppel und weiteres Format ---------------------------------------------------------------------------------------------

async def test_gleiche_datei_weglassen_weiteres_format_und_eigenes_buch(annahme_dienst, auth_headers, test_db):
    vorhanden = await buch_erstellen(test_db, hash="vorhanden-epub", title="Das Lied der Krähen", author="Wanda Beispiel", file_format="epub",
                                     file_name="Lied.epub", isbn="")
    inhalt = pdf("Krähenlied", 30, titel="Das Lied der Krähen", autor="Wanda Beispiel")
    z = await bis_bestaetigen(annahme_dienst, auth_headers, "Lied der Krähen.pdf", inhalt)
    v = await vorschau_von(annahme_dienst, auth_headers, z["id"])
    f = zeile(v, "Lied der Krähen.pdf")["felder"]
    assert (f["doppel"]["art"], f["doppel"]["wahl"], f["doppel"]["herkunft"], f["ziel"]["buch_id"]) == ("format", "format", "bestand", vorhanden)
    assert f["art"]["herkunft"] == "bestand" and "EPUB" in f["doppel"]["grund"]
    await annahme_dienst.post(f"/api/annahme/vorschau/{z['vorschau']}/uebernehmen", headers=auth_headers, json={})
    fertig = await warten(annahme_dienst, auth_headers, z["id"])
    assert fertig["stand"] == "fertig" and fertig["buch_id"] == vorhanden and "weiteres Format" in fertig["text"], fertig
    buch = (await annahme_dienst.get(f"/api/books/{vorhanden}", headers=auth_headers)).json()
    assert [(d["format"], d["haupt"]) for d in buch["dateien"]] == [("epub", True), ("pdf", False)]
    assert (await annahme_dienst.get("/api/books", headers=auth_headers)).json()["gesamt"] == 1
    datei = await annahme_dienst.get(f"/api/books/{vorhanden}/file", params={"format": "pdf"}, headers=auth_headers)
    assert datei.status_code == 200 and datei.content == inhalt
    assert (await annahme_dienst.get(f"/api/books/{vorhanden}/file", params={"format": "mobi"}, headers=auth_headers)).status_code == 404

    noch_einmal = await bis_bestaetigen(annahme_dienst, auth_headers, "Noch einmal.pdf", inhalt)        # gleiche Datei: gleich da
    assert noch_einmal["stand"] == "da" and noch_einmal["buch_id"] == vorhanden and "PDF" in noch_einmal["text"]
    assert zeile(await vorschau_von(annahme_dienst, auth_headers, noch_einmal["id"]), "Noch einmal.pdf")["rolle"] == "doppel"

    anders = pdf("Krähenlied, zweite Ausgabe", 31, titel="Das Lied der Krähen", autor="Wanda Beispiel")
    eigen = await bis_bestaetigen(annahme_dienst, auth_headers, "Lied, andere Ausgabe.pdf", anders)
    v = await vorschau_von(annahme_dienst, auth_headers, eigen["id"])
    assert zeile(v, "Lied, andere Ausgabe.pdf")["felder"]["doppel"]["art"] == "neu"                  # ein PDF hat das Buch schon
    hinweis = zeile(v, "Lied, andere Ausgabe.pdf")["felder"]["hinweise"][0]
    assert "schon als PDF" in hinweis["text"] and hinweis["herkunft"] == "bestand"
    await annahme_dienst.post(f"/api/annahme/vorschau/{v['id']}/uebernehmen", headers=auth_headers, json={})
    assert (await warten(annahme_dienst, auth_headers, eigen["id"]))["buch_id"] != vorhanden


# -- Verwerfen -------------------------------------------------------------------------------------------------------------

async def test_verwerfen_ohne_kellerwolke_loescht_endgueltig_nach_den_folgen(annahme_dienst, auth_headers):
    z = await bis_bestaetigen(annahme_dienst, auth_headers, "Wegwerfprobe.pdf", pdf("Wegwerfprobe"))
    vid = z["vorschau"]
    assert (await annahme_dienst.delete(f"/api/annahme/vorschau/{vid}", headers=auth_headers)).status_code == 422     # ohne stand
    folgen = (await annahme_dienst.get(f"/api/annahme/vorschau/{vid}/folgen", headers=auth_headers)).json()
    [f] = folgen["dateien"]
    assert (f["name"], f["wirkung"], folgen["endgueltig"], folgen["papierkorb"]) == ("Wegwerfprobe.pdf", "endgueltig", 1, 0)
    datei = settings.eingang_dir / str(z["id"]) / "Wegwerfprobe.pdf"
    assert f["pfad"] == str(datei) and datei.exists()
    assert (await annahme_dienst.delete(f"/api/annahme/vorschau/{vid}", params={"stand": "falsch"}, headers=auth_headers)).status_code == 409
    r = await annahme_dienst.delete(f"/api/annahme/vorschau/{vid}", params={"stand": folgen["stand"]}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["verworfen"] == 1 and r.json()["vorschau"]["stand"] == "verworfen"
    assert not datei.exists() and not (settings.storage_dir / z["sha256"][:2] / z["sha256"][2:4] / z["sha256"]).exists()
    assert (await annahme_dienst.get(f"/api/annahme/{z['id']}", headers=auth_headers)).json()["stand"] == "verworfen"     # bleibt im Verlauf
    assert (await annahme_dienst.get("/api/books", headers=auth_headers)).json()["gesamt"] == 0


async def test_verwerfen_mit_kellerwolke_in_den_papierkorb(annahme_dienst, auth_headers, monkeypatch):
    wolke = Kellerwolke()
    wolke.einhaengen(monkeypatch)
    z = await bis_bestaetigen(annahme_dienst, auth_headers, "Papierkorbprobe.pdf", pdf("Papierkorbprobe"))
    assert z["stand"] == "bestaetigen"
    folgen = (await annahme_dienst.get(f"/api/annahme/vorschau/{z['vorschau']}/folgen", headers=auth_headers)).json()
    assert [f["wirkung"] for f in folgen["dateien"]] == ["papierkorb"] and folgen["papierkorb"] == 1
    r = await annahme_dienst.delete(f"/api/annahme/vorschau/{z['vorschau']}", params={"stand": folgen["stand"]}, headers=auth_headers)
    assert r.status_code == 200
    assert wolke.im_papierkorb() == [f"{z['id']} Papierkorbprobe.pdf"]


async def test_uebernehmen_mit_kellerwolke_legt_ab(annahme_dienst, auth_headers, monkeypatch):
    wolke = Kellerwolke()
    wolke.einhaengen(monkeypatch)
    z = await bis_bestaetigen(annahme_dienst, auth_headers, "Wolkenprobe.pdf", pdf("Wolkenprobe"))
    assert zeile(await vorschau_von(annahme_dienst, auth_headers, z["id"]), "Wolkenprobe.pdf")["ablage"]["ort"] == "kellerwolke"
    await annahme_dienst.post(f"/api/annahme/vorschau/{z['vorschau']}/uebernehmen", headers=auth_headers, json={})
    fertig = await warten(annahme_dienst, auth_headers, z["id"])
    assert fertig["stand"] == "fertig"
    assert any(p.startswith("Apps/BücherFreunde/Bücher/W/Wolkenprobe [") for p in (wolke.pfad(k) for k in wolke.knoten))


# -- Einstellungen und andere Wege ----------------------------------------------------------------------------------------

async def test_einstellungen_und_eingangsordner_erst_bestaetigen(annahme_dienst, auth_headers, tmp_path, monkeypatch):
    from backend.app.annahme import eingangsordner

    r = await annahme_dienst.get("/api/annahme/einstellungen", headers=auth_headers)
    assert r.status_code == 200 and r.json()["bestaetigen"] == {"hochladen": True, "eingangsordner": False, "ordner": False}
    neu = r.json() | {"bestaetigen": {"hochladen": True, "eingangsordner": True, "ordner": False}}
    assert (await annahme_dienst.put("/api/annahme/einstellungen", headers=auth_headers, json=neu)).json()["bestaetigen"]["eingangsordner"] is True
    falsch = await annahme_dienst.put("/api/annahme/einstellungen", headers=auth_headers, json=neu | {"bestaetigen": {**neu["bestaetigen"], "hochladen": False}})
    assert falsch.status_code == 422
    falsch = await annahme_dienst.put("/api/annahme/einstellungen", headers=auth_headers, json=neu | {"zip": {**neu["zip"], "dateien": 0}})
    assert falsch.status_code == 422

    ort = tmp_path / "eingangsordner"
    monkeypatch.setattr(settings, "eingangsordner_dir", ort)
    eingangsordner.einrichten()
    datei = ort / "Abgelegtes Heft.pdf"
    datei.write_bytes(pdf("Abgelegtes Heft"))
    os.utime(datei, (time.time() - 60, time.time() - 60))
    assert await eingangsordner.aufnehmen() == 1
    nr = (await annahme_dienst.get("/api/annahme", headers=auth_headers)).json()["eintraege"][0]["id"]
    z = await warten(annahme_dienst, auth_headers, nr, bestaetigen=False)
    assert z["stand"] == "bestaetigen" and z["quelle"] == "eingangsordner"
    v = await vorschau_von(annahme_dienst, auth_headers, nr)
    assert (v["name"], v["quelle"]) == ("Eingangsordner", "eingangsordner")
    assert datei.exists()                                                     # wartet im Eingangsordner
    assert await eingangsordner.aufnehmen() == 0


async def test_einstellungen_nur_mit_der_faehigkeit(client, test_db):
    from tests.api.familie_hilfen import familie_anlegen

    f = await familie_anlegen(client, test_db)
    assert (await client.get("/api/annahme/einstellungen", headers=f.kopf["bert"])).status_code == 403
    assert (await client.get("/api/annahme/vorschau", headers=f.kopf["dora"])).status_code == 403


async def test_anleitung_kommt_einmal_zu_den_bereichen_fuer_dokumente(client, test_db):
    from backend.app.katalog.kategorien import anleitung_nachziehen

    katalog = await katalog_annehmen(client)                                  # Besonderes gilt für dokument und heft
    besonderes = nummern(katalog)["besonderes"]
    assert await anleitung_nachziehen() == 1
    arten = lambda: test_db.fetch_one("SELECT arten FROM categories WHERE id = ?", (besonderes,))      # noqa: E731
    assert json.loads((await arten())["arten"]) == ["dokument", "heft", "anleitung"]
    await test_db.execute("UPDATE categories SET arten = '[\"dokument\"]' WHERE id = ?", (besonderes,))   # der Nutzer nimmt sie wieder heraus
    await test_db.commit()
    assert await anleitung_nachziehen() == 0 and json.loads((await arten())["arten"]) == ["dokument"]
