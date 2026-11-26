"""Der Lauf der Übersetzung gegen eine Attrappe der Leitstelle (BF-71): ganze Kette für das Probe-EPUB, falsche Anzahl
(Halbieren), fehlende Marke, geänderte Zahl, englischer Satz und Mangel des Prüfers mit Bestätigung (Nacharbeit, Verbleib im
Original mit Bericht), doppelte Marke (Reparatur), Zwischenspeicher, Fortsetzen nach einem Neustart mitten im Kapitel, Ablage
in der Kellerwolke."""

import asyncio
import json
from collections import Counter

import httpx

from backend.app.ablage.wolke import Wolke
from backend.app.core.config import settings
from backend.app.services import fassungen
from backend.app.services.fassungen import NICHT_BESTANDEN
from backend.app.services.ki import ki
from backend.app.services.uebersetzungslauf import Uebersetzungslauf
from backend.app.uebersetzung.marken import fuer_modell
from backend.app.uebersetzung.modelle import Befund
from tests.api.test_ausfuehren import leitstelle  # noqa: F401 - Attrappe der Leitstelle
from tests.api.uebersetzer import DEUTSCH, abgelegt, orte, probebuch, uebersetzer  # noqa: F401 - Fixtures
from tests.uebersetzung_probe import dateien

KAPITEL1 = "OEBPS/text/kapitel 1.xhtml"
ZAHL = "A small machine can water <t1>16,000</t1> plants in 1.5 hours, which is about 3 GB of logs.<x2/>"
FALSCHE_ZAHL = "Eine kleine Maschine kann <t1>17.000</t1> Pflanzen in 1,5 Stunden gießen, das sind etwa 3 GB Protokolle.<x2/>"
MARKE = "Check the <t1>filter <t2>twice</t2></t1> a week."
ENGLISCH = "A garden at dawn."
MANGEL = "A raised box of soil."


async def starten(client, buch: int) -> int:
    r = await client.post(f"/api/books/{buch}/fassungen/de")
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def test_ganze_kette_mit_halbieren_nacharbeit_und_bericht(client, test_db, uebersetzer, leitstelle):  # noqa: F811
    u = uebersetzer
    u.kaputt.add("uebersetzung")                                        # die erste Antwort hat einen Text zu wenig
    u.tabelle[ZAHL] = FALSCHE_ZAHL                                      # bleibt falsch, auch in beiden Nacharbeiten
    u.tabelle[MARKE] = "Prüfe den <t1>Filter</t1> zweimal pro Woche."   # eine Marke fehlt; die Nacharbeit bringt sie
    u.nacharbeit[MARKE] = [DEUTSCH[MARKE]]
    u.tabelle[ENGLISCH] = ENGLISCH                                      # unübersetzt; die Nacharbeit übersetzt
    u.nacharbeit[ENGLISCH] = [DEUTSCH[ENGLISCH]]
    u.maengel[DEUTSCH[MANGEL]] = {"in_ordnung": False, "art": "sinn", "grund": "Der Kasten ist nicht erhöht", "stelle": "erhöhter"}
    buch = await probebuch(test_db)
    fid = await starten(client, buch)

    lauf = Uebersetzungslauf(ki)
    assert await lauf.runde() == 1
    f = await fassungen.holen(fid)
    assert f.stand == "fertig" and f.modell == "qwen/qwen3-next-80b" and f.pruefmodell == "qwen/qwen3-coder-next" and f.datei_aktuell

    zeilen = {z.kennung: z for z in await fassungen.bloecke(fid)}
    assert len(zeilen) == 25
    assert (zeilen["2.2"].stand, zeilen["2.2"].nacharbeiten, zeilen["2.2"].versuche) == ("offen", 2, 3)
    assert [(b.art, b.quelle) for b in zeilen["2.2"].befunde] == [("zahlen", "pruefung"), ("antwort", "pruefung")]
    assert zeilen["2.2"].befunde[1].text == "Die Nacharbeit kam unverändert zurück; die Mängel bestehen weiter"
    assert (zeilen["2.8"].stand, zeilen["2.8"].nacharbeiten, zeilen["2.8"].uebersetzung) == ("nachgearbeitet", 1, DEUTSCH[MARKE])
    assert (zeilen["2.13"].stand, zeilen["2.13"].uebersetzung) == ("nachgearbeitet", DEUTSCH[ENGLISCH])
    assert (zeilen["3.4"].stand, zeilen["3.4"].nacharbeiten, zeilen["3.4"].geprueft) == ("nachgearbeitet", 1, True)
    assert Counter(z.stand for z in zeilen.values()) == {"bestanden": 21, "nachgearbeitet": 3, "offen": 1}

    # falsche Anzahl: die erste Portion (das ganze Kapitel) wird halbiert
    anfragen = [d["bloecke"] for a, d in u.beantwortet if a == "uebersetzung"]
    assert len(anfragen[0]) == 15 and len(anfragen[1]) == 7 and len(anfragen[2]) == 8
    # Prüfer und Bestätigung mit dem zweiten Modell, Übersetzen mit dem, das gilt; alles im Hintergrund
    assert {m for a, m in u.modelle if a in ("pruefung", "bestaetigung")} == {"qwen/qwen3-coder-next"}
    assert {m for a, m in u.modelle if a not in ("pruefung", "bestaetigung")} == {"qwen/qwen3-next-80b"}
    # der Einwand ging vor der Nacharbeit an die zweite Prüfung: Original, Übersetzung, Art und Stelle, nicht der Grund
    [bestaetigung] = [d for a, d in u.beantwortet if a == "bestaetigung"]
    assert bestaetigung["faelle"] == [{"original": MANGEL, "deutsch": DEUTSCH[MANGEL], "art": "sinn", "stelle": "erhöhter"}]
    assert (zeilen["3.4"].befunde, zeilen["3.4"].reparaturen) == ([], [])
    chats = [r for r in leitstelle.anfragen if r.url.path == "/v1/chat/completions"]
    assert chats and all(r.headers.get("X-Leitstelle-Prioritaet") == "hintergrund" for r in chats)
    # Nacharbeit mit dem Grund im Auftrag
    nacharbeit = [d for a, d in u.beantwortet if a == "nacharbeit" and d["bloecke"] == [MANGEL]][0]
    assert nacharbeit["beanstandet"] == {"uebersetzung": DEUTSCH[MANGEL], "maengel": ["Der Kasten ist nicht erhöht (Stelle: erhöhter)"]}
    assert Counter(v for v in u.gesendet("nacharbeit")) == {ZAHL: 2, MARKE: 1, ENGLISCH: 1, MANGEL: 1}
    # unverändert englisch zurück: gleich einzeln mit der Anweisung dafür, in der Nacharbeit ohne die Kopie als frühere Übersetzung
    einzeln = [json.loads(r.content) for r in chats if json.loads(json.loads(r.content)["messages"][1]["content"]).get("bloecke") == [ENGLISCH]]
    assert [k["response_format"]["json_schema"]["name"] for k in einzeln] == ["uebersetzung", "nacharbeit"]
    assert all("unverändert englisch zurück" in k["messages"][0]["content"] for k in einzeln)
    assert "uebersetzung" not in json.loads(einzeln[1]["messages"][1]["content"])["beanstandet"]

    # Begriffe: Regel und KI; was nicht im Buch steht, kam nicht in die Liste
    begriffe = (await client.get(f"/api/books/{buch}/begriffe")).json()
    assert [(b["englisch"], b["deutsch"], b["bleibt"], b["herkunft"], b["stellen"], b["fragwuerdig"]) for b in begriffe] == [
        ("pump", "Pumpe | pump", False, "ki", 1, "")]                       # das englische Wort ist als zweite Form erlaubt
    assert u.beantwortet[0][0] == "begriffe" and u.beantwortet[0][1]["verzeichnis"] == [
        "Getting Started", "Watering the Beds", "Inhaltsverzeichnis", "Inhaltsverzeichnis"]

    # Bericht: die offene Stelle mit Original, Übersetzung und Befund
    bericht = (await client.get(f"/api/fassungen/{fid}/bericht")).json()
    assert bericht["zahlen"] == {"bloecke": 25, "uebersetzt": 24, "bestanden": 21, "nachgearbeitet": 3, "offen": 1, "verworfen": 0,
                                 "repariert": 0}
    assert bericht["begriffe_fragwuerdig"] == [] and bericht["repariert"] == []
    [offen] = bericht["offen"]
    assert {k: offen[k] for k in ("kennung", "kapitel", "ort", "seite_original", "original", "deutsch")} == {
        "kennung": "2.2", "kapitel": 2, "ort": "Getting Started, Absatz 2", "seite_original": None, "original": ZAHL, "deutsch": FALSCHE_ZAHL}
    assert offen["befunde"][0]["art"] == "zahlen" and "16,000" in offen["befunde"][0]["text"] and offen["befunde"][0]["stelle"] == "17.000"

    # Ablage auf dem Gerät neben dem Original, das Original bleibt
    b = await fassungen.buch(buch)
    datei = abgelegt(b.hash)
    assert f.datei == str(datei) and datei.is_file()
    epub = dateien(datei.read_bytes())
    k1 = epub[KAPITEL1].decode()
    assert '<h1 id="h1">Erste Schritte</h1>' in k1 and "<li><p>Prüfe den <b>Filter <i>zweimal</i></b> pro Woche.</p></li>" in k1
    assert f'<span class="bf-original" lang="en" xml:lang="en" title="{NICHT_BESTANDEN}"' in k1 and "16,000" in k1
    assert "Übersetzt mit qwen/qwen3-next-80b, geprüft mit qwen/qwen3-coder-next" in epub["OEBPS/bf-uebersetzung.xhtml"].decode()
    assert "<navLabel><text>Erste Schritte</text></navLabel>" in epub["OEBPS/toc.ncx"].decode()
    assert sorted(p.name for p in (datei.parents[2]).iterdir()) == ["Fassungen", "Garten.epub"]

    # der Leser bekommt die abgelegte Datei
    r = await client.get(f"/api/fassungen/{fid}/datei")
    assert r.status_code == 200 and r.headers["content-type"] == "application/epub+zip" and r.content == datei.read_bytes()
    assert await lauf.runde() == 0                                       # nichts mehr zu tun


async def _block_aendern(test_db, fid: int, kennung: str, **spalten) -> None:
    if "befunde" in spalten:
        spalten["befunde"] = json.dumps([b.model_dump() for b in spalten["befunde"]], ensure_ascii=False)
    gesetzt = ", ".join(f"{k} = ?" for k in spalten)
    await test_db.execute(f"UPDATE uebersetzung_block SET {gesetzt} WHERE fassung_id = ? AND kennung = ?", (*spalten.values(), fid, kennung))


async def test_geaenderte_pruefungen_pruefen_neu_ohne_neu_zu_uebersetzen(client, test_db, uebersetzer):
    """Eine fertige Fassung, geprüft mit einer älteren Fassung der Prüfungen: der nächste Durchgang prüft alles der KI noch
    einmal fest. Was besteht, bleibt; was neu durchfällt (hier die Anrede), geht mit vollen Nacharbeiten in die Nacharbeit;
    eine offene Stelle, die nur an den festen Prüfungen oder an einem nie bestätigten Einwand scheiterte, geht zum Prüfer;
    ein bestätigter Mangel des Prüfers bleibt offen; Texte des Nutzers bleiben, wie sie sind. Übersetzt wird nichts neu."""
    u = uebersetzer
    buch = await probebuch(test_db)
    fid = await starten(client, buch)
    await Uebersetzungslauf(ki).runde()
    assert (await fassungen.holen(fid)).geprueft_mit == fassungen.geprueft_mit()

    sie = "Rufe <x1/> auf, bevor Sie die <t2>Pumpe</t2> starten, &amp; lies im <t3>nächsten Kapitel</t3> die Einzelheiten."
    await _block_aendern(test_db, fid, "2.3", uebersetzung=sie, nacharbeiten=2)
    await _block_aendern(test_db, fid, "3.2", stand="offen", nacharbeiten=2, versuche=3,
                         befunde=[Befund(art="marken", quelle="pruefung", text="Fremde Auszeichnung im Text", stelle="<")])
    await _block_aendern(test_db, fid, "3.4", stand="offen", nacharbeiten=2, versuche=3,
                         befunde=[Befund(art="sinn", quelle="ki", text="Der Kasten ist nicht erhöht", stelle="erhöhter",
                                         bestaetigung="Das Original sagt raised")])
    await _block_aendern(test_db, fid, "3.3", stand="offen", nacharbeiten=2, versuche=3,                     # nie bestätigt: geht zum Prüfer
                         befunde=[Befund(art="sinn", quelle="ki", text="Ein Beet ist kein Feld", stelle="Beet")])
    von_hand = "Hier sehen Sie einen Garten im Morgengrauen."
    await _block_aendern(test_db, fid, "2.13", stand="gesetzt", uebersetzung=von_hand)
    await test_db.execute("UPDATE fassung SET geprueft_mit = '1:0.8:1.8:60' WHERE id = ?", (fid,))
    await test_db.commit()

    assert (await client.post(f"/api/books/{buch}/fassungen/de")).json()["stand"] == "laeuft"   # fertig, aber neu zu prüfen
    vorher = len(u.beantwortet)
    await Uebersetzungslauf(ki).runde()

    f = await fassungen.holen(fid)
    assert f.stand == "fertig" and f.geprueft_mit == fassungen.geprueft_mit()
    zeilen = {z.kennung: z for z in await fassungen.bloecke(fid)}
    assert (zeilen["2.3"].stand, zeilen["2.3"].nacharbeiten) == ("nachgearbeitet", 1) and " du " in zeilen["2.3"].uebersetzung
    assert (zeilen["3.2"].stand, zeilen["3.2"].befunde, zeilen["3.2"].geprueft) == ("nachgearbeitet", [], True)
    assert zeilen["3.4"].stand == "offen" and zeilen["3.4"].befunde[0].quelle == "ki"
    assert (zeilen["3.3"].stand, zeilen["3.3"].befunde, zeilen["3.3"].geprueft) == ("nachgearbeitet", [], True)
    assert (zeilen["3.3"].nacharbeiten, zeilen["3.2"].nacharbeiten) == (0, 0)        # zurück beim Prüfer mit vollen Nacharbeiten
    assert (zeilen["2.13"].stand, zeilen["2.13"].uebersetzung) == ("gesetzt", von_hand)
    assert zeilen["2.1"].stand == "bestanden"
    neu = u.beantwortet[vorher:]
    assert [a for a, _ in neu if a != "pruefung"] == ["nacharbeit"]                              # nichts neu übersetzt
    assert neu[0][1]["beanstandet"]["maengel"] == ['Der Leser wird mit "du" angesprochen, hier steht "Sie" (Stelle: bevor Sie)']
    assert sorted(p["deutsch"] for _, d in neu if _ == "pruefung" for p in d["paare"]) == sorted(
        [DEUTSCH["Call <x1/> before you start the <t2>pump</t2> & check the <t3>next chapter</t3> for details."], DEUTSCH["Water early, water deep."],
         DEUTSCH["Bed"]])
    assert (await fassungen.holen(fid)).pruefer_verworfen == 0          # der nie bestätigte Einwand ist nicht verworfen, er ging neu zum Prüfer


async def test_geaenderte_regeln_kennzeichnen_fragwuerdige_begriffe_und_verwerfen_einwaende(client, test_db, uebersetzer):
    """Beim Neuprüfen nach geänderten Regeln: Einträge von Regel und KI, die die Regeln von heute nicht bestehen, werden
    fragwürdig (mit Grund, in Liste und Bericht) und gelten nicht, gelöscht wird nichts; Einträge von Hand bleiben, wie sie
    sind. Eine offene Stelle, die nur an einem Einwand des Prüfers über Begriffe scheiterte, geht wieder zum Prüfer; Einwände
    anderer Art werden verworfen und gezählt."""
    u = uebersetzer
    buch = await probebuch(test_db)
    fid = await starten(client, buch)
    await Uebersetzungslauf(ki).runde()
    await test_db.execute_many("INSERT INTO begriff (buch_id, englisch, deutsch, bleibt, herkunft, grund) VALUES (?, ?, ?, ?, ?, ?)", [
        (buch, "Watering", "", 1, "regel", "Name"),                               # groß nur in Überschrift und Verzeichnis
        (buch, "beds", "Beete", 0, "ki", "üblich"),                               # steht nur in Überschriften: kein Begriff
        (buch, "tank", "", 1, "hand", "so gewollt"),                              # von Hand: fasst keine Regel an
    ])
    await _block_aendern(test_db, fid, "3.2", stand="offen", nacharbeiten=2, versuche=3,
                         befunde=[Befund(art="begriff", quelle="ki", text="Water muss laut Begriffsliste englisch bleiben")])
    await test_db.execute("UPDATE fassung SET geprueft_mit = '2:0.8:1.8:60' WHERE id = ?", (fid,))
    await test_db.commit()
    u.maengel[DEUTSCH["Water early, water deep."]] = {"in_ordnung": False, "art": "anderes", "grund": "gießen schreibt man groß",
                                                      "stelle": "gießen"}

    assert (await client.post(f"/api/books/{buch}/fassungen/de")).json()["stand"] == "laeuft"
    vorher = len(u.beantwortet)
    await Uebersetzungslauf(ki).runde()

    begriffe = {b["englisch"]: b for b in (await client.get(f"/api/books/{buch}/begriffe")).json()}
    assert begriffe["Watering"]["fragwuerdig"] == "Kein Name nach der Regel: im Fließtext nicht oft genug mitten im Satz groß"
    assert begriffe["beds"]["fragwuerdig"] == "Überschrift statt Fachbegriff: steht nur in Überschriften und Titelzeilen"
    assert begriffe["tank"]["fragwuerdig"] == "" and begriffe["pump"]["fragwuerdig"] == ""
    zeilen = {z.kennung: z for z in await fassungen.bloecke(fid)}
    assert (zeilen["3.2"].stand, zeilen["3.2"].befunde, zeilen["3.2"].geprueft) == ("nachgearbeitet", [], True)
    assert {z.stand for z in zeilen.values()} == {"bestanden", "nachgearbeitet"}             # die fragwürdigen galten nicht
    assert [a for a, _ in u.beantwortet[vorher:]] == ["pruefung"]                             # nichts neu übersetzt
    bericht = (await client.get(f"/api/fassungen/{fid}/bericht")).json()
    assert bericht["zahlen"]["verworfen"] == 2                                               # der alte Einwand und der neue
    assert [b["englisch"] for b in bericht["begriffe_fragwuerdig"]] == ["beds", "Watering"]
    assert (await fassungen.holen(fid)).stand == "fertig"


async def test_mehrfachpruefung_verwirft_nicht_bestaetigte_einwaende(client, test_db, uebersetzer):
    """Ein Einwand des Prüfers, den die zweite Prüfung nicht bestätigt, schickt nichts zur Nacharbeit: der Block besteht, der
    Einwand wird verworfen und gezählt. Ein Einwand "englisch" gegen einen Begriff, der englisch bleibt, braucht keine
    zweite Anfrage."""
    u = uebersetzer
    u.maengel[DEUTSCH[MANGEL]] = {"in_ordnung": False, "art": "sinn", "grund": "erhöht heißt hoch", "stelle": "erhöhter"}
    u.unbestaetigt.add(DEUTSCH[MANGEL])
    pumpe = DEUTSCH["Call <x1/> before you start the <t2>pump</t2> & check the <t3>next chapter</t3> for details."]
    u.maengel[pumpe] = {"in_ordnung": False, "art": "englisch", "grund": "Pumpe ist englisch", "stelle": "Pumpe"}
    buch = await probebuch(test_db)
    fid = await starten(client, buch)
    await Uebersetzungslauf(ki).runde()

    zeilen = {z.kennung: z for z in await fassungen.bloecke(fid)}
    assert (zeilen["3.4"].stand, zeilen["3.4"].befunde, zeilen["3.4"].nacharbeiten) == ("bestanden", [], 0)
    assert (zeilen["2.3"].stand, zeilen["2.3"].nacharbeiten) == ("bestanden", 0)
    assert u.gesendet("nacharbeit") == []
    assert [f["deutsch"] for a, d in u.beantwortet if a == "bestaetigung" for f in d["faelle"]] == [DEUTSCH[MANGEL]]
    assert (await client.get(f"/api/fassungen/{fid}/bericht")).json()["zahlen"]["verworfen"] == 2


async def test_doppelte_marke_wird_repariert_und_steht_im_bericht(client, test_db, uebersetzer):
    """Eine Antwort, die eine Auszeichnungsmarke doppelt setzt, wird vor den Prüfungen verlustfrei berichtigt: die Stelle, die
    zum Original passt, behält die Marke, die andere nur den Text. Der Block besteht ohne Nacharbeit, die Reparatur steht am
    Block und im Bericht; nichts geschieht still."""
    u = uebersetzer
    doppelt = "Prüfe den <t1>Filter <t2>zweimal</t2></t1> pro Woche, den <t1>Filter</t1> genau."
    u.tabelle[MARKE] = doppelt
    buch = await probebuch(test_db)
    fid = await starten(client, buch)
    await Uebersetzungslauf(ki).runde()

    z = await fassungen.block(fid, "2.8")
    assert (z.stand, z.nacharbeiten, z.uebersetzung) == ("bestanden", 0, "Prüfe den <t1>Filter <t2>zweimal</t2></t1> pro Woche, den Filter genau.")
    assert [(r.art, r.stelle) for r in z.reparaturen] == [("marken", "Filter")] and "doppelt" in z.reparaturen[0].text
    assert MARKE not in u.gesendet("nacharbeit")
    bericht = (await client.get(f"/api/fassungen/{fid}/bericht")).json()
    assert bericht["zahlen"]["repariert"] == 1 and bericht["offen"] == []
    [stelle] = bericht["repariert"]
    assert {k: stelle[k] for k in ("kennung", "ort", "original", "deutsch")} == {
        "kennung": "2.8", "ort": "Getting Started, Listenpunkt 8", "original": MARKE, "deutsch": z.uebersetzung}
    assert stelle["reparaturen"] == [r.model_dump() for r in z.reparaturen]

    await client.post(f"/api/fassungen/{fid}/bloecke/2.8", json={"aktion": "neu"})            # neu übersetzen nimmt sie weg
    assert (await fassungen.block(fid, "2.8")).reparaturen == []


async def test_zwischenspeicher_uebersetzt_wiederkehrendes_einmal(client, test_db, uebersetzer):
    buch = await probebuch(test_db)
    await starten(client, buch)
    await Uebersetzungslauf(ki).runde()
    gesendet = uebersetzer.gesendet()
    assert gesendet.count("Getting Started") == 1 and gesendet.count("Watering the Beds") == 1      # NCX aus dem Speicher
    assert Counter(gesendet).most_common(1)[0][1] == 1


async def test_fortsetzen_nach_neustart_mitten_im_kapitel(client, test_db, uebersetzer, monkeypatch):
    """Der Lauf hält mitten in Kapitel 2 an (Herunterfahren während einer Anfrage); ein neuer Lauf setzt am ersten offenen
    Block fort. Jeder Block geht genau einmal in einer beantworteten Anfrage hinaus, keiner geht verloren."""
    monkeypatch.setattr(settings, "uebersetzen_portion_bloecke", 3)
    buch = await probebuch(test_db)
    fid = await starten(client, buch)
    erster = Uebersetzungslauf(ki)
    gezaehlt = {"n": 0}

    def unterbrechen(art: str, daten: dict) -> bool:
        if art != "uebersetzung":
            return False
        gezaehlt["n"] += 1
        if gezaehlt["n"] == 3:                                         # die dritte Portion: Herunterfahren mitten in der Anfrage
            asyncio.get_running_loop().create_task(erster.stoppen())
            return True
        return False

    uebersetzer.unterbrechen = unterbrechen
    await erster.runde()
    f = await fassungen.holen(fid)
    assert f.stand == "laeuft"                                         # bleibt laufend, wird nach dem Neustart aufgenommen
    staende = Counter(z.stand for z in await fassungen.bloecke(fid, 2))
    assert staende == {"uebersetzt": 6, "wartet": 9}

    uebersetzer.unterbrechen = lambda art, daten: False
    await Uebersetzungslauf(ki).runde()
    f = await fassungen.holen(fid)
    assert f.stand == "fertig"
    zeilen = await fassungen.bloecke(fid)
    assert {z.stand for z in zeilen} == {"bestanden"}
    gesendet = Counter(uebersetzer.gesendet())
    assert set(gesendet) == {fuer_modell(z.vorlage) for z in zeilen} and set(gesendet.values()) == {1}   # keine doppelt, keine verloren


async def test_ablage_in_der_kellerwolke_neben_dem_original(client, test_db, uebersetzer, monkeypatch):
    rufe: list[tuple[str, str, dict]] = []
    hochgeladen: list[bytes] = []

    async def rufe_auf(_s, art, weg, **weiter):
        if "content" in weiter:
            hochgeladen.append(b"".join([s async for s in weiter["content"]]))
        rufe.append((art, weg, {k: v for k, v in (weiter.get("headers") or {}).items() if k.startswith("If")} | dict(weiter.get("params") or {})))
        if weg == "/api/v1/ablage/ordner":
            return {"id": "ordner1"}
        if weg == "/api/v1/ablage/datei":
            return {"id": "k9", "etag": "e1", "name": "Garten [1].epub"}
        if weg == "/api/v1/ablage/knoten/k9":
            return {"id": "k9", "etag": "e1"}
        return {"id": "k9", "etag": "e2"}

    monkeypatch.setattr(Wolke, "bereit", property(lambda _s: True))
    monkeypatch.setattr(Wolke, "rufe", rufe_auf)
    buch = await probebuch(test_db)
    b = await fassungen.buch(buch)
    await test_db.execute("INSERT INTO ablage_datei (hash, knoten, name, pfad, groesse) VALUES (?, 'k1', 'Garten [1].epub', "
                          "'Apps/BücherFreunde/Bücher/G/Garten [1].epub', 100)", (b.hash,))
    await test_db.commit()
    folgen = (await client.get(f"/api/books/{buch}/fassungen/de/folgen")).json()
    assert folgen["ablage"] == {"ort": "kellerwolke", "pfad": "Apps/BücherFreunde/Bücher/G/Fassungen/de/Garten [1].epub"}
    fid = await starten(client, buch)
    await Uebersetzungslauf(ki).runde()
    f = await fassungen.holen(fid)
    assert (f.stand, f.datei, f.knoten) == ("fertig", "Apps/BücherFreunde/Bücher/G/Fassungen/de/Garten [1].epub", "k9")
    assert rufe == [("POST", "/api/v1/ablage/ordner", {}),
                    ("PUT", "/api/v1/ablage/datei", {"If-None-Match": "*", "pfad": "Apps/BücherFreunde/Bücher/G/Fassungen/de/Garten [1].epub"})]
    assert dateien(hochgeladen[0])["OEBPS/text/kap2.xhtml"].count(b"Die Beete gie") == 1

    # ein Block von Hand: neu gesetzt, als neue Version auf den gelesenen Stand
    r = await client.post(f"/api/fassungen/{fid}/bloecke/3.2", json={"aktion": "setzen", "text": "Früh gießen und tief gießen."})
    assert r.status_code == 200, r.text
    await Uebersetzungslauf(ki).runde()
    assert rufe[2:] == [("GET", "/api/v1/ablage/knoten/k9", {}), ("PUT", "/api/v1/ablage/knoten/k9/inhalt", {"If-Match": '"e1"'})]
    assert b"Fr\xc3\xbch gie\xc3\x9fen und tief gie\xc3\x9fen." in dateien(hochgeladen[1])["OEBPS/text/kap2.xhtml"]
    assert not list((settings.zwischen_dir / "fassungen").iterdir())                # nichts bleibt im Zwischenspeicher

    # die Löschfolgen nennen die Fassung, und sie geht mit in den Papierkorb
    folgen = (await client.get(f"/api/books/{buch}/loeschfolgen")).json()
    assert folgen["fassungen"] == [{"pfad": "Apps/BücherFreunde/Bücher/G/Fassungen/de/Garten [1].epub", "groesse": 0, "papierkorb": True}]
    assert (await client.delete(f"/api/books/{buch}")).status_code == 200
    assert [w for a, w, _ in rufe if a == "DELETE"] == ["/api/v1/ablage/knoten/k1", "/api/v1/ablage/knoten/k9"]


async def test_leitstelle_lehnt_ab_die_fassung_steht_auf_fehler(client, test_db, uebersetzer, leitstelle):  # noqa: F811
    buch = await probebuch(test_db)
    fid = await starten(client, buch)
    leitstelle.antwort = lambda r: (uebersetzer._modelle(r) if r.url.path == "/v1/models"
                                    else httpx.Response(429, json={"error": {"code": "gesperrt", "message": "von Hand gesperrt"}}))
    await Uebersetzungslauf(ki).runde()
    f = await fassungen.holen(fid)
    assert f.stand == "fehler" and "gesperrt" in f.grund
    stand = (await client.post(f"/api/fassungen/{fid}/fortsetzen")).json()
    assert stand["stand"] == "laeuft" and stand["grund"] == ""


async def test_ohne_brauchbare_vorschlaege_der_ki_geht_es_ohne_sie_weiter(client, test_db, uebersetzer):
    uebersetzer.vorschlag = {"etwas": "anderes"}
    buch = await probebuch(test_db)
    fid = await starten(client, buch)
    await Uebersetzungslauf(ki).runde()
    stand = (await client.get(f"/api/fassungen/{fid}/stand")).json()
    assert stand["stand"] == "fertig"
    assert stand["stationen"][1] == {"name": "Begriffe", "stand": "fertig",
                                     "text": "0 nach Regeln; ohne Vorschlag der KI: Die Antwort der KI passt nicht zur verlangten Form"}


async def test_ohne_angebotenes_zweites_modell_prueft_dasselbe(client, test_db, uebersetzer, monkeypatch):
    monkeypatch.setattr(settings, "uebersetzen_pruefmodell", "anbieter/gibt-es-nicht")
    buch = await probebuch(test_db)
    fid = await starten(client, buch)
    await Uebersetzungslauf(ki).runde()
    f = await fassungen.holen(fid)
    assert (f.stand, f.modell, f.pruefmodell) == ("fertig", "qwen/qwen3-next-80b", "qwen/qwen3-next-80b")
    assert {m for _, m in uebersetzer.modelle} == {"qwen/qwen3-next-80b"}
