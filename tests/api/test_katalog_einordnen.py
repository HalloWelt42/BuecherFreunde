"""Einordnen in den Katalog (BF-69): Lauf in Stapeln ohne KI und mit einer Attrappe der Leitstelle, unbrauchbare Antworten,
unbekannte Schlüssel, Pause und Fortsetzen, Neustart, Vorschläge annehmen und ablehnen, die Arten der Bereiche, alte Regale
und neue Kategorien aus dem Bestand. Alle Werke und Regale sind erfunden."""

import asyncio
import json
import re
from urllib.parse import unquote

import httpx
import pytest

from backend.app.core.config import settings
from backend.app.katalog.alt import NICHT_GEPRUEFT
from backend.app.katalog.bestandslauf import bestandslauf
from backend.app.katalog.einordnen import OHNE_KI, einordner
from tests.api.katalog_hilfen import katalog_annehmen, nummern, regal, werk
from tests.api.test_ausfuehren import chat_antwort, leitstelle  # noqa: F401 - Attrappe der Leitstelle

ZEILE = re.compile(r"^(\d+)\. (?:Titel: )?(.*?)(?: \| |$)", re.M)


def frage(r: httpx.Request) -> str:
    return unquote(r.headers["X-Leitstelle-Titel"]).split(": ", 1)[1]


def nutzertext(r: httpx.Request) -> str:
    return json.loads(r.content)["messages"][1]["content"]


@pytest.fixture(autouse=True)
async def laeufe_aufraeumen():
    yield
    await einordner.stoppen()
    await bestandslauf.stoppen()


@pytest.fixture
def ohne_ki(monkeypatch):
    monkeypatch.setattr(settings, "leitstelle_adresse", "")


@pytest.fixture
def ki_sagt(leitstelle, monkeypatch):  # noqa: F811
    """Die Leitstelle ohne Pausen. `buecher`: je Titel, was die KI vorschlägt [(schluessel, sicherheit, satz)]; `regale`: je
    Name eines alten Regals (schluessel, satz); `neu`: die neuen Kategorien; `sonst`: je Anfang einer Frage eine feste
    Antwort (Daten, Text oder httpx.Response); `halt`: wartet die Einordnen-Antwort auf ein Ereignis."""
    monkeypatch.setattr(settings, "katalog_abstand_s", 0)
    modelle = leitstelle.antwort
    leitstelle.buecher, leitstelle.regale, leitstelle.neu, leitstelle.sonst = {}, {}, [], {}
    leitstelle.halt, leitstelle.angekommen = None, asyncio.Event()

    async def antwort(r: httpx.Request) -> httpx.Response:
        if r.url.path == "/v1/models":
            return modelle(r)
        f, text = frage(r), nutzertext(r)
        for anfang, a in leitstelle.sonst.items():
            if f.startswith(anfang):
                return a if isinstance(a, httpx.Response) else chat_antwort(a if isinstance(a, str) else json.dumps(a))
        if f.startswith("Katalog einordnen"):
            leitstelle.angekommen.set()
            if leitstelle.halt is not None:
                await leitstelle.halt.wait()
            werke = text.split("\nWerke:\n", 1)[1]
            return chat_antwort(json.dumps({"buecher": [
                {"nummer": int(n), "kategorien": [{"schluessel": s, "sicherheit": w, "satz": satz} for s, w, satz in leitstelle.buecher.get(t, [])]}
                for n, t in ZEILE.findall(werke)]}))
        if f.startswith("Alte Regale"):
            regale = text.split("\nAlte Regale:\n", 1)[1]
            return chat_antwort(json.dumps({"regale": [{"nummer": int(n), "schluessel": leitstelle.regale.get(t, ("", ""))[0],
                                                        "satz": leitstelle.regale.get(t, ("", "Bleibt ein Schlagwort."))[1]}
                                                       for n, t in ZEILE.findall(regale)]}))
        if f.startswith("Neue Kategorien"):
            return chat_antwort(json.dumps({"neu": leitstelle.neu}))
        raise AssertionError(f"unerwartete Frage: {f}")

    leitstelle.antwort = antwort
    leitstelle.chats = lambda: [r for r in leitstelle.anfragen if r.url.path == "/v1/chat/completions"]
    return leitstelle


async def einordnen(client, **start) -> dict:
    r = await client.post("/api/katalog/einordnen", json=start or None)
    assert r.status_code == 200, r.text
    await einordner.warten()
    return (await client.get("/api/katalog/einordnen/stand")).json()


async def vorschlaege(client, **filter) -> list[dict]:
    r = await client.get("/api/katalog/vorschlaege", params=filter)
    assert r.status_code == 200, r.text
    return r.json()["vorschlaege"]


def je_buch(liste: list[dict], n: dict[str, int]) -> set[tuple[int, str, str]]:
    namen = {v: k for k, v in n.items()}
    return {(v["buch"]["id"], namen[v["kategorie_id"]], v["quelle"]) for v in liste}


# -- ohne KI ----------------------------------------------------------------------------------------------------------------

async def test_ohne_katalog_kein_lauf(client, ohne_ki):
    r = await client.post("/api/katalog/einordnen")
    assert r.status_code == 409 and r.json()["detail"] == "Es gibt noch keinen Katalog mit sichtbaren Kategorien"
    assert (await client.get("/api/katalog/einordnen/stand")).json()["stand"] == ""


async def test_ohne_ki_nur_regeln_in_stapeln(client, test_db, ohne_ki):
    n = nummern(await katalog_annehmen(client))
    krimi = await werk(test_db, "Nebel über der Marsch", regale=("Kriminalroman",))
    python = await werk(test_db, "Python für Neugierige", regale=("Informatik",))
    nichts = await werk(test_db, "Ganz für sich")
    beleg = await werk(test_db, "Rechnung des Kommissars", typ="dokument")
    schon = await werk(test_db, "Schon eingeordnet", regale=("Fantasy",))
    await test_db.execute("INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)", (schon, n["romane/fantasy"]))
    await test_db.commit()

    s = await einordnen(client, stapel=2)
    assert {k: s[k] for k in ("laeuft", "pause", "stand", "stapel", "stapel_gesamt", "stapel_groesse", "regeln", "ki", "ohne_vorschlag", "grund")} == {
        "laeuft": False, "pause": False, "stand": "fertig", "stapel": 2, "stapel_gesamt": 2, "stapel_groesse": 2, "regeln": 3, "ki": 0,
        "ohne_vorschlag": 1, "grund": OHNE_KI}
    liste = await vorschlaege(client)
    assert je_buch(liste, n) == {(krimi, "romane/krimi", "regel"), (python, "technik/informatik", "regel"), (beleg, "besonderes/belege", "regel")}
    erster = liste[0]
    assert (erster["buch"]["id"], erster["sicherheit"], erster["gruende"], erster["vorab"]) == (
        python, 93, ["Sachgruppe 004", "Titelwort Python"], True)
    assert "cover_stand" in erster["buch"] and erster["auch"] == []
    assert nichts not in {v["buch"]["id"] for v in liste}
    assert (await client.get("/api/katalog/vorschlaege/uebersicht")).json() == [
        {"kategorie_id": n["romane/krimi"], "anzahl": 1}, {"kategorie_id": n["technik/informatik"], "anzahl": 1},
        {"kategorie_id": n["besonderes/belege"], "anzahl": 1}]
    seite = (await client.get("/api/katalog/vorschlaege", params={"kategorie": n["romane/krimi"], "pro_seite": 1})).json()
    assert seite["gesamt"] == 1 and seite["vorschlaege"][0]["buch"]["id"] == krimi
    assert (await client.get("/api/katalog/vorschlaege", params={"kategorie": 99999})).status_code == 404


async def test_ein_dokument_bekommt_nie_eine_romankategorie(client, test_db, ki_sagt):
    """Regeln und KI schlagen nur Kategorien aus Bereichen der Art des Werks vor; die KI sieht nur diese."""
    n = nummern(await katalog_annehmen(client))
    buch = await werk(test_db, "Kommissar Rechnung ermittelt")                 # trifft Krimi und (nur für Dokumente) Belege
    dokument = await werk(test_db, "Rechnung vom Kommissar", typ="dokument")
    ki_sagt.buecher = {"Kommissar Rechnung ermittelt": [("besonderes/belege", 90, "Eine Rechnung."), ("romane/krimi", 70, "Ein Krimi.")],
                       "Rechnung vom Kommissar": [("romane/krimi", 95, "Ein Kommissar."), ("besonderes/belege", 80, "Eine Rechnung.")]}

    s = await einordnen(client)
    assert s["stand"] == "fertig" and s["grund"] == ""
    assert je_buch(await vorschlaege(client), n) == {(buch, "romane/krimi", "beide"), (dokument, "besonderes/belege", "beide")}
    texte = {nutzertext(r).split("\nWerke:\n")[1]: nutzertext(r) for r in ki_sagt.chats()}
    assert len(texte) == 2                                                   # eine Anfrage je Art
    for werke, ganz in texte.items():
        if "Rechnung vom Kommissar" in werke:
            assert "besonderes/belege" in ganz and "romane/krimi" not in ganz
        else:
            assert "romane/krimi" in ganz and "besonderes/belege" not in ganz
    koerper = json.loads(ki_sagt.chats()[0].content)
    assert koerper["response_format"]["json_schema"]["name"] == "katalog_einordnen"
    assert ki_sagt.chats()[0].headers["X-Leitstelle-Prioritaet"] == "hintergrund"
    assert ki_sagt.chats()[0].headers["X-Leitstelle-Arbeit"].startswith("bf-katalog-")


# -- mit KI -----------------------------------------------------------------------------------------------------------------

async def test_ki_und_regel_zusammen_unbekanntes_faellt_weg(client, test_db, ki_sagt):
    n = nummern(await katalog_annehmen(client))
    krimi = await werk(test_db, "Nebel über der Marsch", regale=("Kriminalroman",))
    drache = await werk(test_db, "Die Flügel des Morgens", beschreibung="Ein junger Drache lernt fliegen.")
    ki_sagt.buecher = {"Nebel über der Marsch": [("romane/krimi", 85, "Ein Mord im Watt."), ("romane/gibtsnicht", 99, "Erfunden."),
                                                 ("romane/fantasy", 30, "Vielleicht."), ("technik/informatik", 20, "Kaum.")],
                       "Die Flügel des Morgens": [("romane/fantasy", 88, "Ein Drache.")]}

    s = await einordnen(client)
    assert (s["stand"], s["regeln"], s["ki"], s["ohne_vorschlag"]) == ("fertig", 1, 3, 0)
    liste = await vorschlaege(client)
    assert je_buch(liste, n) == {(krimi, "romane/krimi", "beide"), (krimi, "romane/fantasy", "ki"), (drache, "romane/fantasy", "ki")}
    beide = next(v for v in liste if v["quelle"] == "beide")
    assert (beide["sicherheit"], beide["gruende"]) == (90, ["Schlagwort Kriminalroman", "Ein Mord im Watt."])
    vielleicht = next(v for v in liste if v["buch"]["id"] == krimi and v["quelle"] == "ki")
    assert beide["auch"] == [{"id": vielleicht["id"], "kategorie_id": n["romane/fantasy"], "name": "Fantasy", "sicherheit": 30}]
    assert vielleicht["vorab"] is False                                      # unter katalog_sicher_ab
    werke = nutzertext(next(r for r in ki_sagt.chats() if frage(r).startswith("Katalog einordnen"))).split("\nWerke:\n")[1]
    assert "Schlagworte: Kriminalroman" in werke and "Beschreibung: Ein junger Drache lernt fliegen." in werke


async def test_unbrauchbare_antwort_laesst_die_regeln(client, test_db, ki_sagt):
    n = nummern(await katalog_annehmen(client))
    krimi = await werk(test_db, "Nebel über der Marsch", regale=("Kriminalroman",))
    ki_sagt.sonst = {"Katalog einordnen": "Das weiß ich leider nicht."}
    s = await einordnen(client)
    assert s["stand"] == "fertig" and "Die Antwort der KI ist kein JSON" in s["grund"] and "nur nach Regeln" in s["grund"]
    assert je_buch(await vorschlaege(client), n) == {(krimi, "romane/krimi", "regel")}


async def test_falsche_form_laesst_die_regeln(client, test_db, ki_sagt):
    await katalog_annehmen(client)
    await werk(test_db, "Nebel über der Marsch", regale=("Kriminalroman",))
    ki_sagt.sonst = {"Katalog einordnen": {"buecher": [{"nummer": 1, "kategorien": "krimi"}]}}
    s = await einordnen(client)
    assert "passt nicht zur verlangten Form" in s["grund"] and s["regeln"] == 1


async def test_ablehnung_pausiert_und_fortsetzen_macht_weiter(client, test_db, ki_sagt):
    n = nummern(await katalog_annehmen(client))
    erstes = await werk(test_db, "Nebel über der Marsch", regale=("Kriminalroman",))
    zweites = await werk(test_db, "Python für Neugierige")
    abgelehnt = httpx.Response(403, json={"error": {"code": "faehigkeit_nicht_erlaubt", "message": "Fähigkeit text fehlt"}})
    ki_sagt.sonst = {"Katalog einordnen: Stapel 2": abgelehnt}

    s = await einordnen(client, stapel=1)
    assert (s["stand"], s["pause"], s["stapel"], s["stapel_gesamt"]) == ("pause", True, 1, 2)
    assert s["grund"].startswith("Die KI kann gerade nicht: ") and "Fähigkeit text fehlt" in s["grund"]
    assert {v["buch"]["id"] for v in await vorschlaege(client)} == {erstes}          # nur der fertige Stapel
    assert len(ki_sagt.chats()) == 2                                                 # nie in einer Schleife

    r = await client.post("/api/katalog/einordnen")                                  # pausiert: es bleibt bei ihm
    assert r.json()["stand"] == "pause"
    ki_sagt.sonst = {}
    r = await client.post("/api/katalog/einordnen/fortsetzen")
    assert r.status_code == 200 and r.json()["laeuft"] is True
    await einordner.warten()
    s = (await client.get("/api/katalog/einordnen/stand")).json()
    assert (s["stand"], s["stapel"], s["grund"]) == ("fertig", 2, "")
    assert je_buch(await vorschlaege(client), n) == {(erstes, "romane/krimi", "regel"), (zweites, "technik/informatik", "regel")}


async def test_pause_mitten_in_der_anfrage(client, test_db, ki_sagt):
    n = nummern(await katalog_annehmen(client))
    b = await werk(test_db, "Nebel über der Marsch")
    ki_sagt.buecher = {"Nebel über der Marsch": [("romane/krimi", 80, "Ein Krimi.")]}
    ki_sagt.halt = asyncio.Event()

    r = await client.post("/api/katalog/einordnen")
    assert r.json()["laeuft"] is True
    await asyncio.wait_for(ki_sagt.angekommen.wait(), 5)
    r = await client.post("/api/katalog/einordnen/pause")
    assert (r.json()["stand"], r.json()["grund"], r.json()["schritt"]) == ("pause", "Pausiert", "")
    await asyncio.wait_for(einordner.warten(), 5)                                    # die Aufgabe endet sofort
    assert await vorschlaege(client) == []
    assert (await client.post("/api/katalog/einordnen/pause")).json()["stand"] == "pause"

    ki_sagt.halt.set()
    ki_sagt.halt = None
    await client.post("/api/katalog/einordnen/fortsetzen")
    await einordner.warten()
    s = (await client.get("/api/katalog/einordnen/stand")).json()
    assert (s["stand"], s["stapel"], s["ki"]) == ("fertig", 1, 1)
    assert je_buch(await vorschlaege(client), n) == {(b, "romane/krimi", "ki")}


async def test_nach_neustart_am_letzten_fertigen_stapel(client, test_db, ohne_ki):
    n = nummern(await katalog_annehmen(client))
    erstes = await werk(test_db, "Nebel über der Marsch", regale=("Kriminalroman",))
    zweites = await werk(test_db, "Python für Neugierige")
    # so stand es beim Beenden: der erste Stapel war fertig, der Lauf lief
    await test_db.execute("""INSERT INTO katalog_lauf (art, stand, stapel, stapel_gesamt, stapel_groesse, nach_buch, regeln)
                             VALUES ('einordnen', 'laeuft', 1, 2, 1, ?, 1)""", (erstes,))
    await test_db.commit()

    await einordner.nach_neustart()
    await einordner.warten()
    s = (await client.get("/api/katalog/einordnen/stand")).json()
    assert (s["stand"], s["stapel"], s["stapel_gesamt"], s["regeln"]) == ("fertig", 2, 2, 2)
    assert je_buch(await vorschlaege(client), n) == {(zweites, "technik/informatik", "regel")}      # das erste nicht noch einmal


# -- Vorschläge entscheiden -------------------------------------------------------------------------------------------------

async def test_annehmen_schreibt_die_quelle_abgelehnte_kommen_nicht_wieder(client, test_db, ki_sagt):
    n = nummern(await katalog_annehmen(client))
    krimi = await werk(test_db, "Nebel über der Marsch", regale=("Kriminalroman",))
    drache = await werk(test_db, "Die Flügel des Morgens")
    zweifel = await werk(test_db, "Python im Nebel")
    ki_sagt.buecher = {"Die Flügel des Morgens": [("romane/fantasy", 88, "Ein Drache.")],
                       "Python im Nebel": [("romane/krimi", 60, "Klingt nach Krimi.")]}
    await einordnen(client)
    v = {(x["buch"]["id"], x["kategorie_id"]): x["id"] for x in await vorschlaege(client)}

    r = await client.post("/api/katalog/vorschlaege/annehmen", json={"ids": [v[(krimi, n["romane/krimi"])], v[(drache, n["romane/fantasy"])], 99999]})
    assert r.status_code == 200 and r.json() == {"angenommen": 2}
    quellen = await test_db.fetch_all("SELECT book_id, category_id, quelle FROM book_categories WHERE category_id IN (?, ?) ORDER BY book_id",
                                      (n["romane/krimi"], n["romane/fantasy"]))
    assert [(z["book_id"], z["quelle"]) for z in quellen] == [(krimi, "katalog-regel"), (drache, "katalog-ki")]
    r = await client.post("/api/katalog/vorschlaege/ablehnen", json={"ids": [v[(zweifel, n["romane/krimi"])]]})
    assert r.json() == {"abgelehnt": 1}
    assert (await client.post("/api/katalog/vorschlaege/ablehnen", json={"ids": [v[(zweifel, n["romane/krimi"])]]})).json() == {"abgelehnt": 0}
    offen = {(x["buch"]["id"], x["kategorie_id"]) for x in await vorschlaege(client)}
    assert offen == {(zweifel, n["technik/informatik"])}

    await client.post("/api/katalog/vorschlaege/ablehnen", json={"ids": [v[(zweifel, n["technik/informatik"])]]})
    ki_sagt.buecher["Python im Nebel"] = [("romane/krimi", 99, "Jetzt ganz sicher ein Krimi."), ("romane/fantasy", 50, "Vielleicht.")]
    await einordnen(client)                                                          # das Werk steht in keiner Kategorie: wieder dran
    assert {(x["buch"]["id"], x["kategorie_id"]) for x in await vorschlaege(client)} == {(zweifel, n["romane/fantasy"])}
    stand = await test_db.fetch_all("SELECT stand FROM katalog_vorschlag WHERE book_id = ? AND category_id = ?", (zweifel, n["romane/krimi"]))
    assert [z["stand"] for z in stand] == ["abgelehnt"]


async def test_alle_einer_kategorie_annehmen(client, test_db, ohne_ki):
    n = nummern(await katalog_annehmen(client))
    for t in ("Python für Neugierige", "Python im Nebel"):
        await werk(test_db, t)
    await einordnen(client)
    r = await client.post("/api/katalog/vorschlaege/annehmen", json={"kategorie": n["technik/informatik"]})
    assert r.json() == {"angenommen": 2}
    assert await vorschlaege(client) == []
    assert (await client.post("/api/katalog/vorschlaege/annehmen", json={})).status_code == 422
    assert (await client.post("/api/katalog/vorschlaege/annehmen", json={"ids": [1], "kategorie": 1})).status_code == 422
    k = (await client.get("/api/katalog")).json()
    assert next(b for b in k["bereiche"] if b["schluessel"] == "technik")["anzahl"] == 2


# -- alte Regale ------------------------------------------------------------------------------------------------------------

async def test_alte_regale_vorschlag_uebernehmen_und_entfernen(client, test_db, ki_sagt):
    n = nummern(await katalog_annehmen(client))
    a = await werk(test_db, "Nebel über der Marsch", regale=("Kriminalroman", "Fernweh"))
    b = await werk(test_db, "Inselsommer", regale=("Fernweh", "Drachenkunde"))
    await werk(test_db, "Python für Neugierige", regale=("Informatik",))
    await regal(test_db, "Lieblinge", spezial=True)                                   # eigenes Regal: kein altes
    await regal(test_db, "Ungeordnet")

    alte = {x["name"]: x for x in (await client.get("/api/katalog/alt")).json()}
    assert set(alte) == {"Kriminalroman", "Fernweh", "Drachenkunde", "Informatik"}
    assert alte["Kriminalroman"]["vorschlag"] == {"art": "kategorie", "kategorie_id": n["romane/krimi"],
                                                  "grund": "Schlagwort Kriminalroman der Kategorie Krimi"}
    assert alte["Informatik"]["vorschlag"]["grund"] == "Gleicher Name wie die Kategorie Informatik"
    assert alte["Fernweh"]["vorschlag"] == {"art": "schlagwort", "kategorie_id": None, "grund": NICHT_GEPRUEFT}
    assert alte["Fernweh"]["anzahl"] == 2

    ki_sagt.regale = {"Drachenkunde": ("romane/fantasy", "Drachen sind Fantasy."), "Fernweh": ("", "Ein Gefühl, keine Gattung.")}
    await einordnen(client)
    fragen = [frage(r) for r in ki_sagt.chats()]
    assert fragen[0] == "Alte Regale zuordnen: Anfrage 1"
    gefragt = nutzertext(ki_sagt.chats()[0]).split("\nAlte Regale:\n")[1]
    assert set(gefragt.splitlines()) == {"1. Drachenkunde", "2. Fernweh"}           # nur die ohne Regel
    alte = {x["name"]: x for x in (await client.get("/api/katalog/alt")).json()}
    assert alte["Drachenkunde"]["vorschlag"] == {"art": "kategorie", "kategorie_id": n["romane/fantasy"], "grund": "Die KI: Drachen sind Fantasy."}
    assert alte["Fernweh"]["vorschlag"] == {"art": "schlagwort", "kategorie_id": None, "grund": "Die KI: Ein Gefühl, keine Gattung."}

    r = await client.post("/api/katalog/alt/uebernehmen", json={"ids": [alte["Drachenkunde"]["id"]], "ziel": {"kategorie_id": n["romane/fantasy"]}})
    assert r.status_code == 200 and r.json() == {"buecher": 1}
    z = await test_db.fetch_one("SELECT quelle FROM book_categories WHERE book_id = ? AND category_id = ?", (b, n["romane/fantasy"]))
    assert z["quelle"] == "manuell"
    r = await client.post("/api/katalog/alt/uebernehmen", json={"ids": [alte["Fernweh"]["id"]], "ziel": {"schlagwort": True}})
    assert r.json() == {"buecher": 2}
    await client.post("/api/katalog/alt/uebernehmen", json={"ids": [alte["Fernweh"]["id"]], "ziel": {"schlagwort": True}})   # nicht doppelt
    etiketten = await test_db.fetch_all("SELECT book_id, name FROM book_labels ORDER BY book_id")
    assert [(e["book_id"], e["name"]) for e in etiketten] == [(a, "Fernweh"), (b, "Fernweh")]

    assert (await client.post("/api/katalog/alt/uebernehmen", json={"ids": [99999], "ziel": {"schlagwort": True}})).status_code == 404
    lieblinge = await regal(test_db, "Lieblinge", spezial=True)
    assert (await client.get(f"/api/katalog/alt/{lieblinge}/loeschfolgen")).status_code == 404
    assert (await client.post("/api/katalog/alt/uebernehmen", json={"ids": [alte["Fernweh"]["id"]], "ziel": {}})).status_code == 422
    assert (await client.post("/api/katalog/alt/uebernehmen", json={"ids": [alte["Fernweh"]["id"]], "ziel": {"kategorie_id": 99999}})).status_code == 404

    # erst nach der Folgenvorschau und ausdrücklich entfernt; bis dahin bleibt das Regal stehen
    assert await test_db.fetch_one("SELECT id FROM categories WHERE id = ?", (alte["Fernweh"]["id"],))
    r = await client.get(f"/api/katalog/alt/{alte['Fernweh']['id']}/loeschfolgen")
    assert r.json() == {"id": alte["Fernweh"]["id"], "name": "Fernweh", "buecher": 2, "ohne_kategorie": 1,           # Inselsommer steht in Fantasy
                        "titel": ["Inselsommer", "Nebel über der Marsch"]}
    r = await client.delete(f"/api/katalog/alt/{alte['Fernweh']['id']}")
    assert r.json() == {"entfernt": True, "id": alte["Fernweh"]["id"], "buecher": 2}
    assert await test_db.fetch_one("SELECT id FROM categories WHERE id = ?", (alte["Fernweh"]["id"],)) is None
    assert len(await test_db.fetch_all("SELECT id FROM books WHERE id IN (?, ?)", (a, b))) == 2
    assert (await client.delete(f"/api/katalog/alt/{alte['Fernweh']['id']}")).status_code == 404


# -- neu aus dem Bestand ----------------------------------------------------------------------------------------------------

async def test_neue_kategorien_aus_dem_bestand(client, test_db, ki_sagt, monkeypatch):
    monkeypatch.setattr(settings, "katalog_neu_ab", 2)
    for t in ("Bienen im Garten", "Honig ernten", "Das Bienenjahr"):
        await werk(test_db, t, regale=("Imkerei",))
    await werk(test_db, "Einmal Imkerei", regale=("Imkerei", "Kriminalroman"))
    ki_sagt.neu = [{"bereich": "leben", "name": "Imkerei", "zeichen": "seedling", "ki_beschreibung": "Bienen halten und Honig.",
                    "schlagworte": ["imkerei", "Erfunden"]},
                   {"bereich": "gibtsnicht", "name": "Irgendwas", "zeichen": "tag", "ki_beschreibung": "", "schlagworte": ["Imkerei"]},
                   {"bereich": "romane", "name": "Krimi und Thriller", "zeichen": "tag", "ki_beschreibung": "", "schlagworte": ["Imkerei"]}]

    await client.post("/api/katalog/entwurf", json={"weg": "bestand"})
    await bestandslauf.warten()
    s = (await client.get("/api/katalog/entwurf")).json()
    assert (s["lauf"]["stand"], s["lauf"]["ki"], s["lauf"]["grund"]) == ("fertig", 1, "")
    [frage_neu] = [r for r in ki_sagt.chats() if frage(r) == "Neue Kategorien aus dem Bestand"]
    assert "- Imkerei (4 Bücher)" in nutzertext(frage_neu) and "Kriminalroman" not in nutzertext(frage_neu).split("Häufige")[1]
    leben = next(b for b in s["entwurf"]["bereiche"] if b["schluessel"] == "leben")
    neu = [k for k in leben["kategorien"] if k["herkunft"] == "neu"]
    assert [(k["schluessel"], k["name"], k["zeichen"], k["regeln"]["schlagworte"], k["anzahl"], k["verborgen"]) for k in neu] == [
        ("leben/imkerei", "Imkerei", "seedling", ["Imkerei"], 4, False)]
    assert leben["verborgen"] is False


# -- große Kategorie und ihre Teile -----------------------------------------------------------------------------------------

async def test_teil_vor_der_grossen_kategorie(client, test_db, ki_sagt):
    """Passt ein Werk zu einem Teil, wird der Teil vorgeschlagen, sonst die große Kategorie; kein Werk fällt heraus."""
    katalog = {"fassung": 1, "bereiche": [{"schluessel": "technik", "name": "Technik", "farbe": "#2f6fb3", "kategorien": [
        {"schluessel": "technik/informatik", "name": "Informatik", "regeln": {"schlagworte": ["Informatik"], "titelwoerter": ["Python"]}},
        {"schluessel": "technik/programmierung", "name": "Programmierung", "teil_von": "technik/informatik",
         "regeln": {"titelwoerter": ["Python"]}},
        {"schluessel": "technik/netzwerke", "name": "Netzwerke", "teil_von": "technik/informatik", "regeln": {"titelwoerter": ["Netzwerk"]}}]}]}
    n = nummern(await katalog_annehmen(client, katalog))
    python = await werk(test_db, "Python für Neugierige", regale=("Informatik",))       # Regel trifft Teil und große
    allgemein = await werk(test_db, "Rechnen mit Maschinen", regale=("Informatik",))    # nur die große
    netz = await werk(test_db, "Leitungen im Haus")                                     # die KI nennt die große, die Regel nichts
    kabel = await werk(test_db, "Kabel und Knoten")                                     # die KI nennt große und Teil
    ki_sagt.buecher = {"Leitungen im Haus": [("technik/informatik", 70, "Etwas mit Rechnern.")],
                       "Kabel und Knoten": [("technik/informatik", 80, "Rechner."), ("technik/netzwerke", 85, "Netze.")]}

    await einordnen(client)
    assert je_buch(await vorschlaege(client), n) == {(python, "technik/programmierung", "regel"), (allgemein, "technik/informatik", "regel"),
                                                     (netz, "technik/informatik", "ki"), (kabel, "technik/netzwerke", "ki")}
    katalogtext = nutzertext(next(r for r in ki_sagt.chats() if frage(r).startswith("Katalog einordnen")))
    assert "- technik/informatik: Informatik (nur, wenn keiner ihrer Teile passt)" in katalogtext
    assert "- technik/netzwerke: Netzwerke (Teil von technik/informatik)" in katalogtext
    k = (await client.get("/api/katalog")).json()
    assert [(x["schluessel"], x["teil_von"]) for x in k["bereiche"][0]["kategorien"]] == [
        ("technik/informatik", ""), ("technik/programmierung", "technik/informatik"), ("technik/netzwerke", "technik/informatik")]
    datei = (await client.get("/api/katalog/datei")).json()
    assert datei["bereiche"][0]["kategorien"][1]["teil_von"] == "technik/informatik"
