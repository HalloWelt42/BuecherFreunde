"""Jeder Weg der Schnittstelle zum Übersetzen (BF-71, docs/neubau/UEBERSETZUNG.md): Fassungen, Rückfrage, Start, Stand mit
Stationen und Kapiteln, Pause, Fortsetzen, Abbrechen, Bericht, Blöcke von Hand, Datei für den Leser, Begriffsliste."""

import asyncio
import json

from backend.app.core.config import settings
from backend.app.services import begriffsliste, fassungen
from backend.app.services.ki import ki
from backend.app.services.uebersetzungslauf import Uebersetzungslauf, uebersetzungslauf
from tests.api.test_ausfuehren import leitstelle  # noqa: F401 - Attrappe der Leitstelle
from tests.api.uebersetzer import DEUTSCH, orte, probebuch, uebersetzer  # noqa: F401 - Fixtures
from backend.app.uebersetzung.zerlegen_epub import zerlegen
from tests.uebersetzung_probe import dateien, probe_epub

STATIONEN = ["Zerlegen", "Begriffe", "Übersetzen", "Prüfen", "Nacharbeit", "Setzen"]
ZAHL = "A small machine can water <t1>16,000</t1> plants in 1.5 hours, which is about 3 GB of logs.<x2/>"


async def fertig_uebersetzt(client, test_db, uebersetzer, **ersetzt) -> tuple[int, int]:
    uebersetzer.tabelle.update(ersetzt)
    buch = await probebuch(test_db)
    fid = (await client.post(f"/api/books/{buch}/fassungen/de")).json()["id"]
    await Uebersetzungslauf(ki).runde()
    return buch, fid


# -- Fassungen und Rückfrage --------------------------------------------------------------------------------------------------

async def test_fassungen_original_zuerst(client, test_db, uebersetzer):
    buch = await probebuch(test_db)
    [original] = (await client.get(f"/api/books/{buch}/fassungen")).json()
    assert {k: original[k] for k in ("id", "sprache", "original", "stand", "kapitel_fertig", "kapitel_gesamt")} == {
        "id": None, "sprache": "en", "original": True, "stand": "fertig", "kapitel_fertig": None, "kapitel_gesamt": None}
    fid = (await client.post(f"/api/books/{buch}/fassungen/de")).json()["id"]
    await Uebersetzungslauf(ki).runde()
    alle = (await client.get(f"/api/books/{buch}/fassungen")).json()
    assert [e["id"] for e in alle] == [None, fid]
    assert {k: alle[1][k] for k in ("sprache", "original", "stand", "kapitel_fertig", "kapitel_gesamt", "fertig_gegen", "modell", "pruefmodell")} == {
        "sprache": "de", "original": False, "stand": "fertig", "kapitel_fertig": 4, "kapitel_gesamt": 4, "fertig_gegen": None,
        "modell": "qwen/qwen3-next-80b", "pruefmodell": "qwen/qwen3-coder-next"}
    assert (await client.get("/api/books/999/fassungen")).status_code == 404


async def test_folgen_vor_dem_start(client, test_db, uebersetzer):
    await begriffsliste.vorgaben_einspielen()                               # wie beim Start der App
    buch = await probebuch(test_db)
    f = (await client.get(f"/api/books/{buch}/fassungen/de/folgen")).json()
    b = await fassungen.buch(buch)
    assert {k: f[k] for k in ("seiten", "kapitel", "bloecke", "abbildungen", "tempo_s_je_seite", "geht", "grund")} == {
        "seiten": 1, "kapitel": 4, "bloecke": 25, "abbildungen": 2, "tempo_s_je_seite": 30.0, "geht": True, "grund": ""}
    woerter = sum(x.woerter for x in zerlegen(probe_epub(), fassungen.nie_klassen()).bloecke())
    assert f["dauer_s"] == round(woerter / settings.uebersetzen_woerter_je_seite * 30, 1) and f["fertig_gegen"].endswith("Z")
    assert f["ablage"] == {"ort": "geraet", "pfad": str(settings.storage_dir / b.hash[:2] / b.hash[2:4] / b.hash / "Fassungen" / "de" / "Garten.epub")}
    assert f["begriffe"] == 16                                       # Einheiten und Begriffe (AI) der Liste für alle
    assert f["anrede"] == "du"                                       # die Vorgabe für eine neue Fassung
    assert (await client.get(f"/api/books/{buch}/fassungen/fr/folgen")).status_code == 404     # nur Deutsch als Ziel


async def test_folgen_wenn_es_nicht_geht(client, test_db, uebersetzer, monkeypatch):
    deutsch = await probebuch(test_db, language="de")
    f = (await client.get(f"/api/books/{deutsch}/fassungen/de/folgen")).json()
    assert f["geht"] is False and f["grund"] == "Das Buch ist nicht englisch (Sprache: de)"
    r = await client.post(f"/api/books/{deutsch}/fassungen/de")
    assert r.status_code == 422 and r.json()["detail"] == "Das Buch ist nicht englisch (Sprache: de)"
    await test_db.execute("UPDATE books SET file_format = 'pdf', hash = 'anders' WHERE id = ?", (deutsch,))
    await test_db.commit()
    assert (await client.get(f"/api/books/{deutsch}/fassungen/de/folgen")).json()["grund"] == "Das Format PDF wird noch nicht übersetzt, bisher nur EPUB"
    ohne_angabe = await probebuch(test_db, language="", hash="ohneangabe")
    assert (await client.get(f"/api/books/{ohne_angabe}/fassungen/de/folgen")).json()["geht"] is False   # zu wenig Text, um englisch zu gelten
    monkeypatch.setattr(settings, "leitstelle_adresse", "")
    englisch = await probebuch(test_db, hash="englisch2")
    assert (await client.get(f"/api/books/{englisch}/fassungen/de/folgen")).json()["grund"].startswith("Keine Leitstelle")


# -- Lauf: Start, Stand, Pause, Fortsetzen, Abbrechen -------------------------------------------------------------------------

async def test_start_und_stand(client, test_db, uebersetzer):
    buch = await probebuch(test_db)
    r = await client.post(f"/api/books/{buch}/fassungen/de")
    assert r.status_code == 200
    s = r.json()
    assert s["stand"] == "laeuft" and [x["name"] for x in s["stationen"]] == STATIONEN and {x["stand"] for x in s["stationen"]} == {"wartet"}
    assert s["kapitel"] == [] and s["zahlen"] == {"bloecke": 0, "uebersetzt": 0, "bestanden": 0, "nachgearbeitet": 0, "offen": 0}
    fid = s["id"]
    assert (await client.post(f"/api/books/{buch}/fassungen/de")).json()["id"] == fid     # noch einmal: dieselbe Fassung
    await Uebersetzungslauf(ki).runde()
    s = (await client.get(f"/api/fassungen/{fid}/stand")).json()
    assert s["stand"] == "fertig" and s["begonnen"].endswith("Z") and s["bisher_s"] >= 0 and s["noch_s"] == 0 and s["fertig_gegen"] is None
    assert [(x["name"], x["stand"]) for x in s["stationen"]] == [(n, "fertig") for n in STATIONEN]
    assert s["stationen"][0]["text"] == "25 Blöcke in 4 Kapiteln" and s["stationen"][2]["text"] == "25 von 25 Blöcken"
    assert [(k["nr"], k["titel"], k["stand"], k["bloecke"], k["fertig"], k["geschaetzt"]) for k in s["kapitel"]] == [
        (2, "Getting Started", "fertig", 15, 15, False), (3, "Watering the Beds", "fertig", 5, 5, False),
        (4, "Inhaltsverzeichnis", "fertig", 3, 3, False), (5, "Inhaltsverzeichnis", "fertig", 2, 2, False)]
    assert s["zahlen"] == {"bloecke": 25, "uebersetzt": 25, "bestanden": 25, "nachgearbeitet": 0, "offen": 0}
    assert s["kapitel_jetzt"] is None and s["block_jetzt"] is None
    assert (await client.get("/api/fassungen/999/stand")).status_code == 404


async def test_anrede_je_buch_beim_start(client, test_db, uebersetzer, leitstelle):  # noqa: F811
    """Die Anrede gilt für die ganze Fassung: beim Start wählbar, in der Rückfrage und der Liste genannt, im Auftrag an die
    KI, und die feste Prüfung "Anrede" hält sie ein. Eine bestehende Fassung wechselt sie nicht."""
    buch = await probebuch(test_db)
    s = await client.post(f"/api/books/{buch}/fassungen/de", json={"anrede": "Sie"})
    assert s.status_code == 200
    fid = s.json()["id"]
    assert (await client.get(f"/api/books/{buch}/fassungen/de/folgen")).json()["anrede"] == "Sie"
    r = await client.post(f"/api/books/{buch}/fassungen/de", json={"anrede": "du"})
    assert r.status_code == 409 and "spricht den Leser mit Sie an" in r.json()["detail"]
    assert (await client.post(f"/api/books/{buch}/fassungen/de", json={})).status_code == 200
    assert (await client.post(f"/api/books/{buch}/fassungen/de", json={"anrede": "ihr"})).status_code == 422

    await Uebersetzungslauf(ki).runde()
    [_, eintrag] = (await client.get(f"/api/books/{buch}/fassungen")).json()
    assert eintrag["anrede"] == "Sie"
    systeme = [json.loads(r.content)["messages"][0]["content"] for r in leitstelle.anfragen if r.url.path == "/v1/chat/completions"]
    assert any('mit "Sie" an' in t for t in systeme) and not any('mit "du" an' in t for t in systeme)
    # der Satz mit du besteht die Prüfung Anrede nicht, auch nicht nach den Nacharbeiten
    [offen] = (await client.get(f"/api/fassungen/{fid}/bericht")).json()["offen"]
    assert offen["kennung"] == "2.3" and [b["art"] for b in offen["befunde"]] == ["anrede"]
    assert offen["befunde"][0]["text"] == 'Der Leser wird mit "Sie" angesprochen, hier steht "du"'


async def test_pause_fortsetzen_abbrechen(client, test_db, uebersetzer):
    buch = await probebuch(test_db)
    fid = (await client.post(f"/api/books/{buch}/fassungen/de")).json()["id"]
    assert (await client.post(f"/api/fassungen/{fid}/pause")).json()["stand"] == "pause"
    assert await Uebersetzungslauf(ki).runde() == 0                          # angehalten: keine Arbeit
    assert (await client.post(f"/api/fassungen/{fid}/fortsetzen")).json()["stand"] == "laeuft"
    s = (await client.post(f"/api/fassungen/{fid}/abbrechen")).json()
    assert s["stand"] == "teilweise"
    await Uebersetzungslauf(ki).runde()                                      # setzt nur: noch nichts zerlegt
    assert (await fassungen.holen(fid)).stand == "teilweise"
    assert (await client.post(f"/api/books/{buch}/fassungen/de")).json()["stand"] == "laeuft"  # Start setzt fort
    await Uebersetzungslauf(ki).runde()
    assert (await client.get(f"/api/fassungen/{fid}/stand")).json()["stand"] == "fertig"
    for weg in ("pause", "fortsetzen", "abbrechen"):
        assert (await client.post(f"/api/fassungen/{fid}/{weg}")).json()["stand"] == "fertig"  # fertig bleibt fertig
        assert (await client.post(f"/api/fassungen/999/{weg}")).status_code == 404


async def test_abbrechen_mitten_im_lauf_legt_das_fertige_ab(client, test_db, uebersetzer, monkeypatch):
    """Abgebrochen über die Schnittstelle, während eine Anfrage zu Kapitel 3 läuft: der Lauf hält sofort an, die Fassung
    bleibt teilweise, Fertiges steht deutsch in der abgelegten Datei, der Rest im Original mit Marke."""
    monkeypatch.setattr(settings, "uebersetzen_portion_bloecke", 5)
    buch = await probebuch(test_db)
    fid = (await client.post(f"/api/books/{buch}/fassungen/de")).json()["id"]
    abgebrochen = []

    def abbrechen_bei_kapitel_3(art, daten):
        if art == "uebersetzung" and daten["kapitel"] == "Watering the Beds" and not abgebrochen:
            abgebrochen.append(asyncio.get_running_loop().create_task(client.post(f"/api/fassungen/{fid}/abbrechen")))
            return True                                                   # die Anfrage bleibt ohne Antwort
        return False

    uebersetzer.unterbrechen = abbrechen_bei_kapitel_3
    await uebersetzungslauf.runde()
    assert (await abgebrochen[0]).json()["stand"] == "teilweise"
    await uebersetzungslauf.runde()                                          # legt ab, übersetzt nicht weiter
    f = await fassungen.holen(fid)
    assert f.stand == "teilweise" and f.datei_aktuell
    assert uebersetzer.gesendet().count("Watering the Beds") == 0
    s = (await client.get(f"/api/fassungen/{fid}/stand")).json()
    assert [(k["nr"], k["stand"]) for k in s["kapitel"]] == [(2, "fertig"), (3, "wartet"), (4, "wartet"), (5, "wartet")]
    assert s["kapitel"][1]["geschaetzt"] is True and s["kapitel"][1]["dauer_s"] > 0
    epub = dateien((await client.get(f"/api/fassungen/{fid}/datei")).content)
    assert "Erste Schritte" in epub["OEBPS/text/kapitel 1.xhtml"].decode()
    assert 'title="Im Original: noch nicht übersetzt"' in epub["OEBPS/text/kap2.xhtml"].decode()
    eintrag = (await client.get(f"/api/books/{buch}/fassungen")).json()[1]
    assert (eintrag["kapitel_fertig"], eintrag["kapitel_gesamt"]) == (1, 4)


async def test_pause_mitten_in_einer_anfrage(client, test_db, uebersetzer, monkeypatch):
    monkeypatch.setattr(settings, "uebersetzen_portion_bloecke", 5)
    buch = await probebuch(test_db)
    fid = (await client.post(f"/api/books/{buch}/fassungen/de")).json()["id"]
    pausiert = []

    def pause_bei_der_zweiten(art, daten):
        if art == "uebersetzung" and len(uebersetzer.gesendet()) == 5 and not pausiert:
            pausiert.append(asyncio.get_running_loop().create_task(client.post(f"/api/fassungen/{fid}/pause")))
            return True
        return False

    uebersetzer.unterbrechen = pause_bei_der_zweiten
    await uebersetzungslauf.runde()
    assert (await pausiert[0]).json()["stand"] == "pause"
    assert await uebersetzungslauf.runde() == 0                              # pausiert: keine Arbeit
    assert len(uebersetzer.gesendet()) == 5
    assert (await client.post(f"/api/fassungen/{fid}/fortsetzen")).json()["stand"] == "laeuft"
    await uebersetzungslauf.runde()
    assert (await fassungen.holen(fid)).stand == "fertig" and len(uebersetzer.gesendet()) == 23     # 25 Blöcke, zwei aus dem Speicher


# -- Bericht und Blöcke -------------------------------------------------------------------------------------------------------

async def test_bericht_und_bloecke_annehmen_setzen_neu(client, test_db, uebersetzer):
    falsch = "Eine kleine Maschine kann <t1>17.000</t1> Pflanzen in 1,5 Stunden gießen, das sind etwa 3 GB Protokolle.<x2/>"
    buch, fid = await fertig_uebersetzt(client, test_db, uebersetzer, **{ZAHL: falsch})
    bericht = (await client.get(f"/api/fassungen/{fid}/bericht")).json()
    assert [o["kennung"] for o in bericht["offen"]] == ["2.2"] and bericht["zahlen"]["offen"] == 1
    assert (await client.get("/api/fassungen/999/bericht")).status_code == 404

    # setzen: ein Text, der die Prüfungen nicht besteht, gibt 422 mit Befunden; einer, der besteht, gilt
    r = await client.post(f"/api/fassungen/{fid}/bloecke/2.2", json={"aktion": "setzen", "text": "Die Maschine gießt 17 Pflanzen."})
    assert r.status_code == 422 and r.json()["detail"].startswith("Der Text besteht die festen Prüfungen nicht")
    assert {b["art"] for b in r.json()["befunde"]} >= {"marken", "zahlen"}
    assert (await fassungen.block(fid, "2.2")).stand == "offen"                 # zurückgerollt, nichts halb geändert
    r = await client.post(f"/api/fassungen/{fid}/bloecke/2.2", json={"aktion": "setzen", "text": DEUTSCH[ZAHL].replace("etwa", "ungefähr")})
    assert r.status_code == 200 and r.json() == {"kennung": "2.2", "stand": "gesetzt", "deutsch": DEUTSCH[ZAHL].replace("etwa", "ungefähr"),
                                                 "befunde": []}
    assert (await client.get(f"/api/fassungen/{fid}/bericht")).json()["offen"] == []

    # annehmen nur bei offenen Stellen
    r = await client.post(f"/api/fassungen/{fid}/bloecke/2.1", json={"aktion": "annehmen"})
    assert r.status_code == 422 and r.json()["detail"] == "Annehmen geht nur bei offenen Stellen"
    await test_db.execute("UPDATE uebersetzung_block SET stand = 'offen' WHERE fassung_id = ? AND kennung = '2.1'", (fid,))
    await test_db.commit()
    r = await client.post(f"/api/fassungen/{fid}/bloecke/2.1", json={"aktion": "annehmen"})
    assert r.status_code == 200 and r.json()["stand"] == "angenommen"

    # neu: der Block wartet, die fertige Fassung läuft weiter und übersetzt ihn wieder
    r = await client.post(f"/api/fassungen/{fid}/bloecke/3.2", json={"aktion": "neu"})
    assert r.json() == {"kennung": "3.2", "stand": "wartet", "deutsch": "", "befunde": []}
    assert (await fassungen.holen(fid)).stand == "laeuft"
    await Uebersetzungslauf(ki).runde()
    assert (await fassungen.block(fid, "3.2")).stand == "bestanden" and (await fassungen.holen(fid)).stand == "fertig"
    datei = dateien((await client.get(f"/api/fassungen/{fid}/datei?herunterladen=true")).content)
    assert "ungefähr 3 GB Protokolle" in datei["OEBPS/text/kapitel 1.xhtml"].decode()

    # von Hand dürfen Zeichen roh stehen; fremde Auszeichnung nicht
    roh = "Rufe <x1/> auf, bevor du die <t2>Pumpe</t2> startest, & lies im <t3>nächsten Kapitel</t3> die Einzelheiten."
    r = await client.post(f"/api/fassungen/{fid}/bloecke/2.3", json={"aktion": "setzen", "text": roh})
    assert r.status_code == 200 and r.json()["deutsch"] == roh.replace("& lies", "&amp; lies")
    r = await client.post(f"/api/fassungen/{fid}/bloecke/2.3", json={"aktion": "setzen", "text": roh.replace("du die", "du <b>die</b>")})
    assert r.status_code == 422 and [b["art"] for b in r.json()["befunde"]] == ["marken"]

    assert (await client.post(f"/api/fassungen/{fid}/bloecke/9.9", json={"aktion": "neu"})).status_code == 404
    r = await client.post(f"/api/fassungen/{fid}/bloecke/2.2", json={"aktion": "setzen"})
    assert r.status_code == 422 and "Zum Setzen gehört ein Text" in r.json()["detail"]
    assert (await client.post(f"/api/fassungen/{fid}/bloecke/2.2", json={"aktion": "loeschen"})).status_code == 422


async def test_annehmen_braucht_vollstaendige_marken(client, test_db, uebersetzer):
    ohne_marke = "Eine kleine Maschine kann 16.000 Pflanzen in 1,5 Stunden gießen, das sind etwa 3 GB Protokolle."
    buch, fid = await fertig_uebersetzt(client, test_db, uebersetzer, **{ZAHL: ohne_marke})
    assert (await fassungen.block(fid, "2.2")).stand == "offen"
    r = await client.post(f"/api/fassungen/{fid}/bloecke/2.2", json={"aktion": "annehmen"})
    assert r.status_code == 422 and "bitte den Text von Hand setzen" in r.json()["detail"]


# -- Datei für den Leser ------------------------------------------------------------------------------------------------------

async def test_datei_auch_waehrend_des_laufs(client, test_db, uebersetzer, monkeypatch):
    buch = await probebuch(test_db)
    fid = (await client.post(f"/api/books/{buch}/fassungen/de")).json()["id"]
    r = await client.get(f"/api/fassungen/{fid}/datei")
    assert r.status_code == 409 and "noch nicht zerlegt" in r.json()["detail"]
    lauf = Uebersetzungslauf(ki)
    uebersetzer.unterbrechen = lambda art, daten: art == "pruefung" and lauf.halten(fid) is None
    await lauf.runde()
    r = await client.get(f"/api/fassungen/{fid}/datei")                     # frisch gesetzt aus den Blöcken
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("inline")
    k1 = dateien(r.content)["OEBPS/text/kapitel 1.xhtml"].decode()
    assert "Getting Started</span>" in k1 and 'lang="de"' in k1                # übersetzt, aber noch nicht geprüft: Original
    assert (await client.get("/api/fassungen/999/datei")).status_code == 404


# -- Begriffsliste ------------------------------------------------------------------------------------------------------------

async def test_begriffsliste_pflegen(client, test_db, uebersetzer):
    buch, fid = await fertig_uebersetzt(client, test_db, uebersetzer)
    allgemein = (await client.get("/api/begriffe")).json()
    assert ("feet", "Fuß", False, "vorgabe", "einheit") in [(b["englisch"], b["deutsch"], b["bleibt"], b["herkunft"], b["art"]) for b in allgemein]

    r = await client.post(f"/api/books/{buch}/begriffe", json={"englisch": "tank", "bleibt": True, "grund": "So im Garten üblich"})
    assert r.status_code == 201
    neu = r.json()
    assert {k: neu[k] for k in ("englisch", "deutsch", "bleibt", "herkunft", "stellen", "grund", "art")} == {
        "englisch": "tank", "deutsch": "", "bleibt": True, "herkunft": "hand", "stellen": 1, "grund": "So im Garten üblich", "art": "begriff"}
    assert (await fassungen.block(fid, "2.5")).stand == "wartet"               # "Fill the tank" wird neu übersetzt
    assert (await fassungen.block(fid, "2.6")).stand == "bestanden"            # die anderen bleiben
    assert (await fassungen.holen(fid)).stand == "laeuft"
    assert (await client.post(f"/api/books/{buch}/begriffe", json={"englisch": "Tank", "bleibt": True})).status_code == 409
    r = await client.post(f"/api/books/{buch}/begriffe", json={"englisch": "soil"})
    assert r.status_code == 422 and "bleibt englisch oder hat eine deutsche Form" in r.json()["detail"]

    uebersetzer.tabelle["Fill the tank"] = "Fülle den Tank"
    await Uebersetzungslauf(ki).runde()
    assert (await fassungen.block(fid, "2.5")).stand == "bestanden"

    r = await client.patch(f"/api/begriffe/{neu['id']}", json={"bleibt": False, "deutsch": "Behälter"})
    assert r.status_code == 200 and (r.json()["deutsch"], r.json()["bleibt"], r.json()["herkunft"]) == ("Behälter", False, "hand")
    assert (await fassungen.block(fid, "2.5")).stand == "wartet"
    assert (await client.patch(f"/api/begriffe/{neu['id']}", json={"bleibt": False, "deutsch": ""})).status_code == 422
    assert (await client.patch("/api/begriffe/999", json={"bleibt": True})).status_code == 404

    pumpe = next(b for b in (await client.get(f"/api/books/{buch}/begriffe")).json() if b["englisch"] == "pump")
    assert (await client.delete(f"/api/begriffe/{pumpe['id']}")).json() == {"geloescht": True, "id": pumpe["id"]}
    assert (await fassungen.block(fid, "2.3")).stand == "wartet"               # "the pump" wird neu übersetzt
    assert (await client.delete(f"/api/begriffe/{pumpe['id']}")).status_code == 404
    assert [b["englisch"] for b in (await client.get(f"/api/books/{buch}/begriffe")).json()] == ["tank"]
    assert (await client.get("/api/books/999/begriffe")).status_code == 404


async def test_begriff_fuer_alle_buecher(client, test_db, uebersetzer):
    buch, fid = await fertig_uebersetzt(client, test_db, uebersetzer)
    r = await client.post("/api/begriffe", json={"englisch": "bed", "deutsch": "Beet", "grund": "Im Garten"})
    assert r.status_code == 201 and r.json()["herkunft"] == "hand" and r.json()["stellen"] == 0
    assert (await fassungen.block(fid, "3.3")).stand == "wartet"               # "Bed" in diesem Buch
    eigener = await client.post(f"/api/books/{buch}/begriffe", json={"englisch": "beds", "bleibt": True})
    assert eigener.status_code == 201
    assert "bed" in [b["englisch"] for b in (await client.get("/api/begriffe")).json()]
