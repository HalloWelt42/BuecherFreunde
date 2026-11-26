"""Katalog (BF-69): Standard, Entwurf (Standard, leer, Datei, Bestand), Annehmen ohne Löschen, Bereiche und Kategorien,
Löschfolgen, Treffer, Einstellungen und was sich an Büchern und Regalen zeigt. Alle Werke sind erfunden."""

import pytest

from backend.app.core.config import settings
from backend.app.katalog.bestandslauf import OHNE_KI, bestandslauf
from backend.app.katalog.einordnen import einordner
from tests.api.katalog_hilfen import KLEIN, katalog_annehmen, nummern, regal, werk


@pytest.fixture(autouse=True)
async def laeufe_aufraeumen(monkeypatch):
    monkeypatch.setattr(settings, "leitstelle_adresse", "")
    yield
    await einordner.stoppen()
    await bestandslauf.stoppen()


async def entwurf(client) -> dict:
    r = await client.get("/api/katalog/entwurf")
    assert r.status_code == 200, r.text
    return r.json()


# -- ohne Katalog, Standard -------------------------------------------------------------------------------------------------

async def test_ohne_katalog(client, test_db):
    await werk(test_db, "Nebel über der Marsch", regale=("Kriminalroman",))
    await regal(test_db, "Lieblinge", spezial=True)
    r = await client.get("/api/katalog")
    assert r.status_code == 200
    k = r.json()
    assert (k["bereiche"], k["hat_katalog"], k["ohne_kategorie"]) == ([], False, 1)
    assert {(g["name"], g["anzahl"], g["spezial"]) for g in k["regale"]} == {("Kriminalroman", 1, False), ("Lieblinge", 0, True)}
    assert (await entwurf(client)) == {"entwurf": None, "lauf": None}


async def test_standard_als_entwurf(client):
    r = await client.get("/api/katalog/standard")
    assert r.status_code == 200
    s = r.json()
    assert len(s["bereiche"]) == 10
    technik = next(b for b in s["bereiche"] if b["schluessel"] == "technik")
    informatik = next(k for k in technik["kategorien"] if k["schluessel"] == "technik/informatik")
    assert (informatik["herkunft"], informatik["anzahl"], informatik["farbe"]) == ("standard", None, technik["farbe"])
    assert "id" not in informatik and informatik["teile"]


# -- Entwurf ----------------------------------------------------------------------------------------------------------------

async def test_standard_annehmen_dann_aendern_ohne_loeschen(client, test_db):
    r = await client.post("/api/katalog/entwurf", json={"weg": "standard"})
    assert r.status_code == 200 and r.json()["entwurf"]["bereiche"][0]["schluessel"] == "romane"
    k = (await client.post("/api/katalog/entwurf/annehmen")).json()
    assert k["hat_katalog"] is True and len(k["bereiche"]) == 10
    assert sum(len(b["kategorien"]) for b in k["bereiche"]) == 66
    vorher = nummern(k)
    assert (await entwurf(client))["entwurf"] is None

    # ein Entwurf mit geänderter und neuer Kategorie, ohne den Bereich Comics: nichts wird gelöscht
    e = (await client.post("/api/katalog/entwurf", json={"weg": "standard"})).json()["entwurf"]
    e["bereiche"] = [b for b in e["bereiche"] if b["schluessel"] != "comics"]
    technik = next(b for b in e["bereiche"] if b["schluessel"] == "technik")
    technik["kategorien"][0]["name"] = "Rechnerkunde"
    technik["kategorien"].append({"schluessel": "technik/funk", "name": "Funk", "zeichen": "fa-tower-broadcast", "farbe": "#123456"})
    r = await client.put("/api/katalog/entwurf", json=e)
    assert r.status_code == 200, r.text
    funk = r.json()["entwurf"]["bereiche"][3]["kategorien"][-1]
    assert (funk["herkunft"], funk["zeichen"], funk["farbe"]) == ("eigen", "tower-broadcast", "#123456")
    k = (await client.post("/api/katalog/entwurf/annehmen")).json()
    nachher = nummern(k)
    assert nachher["technik/informatik"] == vorher["technik/informatik"]
    assert next(x for b in k["bereiche"] for x in b["kategorien"] if x["schluessel"] == "technik/informatik")["name"] == "Rechnerkunde"
    assert "technik/funk" in nachher and "comics/manga" in nachher                     # neu angelegt, nichts gelöscht
    assert set(vorher) <= set(nachher)

    regale = (await client.get("/api/categories")).json()
    assert regale == []                                                                # Bereiche und Kategorien sind keine Regale


async def test_leer_verwerfen_und_ohne_entwurf(client):
    r = await client.post("/api/katalog/entwurf", json={"weg": "leer"})
    assert r.json() == {"entwurf": {"fassung": 1, "bereiche": []}, "lauf": None}
    r = await client.delete("/api/katalog/entwurf")
    assert r.status_code == 200 and r.json() == {"entwurf": None, "lauf": None}
    r = await client.post("/api/katalog/entwurf/annehmen")
    assert r.status_code == 404 and r.json()["detail"] == "Es gibt keinen Entwurf"
    assert (await client.post("/api/katalog/entwurf", json={"weg": "irgendwie"})).status_code == 422


async def test_datei_sichern_und_wieder_laden(client):
    await katalog_annehmen(client)
    r = await client.get("/api/katalog/datei")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    d = r.json()
    assert [b["schluessel"] for b in d["bereiche"]] == ["romane", "technik", "besonderes"]
    assert d["bereiche"][2]["arten"] == ["dokument", "heft"]
    krimi = d["bereiche"][0]["kategorien"][0]
    assert "anzahl" not in krimi and krimi["farbe"] == "" and krimi["regeln"]["titelwoerter"] == ["Kommissar"]
    assert krimi["herkunft"] == "standard"                                           # den Schlüssel kennt der Standard
    d["bereiche"][0]["kategorien"].append({"schluessel": "romane/seefahrt", "name": "Seefahrt"})
    r = await client.post("/api/katalog/datei", json=d)
    assert r.status_code == 200
    geladen = r.json()["entwurf"]
    assert geladen["bereiche"][0]["kategorien"][0]["herkunft"] == "standard"
    assert geladen["bereiche"][0]["kategorien"][-1]["herkunft"] == "eigen"           # ohne Angabe und dem Standard unbekannt
    assert geladen["bereiche"][0]["kategorien"][0]["farbe"] == "#8e44ad"            # gezeigt: die geerbte Farbe


@pytest.mark.parametrize(("aenderung", "meldung"), [
    (lambda d: d["bereiche"][1]["kategorien"].append(dict(d["bereiche"][0]["kategorien"][0])),
     "Anfrage: Der Schlüssel romane/krimi steht mehr als einmal im Katalog"),
    (lambda d: d["bereiche"][0].update(farbe="lila"), "Bereiche, Eintrag 1, Farbe: keine Farbe wie #3366ff"),
    (lambda d: d["bereiche"][0]["kategorien"][0].update(zeichen="Lupe!"), "Bereiche, Eintrag 1, Kategorien, Eintrag 1, Zeichen: hat nicht die erwartete Form"),
    (lambda d: d["bereiche"][0].update(arten=["roman"]), "Bereiche, Eintrag 1, Arten, Eintrag 1: erlaubt ist leer oder dokument, heft, katalog, broschuere, anleitung"),
    (lambda d: d["bereiche"][0]["kategorien"][0]["regeln"].update(farben=["rot"]), "Bereiche, Eintrag 1, Kategorien, Eintrag 1, Regeln, farben: ist hier nicht vorgesehen"),
    (lambda d: d["bereiche"][0]["kategorien"][0].update(schluessel="krimi"), "Bereiche, Eintrag 1, Kategorien, Eintrag 1, Schlüssel: hat nicht die erwartete Form"),
])
async def test_datei_wird_geprueft(client, aenderung, meldung):
    import copy
    d = copy.deepcopy(KLEIN)
    aenderung(d)
    r = await client.post("/api/katalog/datei", json=d)
    assert r.status_code == 422 and r.json()["detail"] == meldung
    assert (await entwurf(client))["entwurf"] is None


async def test_entwurf_aus_dem_bestand(client, test_db):
    assert (await client.put("/api/katalog/einstellungen", json={"stapel": 500, "ki_je_anfrage": 40, "sicher_ab": 80, "teilen_ab": 2})).status_code == 200
    for t in ("Python für Neugierige", "Webseiten bauen mit HTML", "Rechnernetze im Haus"):
        await werk(test_db, t, regale=("Informatik",))
    for t, r in (("Kräfte und Felder", "Physik"), ("Stoffe im Alltag", "Chemie"), ("Zellen verstehen", "Biologie")):
        await werk(test_db, t, regale=(r,))                                  # jedes trifft auch einen Teil
    await werk(test_db, "Nebel über der Marsch", regale=("Kriminalroman",))
    await werk(test_db, "Gebrauchsanleitung Kaffeemühle", typ="dokument")
    await werk(test_db, "Bedienungsanleitung für den Roman")               # ein Buch: Besonderes gilt nur für Dokumente

    r = await client.post("/api/katalog/entwurf", json={"weg": "bestand"})
    assert r.status_code == 200
    assert r.json()["entwurf"] is None and r.json()["lauf"]["laeuft"] is True
    await bestandslauf.warten()
    s = await entwurf(client)
    assert (s["lauf"]["stand"], s["lauf"]["grund"], s["lauf"]["regeln"], s["lauf"]["ki"]) == ("fertig", OHNE_KI, 9, 0)
    bereiche = {b["schluessel"]: b for b in s["entwurf"]["bereiche"]}
    kategorien = {k["schluessel"]: k for b in bereiche.values() for k in b["kategorien"]}

    # 3 Treffer über 2: geteilt; die große bleibt für das Buch, das zu keinem Teil passt
    informatik = kategorien["technik/informatik"]
    assert (informatik["herkunft"], informatik["anzahl"], informatik["verborgen"], informatik["teile"]) == ("standard", 1, False, [])
    technik = [k["schluessel"] for k in bereiche["technik"]["kategorien"]]
    assert technik[technik.index("technik/informatik"):][:3] == ["technik/informatik", "technik/programmierung", "technik/web"]
    assert (kategorien["technik/programmierung"]["herkunft"], kategorien["technik/programmierung"]["anzahl"]) == ("geteilt", 1)
    assert kategorien["technik/programmierung"]["teil_von"] == "technik/informatik"
    # alle Treffer in Teilen: die große ist verborgen, ihre Teile nicht
    natur = kategorien["wissen/naturwissenschaften"]
    assert (natur["anzahl"], natur["verborgen"], natur["herkunft"]) == (0, True, "standard")
    assert [(kategorien[s]["anzahl"], kategorien[s]["verborgen"]) for s in ("wissen/physik", "wissen/chemie", "wissen/biologie", "wissen/erde")] == [
        (1, False), (1, False), (1, False), (0, True)]
    assert bereiche["wissen"]["anzahl"] == 3
    assert kategorien["technik/web"]["anzahl"] == 1 and kategorien["technik/sicherheit"]["verborgen"] is True
    assert (kategorien["romane/krimi"]["anzahl"], kategorien["romane/krimi"]["verborgen"]) == (1, False)
    assert (kategorien["romane/fantasy"]["anzahl"], kategorien["romane/fantasy"]["verborgen"], kategorien["romane/fantasy"]["herkunft"]) == (0, True, "standard")
    assert kategorien["besonderes/gebrauchsanleitungen"]["anzahl"] == 1    # nur das Dokument
    assert kategorien["romane/roman"]["anzahl"] == 1                       # das Buch mit "Roman" im Titel
    assert bereiche["comics"]["verborgen"] is True and bereiche["technik"]["verborgen"] is False
    assert bereiche["technik"]["anzahl"] == 3                               # kein Buch fällt beim Teilen heraus

    r = await client.post("/api/katalog/entwurf", json={"weg": "standard"})  # ein anderer Weg ersetzt
    assert r.json()["lauf"] is None


# -- Bereiche und Kategorien ------------------------------------------------------------------------------------------------

async def test_bereiche_und_kategorien_anlegen_und_aendern(client):
    k = await katalog_annehmen(client)
    r = await client.post("/api/katalog/bereiche", json={"name": "Garten und Hof", "zeichen": "fa-seedling", "farbe": "#257047"})
    assert r.status_code == 201, r.text
    b = r.json()
    assert (b["schluessel"], b["zeichen"], b["arten"], b["kategorien"], b["anzahl"]) == ("garten-und-hof", "seedling", [""], [], 0)
    assert (await client.post("/api/katalog/bereiche", json={"name": "romane"})).status_code == 409

    r = await client.post("/api/katalog/kategorien", json={"bereich_id": b["id"], "name": "Beete", "farbe": "#257047",
                                                           "regeln": {"schlagworte": ["Gemüsegarten"]}})
    assert r.status_code == 201, r.text
    beete = r.json()
    assert (beete["schluessel"], beete["farbe"], beete["herkunft"]) == ("garten-und-hof/beete", "#257047", "eigen")
    assert (await client.post("/api/katalog/kategorien", json={"bereich_id": b["id"], "name": "BEETE"})).status_code == 409
    assert (await client.post("/api/katalog/kategorien", json={"bereich_id": 99999, "name": "Irgendwo"})).status_code == 404
    assert (await client.post("/api/katalog/kategorien", json={"bereich_id": b["id"], "name": "X", "farbe": "grün"})).status_code == 422

    r = await client.patch(f"/api/katalog/bereiche/{b['id']}", json={"farbe": "#0e7563", "arten": ["", "heft"]})
    assert r.status_code == 200 and r.json()["arten"] == ["", "heft"]
    assert r.json()["kategorien"][0]["farbe"] == "#0e7563"                 # erbt, weil sie die Farbe des Bereichs hatte
    r = await client.patch(f"/api/katalog/kategorien/{beete['id']}", json={"farbe": "#7a5230", "zeichen": "carrot", "verborgen": True})
    assert (r.json()["farbe"], r.json()["zeichen"], r.json()["verborgen"]) == ("#7a5230", "carrot", True)
    romane = nummern(k)["romane"]
    r = await client.patch(f"/api/katalog/kategorien/{beete['id']}", json={"bereich_id": romane})
    assert r.status_code == 200 and r.json()["schluessel"] == "garten-und-hof/beete"          # der Schlüssel bleibt fest
    assert (await client.patch("/api/katalog/kategorien/99999", json={"name": "Nirgends"})).status_code == 404
    assert (await client.patch(f"/api/katalog/kategorien/{beete['id']}", json={"name": "Krimi"})).status_code == 409
    assert (await client.patch(f"/api/katalog/bereiche/{nummern(k)['romane/krimi']}", json={"name": "Kein Bereich"})).status_code == 404


async def test_loeschfolgen_und_loeschen(client, test_db):
    k = await katalog_annehmen(client)
    n = nummern(k)
    b = await werk(test_db, "Der Kommissar und die Möwe")
    await test_db.execute("INSERT INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'manuell')", (b, n["romane/krimi"]))
    await test_db.execute("INSERT INTO katalog_vorschlag (book_id, category_id, quelle) VALUES (?, ?, 'regel')", (b, n["romane/fantasy"]))
    await test_db.commit()

    r = await client.get(f"/api/katalog/bereiche/{n['romane']}/loeschfolgen")
    assert r.json() == {"name": "Romane", "buecher": 1, "vorschlaege": 1, "kategorien": 2, "titel": ["Der Kommissar und die Möwe"]}
    r = await client.delete(f"/api/katalog/bereiche/{n['romane']}")
    assert r.status_code == 409 and r.json()["detail"] == "Der Bereich hat noch Kategorien"
    r = await client.get(f"/api/katalog/kategorien/{n['romane/krimi']}/loeschfolgen")
    assert r.json() == {"name": "Krimi", "buecher": 1, "vorschlaege": 0, "kategorien": 0, "titel": ["Der Kommissar und die Möwe"]}

    for weg in ("romane/krimi", "romane/fantasy"):
        r = await client.delete(f"/api/katalog/kategorien/{n[weg]}")
        assert r.status_code == 200 and r.json() == {"geloescht": True, "id": n[weg]}
    assert await test_db.fetch_one("SELECT id FROM books WHERE id = ?", (b,))                 # das Buch bleibt
    assert await test_db.fetch_all("SELECT * FROM katalog_vorschlag") == []
    assert (await client.delete(f"/api/katalog/bereiche/{n['romane']}")).status_code == 200
    assert (await client.delete(f"/api/katalog/bereiche/{n['romane']}")).status_code == 404
    assert (await client.get("/api/katalog/kategorien/99999/loeschfolgen")).status_code == 404
    assert (await client.delete(f"/api/categories/{n['technik']}")).status_code == 404        # nicht über die Regale


async def test_treffer_der_regeln(client, test_db):
    k = await katalog_annehmen(client)
    await werk(test_db, "Python im Garten", regale=("Informatik",))                         # Sachgruppe 004 und Titelwort
    await werk(test_db, "Schlangen und Bits", verlag="Bitverlag Nord")
    await werk(test_db, "Python-Rechnung", typ="dokument")                                  # andere Art: zählt nicht
    r = await client.get(f"/api/katalog/kategorien/{nummern(k)['technik/informatik']}/treffer")
    assert r.status_code == 200
    assert r.json() == {"regeln": [{"art": "sachgruppen", "werte": ["004"], "treffer": 1}, {"art": "schlagworte", "werte": [], "treffer": 0},
                                   {"art": "titelwoerter", "werte": ["Python"], "treffer": 1}, {"art": "verlage", "werte": ["Bitverlag"], "treffer": 1}],
                        "zusammen": 2, "ki_vorschlaege": 0}


# -- Bücher, Regale, Einstellungen ------------------------------------------------------------------------------------------

async def test_buch_zeigt_kategorien_mit_zeichen_farbe_und_bereich(client, test_db):
    k = await katalog_annehmen(client)
    b = await werk(test_db, "Der Kommissar und die Möwe", regale=("Kriminalroman",))
    ohne = await werk(test_db, "Ganz für sich")
    assert (await client.post(f"/api/categories/{nummern(k)['romane/krimi']}/books/{b}")).status_code == 200
    kategorien = (await client.get(f"/api/books/{b}")).json()["categories"]
    assert [(c["art"], c["name"], c["zeichen"], c["farbe"], c["bereich"]) for c in kategorien] == [
        ("kategorie", "Krimi", "magnifying-glass", "#8e44ad", "Romane"), ("regal", "Kriminalroman", "", "#6b7280", None)]

    liste = (await client.get("/api/books", params={"ohne_kategorie": "true"})).json()
    assert [x["id"] for x in liste["buecher"]] == [ohne]
    liste = (await client.get("/api/books", params={"ohne_kategorie": "false"})).json()
    assert [x["id"] for x in liste["buecher"]] == [b]
    assert (await client.get("/api/katalog")).json()["ohne_kategorie"] == 1
    r = await client.post("/api/categories", json={"name": "Krimi"})                         # ein Regal darf wie eine Kategorie heißen
    assert r.status_code == 201
    assert [g["name"] for g in (await client.get("/api/categories")).json()] == ["Krimi", "Kriminalroman"]


async def test_einstellungen(client, monkeypatch):
    monkeypatch.setattr(settings, "katalog_stapel", 250)
    assert (await client.get("/api/katalog/einstellungen")).json() == {"stapel": 250, "ki_je_anfrage": 40, "sicher_ab": 80, "teilen_ab": 300}
    neu = {"stapel": 100, "ki_je_anfrage": 20, "sicher_ab": 90, "teilen_ab": 50}
    assert (await client.put("/api/katalog/einstellungen", json=neu)).json() == neu
    assert (await client.get("/api/katalog/einstellungen")).json() == neu
    r = await client.put("/api/katalog/einstellungen", json={**neu, "sicher_ab": 120})
    assert r.status_code == 422 and r.json()["detail"] == "Vorab angehakt ab: höchstens 100"


async def test_nur_mit_anmeldung(client_ohne_auth):
    for weg in ("/api/katalog", "/api/katalog/entwurf", "/api/katalog/einordnen/stand", "/api/katalog/vorschlaege"):
        assert (await client_ohne_auth.get(weg)).status_code == 401
