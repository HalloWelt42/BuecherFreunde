"""Abgleich mit dem Bestand für die Erweiterung (BF-119): Bücher einer fremden Seite gegen die eigene Bibliothek, und die freie
Suche nach markiertem Text. Bücher, Personen und ISBN sind erfunden."""

import pytest

from tests.api.conftest import buch_erstellen

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def bestand(test_db):
    werft = await buch_erstellen(test_db, hash="werft", title="Die Werft am Fluss", author="Okke Harms", isbn="978-3-946417-70-5", year=2019,
                                 file_format="epub", description="<p>Drei Generationen einer Bootsbauerfamilie.</p>")
    garten = await buch_erstellen(test_db, hash="garten", title="Gärten im Schatten", author="Henrike Moll", isbn="978-3-946417-62-0", year=2014)
    turm = await buch_erstellen(test_db, hash="turm", title="Kleine Geschichte der Leuchttürme", author="Femke Jansen", isbn="9783946417934", year=2017)
    band = await buch_erstellen(test_db, hash="band", title="Die Inselchronik Band 2", author="Tade Petersen", isbn="", year=2020)
    gedichte = await buch_erstellen(test_db, hash="gedichte", title="Gedichte vom Deich", author="Lene Brodersen", isbn="", year=2011)
    return {"werft": werft, "garten": garten, "turm": turm, "band": band, "gedichte": gedichte}


def treffer(antwort: dict) -> dict[int, list[tuple[int, str, str]]]:
    return {e["nr"]: [(t["buch"]["id"], t["art"], t["grund"]) for t in e["treffer"]] for e in antwort["ergebnisse"]}


async def test_eine_seite_mit_vorhandenen_aehnlichen_und_neuen_buechern(client, bestand):
    angebote = [
        {"nr": 0, "titel": "Die Werft am Fluss: Roman", "autoren": ["Okke Harms"], "isbn": ["978-3-946417-71-2"], "jahr": 2021, "ausgabe": "Taschenbuch"},
        {"nr": 1, "titel": "Gärten im Schatten: Pflanzen, Planung, Pflege. 2., erweiterte Auflage", "autoren": ["Henrike Moll"], "jahr": 2022},
        {"nr": 2, "titel": "Kleine Geschichte der Leuchttürme", "autoren": ["F. Jansen"], "isbn": ["978-3-946417-93-4"]},
        {"nr": 3, "titel": "Schattengärten anlegen", "autoren": ["Bernd Kühl"]},
        {"nr": 4, "titel": "Die Werft am Fluss (Taschenbuch)"},
        {"nr": 5, "titel": "Die Inselchronik Band 3", "autoren": ["Tade Petersen"]},
    ]
    r = await client.post("/api/bestandsabgleich", json={"angebote": angebote})
    assert r.status_code == 200
    a = r.json()
    assert a["geprueft"] == 6
    t = treffer(a)
    assert t[0] == [(bestand["werft"], "vorhanden", "Titel und Autor passen")]
    assert t[1] == [(bestand["garten"], "aehnlich", "andere Auflage: 2022 statt 2014")]
    assert t[2] == [(bestand["turm"], "vorhanden", "gleiche ISBN")]
    assert 3 not in t                                                   # nichts Ähnliches: keine Marke
    assert t[4] == [(bestand["werft"], "aehnlich", "Titel gleich, ohne Autor")]   # ohne Autor nie vorhanden
    assert 5 not in t                                                   # ein anderer Band ist kein Treffer


async def test_der_einblick_traegt_buch_und_vergleich(client, bestand):
    angebot = {"nr": 7, "titel": "Gärten im Schatten: Pflanzen, Planung, Pflege. 2., erweiterte Auflage", "autoren": ["Henrike Moll"], "jahr": 2022,
               "isbn": ["978-3-946417-88-0"], "ausgabe": "Gebunden"}
    t = (await client.post("/api/bestandsabgleich", json={"angebote": [angebot]})).json()["ergebnisse"][0]["treffer"][0]
    b = t["buch"]
    assert (b["title"], b["author"], b["year"], b["formate"], b["umschlag"]) == ("Gärten im Schatten", "Henrike Moll", 2014, ["PDF"], "titelseite")
    assert 0 <= t["naehe"] <= 1 and b["gelesen"] == 0 and not b["fertig"]
    zeilen = {z["feld"]: (z["seite"], z["mein"], z["gleich"]) for z in t["vergleich"]}
    assert zeilen["Titel"][2] and zeilen["Autor"] == ("Henrike Moll", "Henrike Moll", True)
    assert zeilen["Auflage"] == ("2.", "1.", False) and zeilen["Jahr"] == ("2022", "2014", False)
    assert zeilen["ISBN"] == ("978-3-946417-88-0", "978-3-946417-62-0", False)
    assert zeilen["Format"] == ("Gebunden", "PDF", False)


async def test_die_beschreibung_kommt_ohne_auszeichnung(client, bestand):
    angebot = {"nr": 0, "titel": "Die Werft am Fluss", "autoren": ["Harms, Okke"]}
    t = (await client.post("/api/bestandsabgleich", json={"angebote": [angebot]})).json()["ergebnisse"][0]["treffer"][0]
    assert t["art"] == "vorhanden" and t["buch"]["beschreibung"] == "Drei Generationen einer Bootsbauerfamilie."


async def test_freie_suche_nach_titel_oder_name(client, bestand):
    r = (await client.post("/api/bestandsabgleich/suche", json={"text": "Geschichte der Leuchttürme"})).json()
    assert [(t["buch"]["id"], t["art"]) for t in r["treffer"]][:1] == [(bestand["turm"], "vorhanden")]
    r = (await client.post("/api/bestandsabgleich/suche", json={"text": "Okke Harms"})).json()
    assert [(t["buch"]["id"], t["art"], t["grund"]) for t in r["treffer"]] == [(bestand["werft"], "vorhanden", "Autor passt")]
    assert (await client.post("/api/bestandsabgleich/suche", json={"text": "Zeppelin"})).json() == {"treffer": []}


async def test_grenzen_der_anfrage(client, bestand):
    assert (await client.post("/api/bestandsabgleich", json={"angebote": [{"nr": 0, "titel": "x" * 501}]})).status_code == 422
    assert (await client.post("/api/bestandsabgleich", json={"angebote": [], "aehnlich_ab": 0.2})).status_code == 422
    assert (await client.post("/api/bestandsabgleich", json={"angebote": []})).json() == {"ergebnisse": [], "geprueft": 0}


async def test_ohne_anmeldung_nichts(client_ohne_auth):
    assert (await client_ohne_auth.post("/api/bestandsabgleich", json={"angebote": []})).status_code == 401
