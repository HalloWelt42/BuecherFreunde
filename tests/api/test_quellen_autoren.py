"""Autoren aus Normdatei und Lexikon: der Weg über die ISBN, mehrdeutige Namen, Sicherheit, Übernahme, Abgleich (BF-23)."""

import json

import pytest

from backend.app.core.config import settings
from backend.app.quellen import autoren, gnd, wiki
from backend.app.quellen.autoren import suchname, suche
from backend.app.quellen.modelle import Autorfrage
from backend.app.services import autoren_uebernahme as uebernahme
from tests.api.conftest import buch_erstellen
from tests.quellen_netz import AUSFALL, antwort, feld, mitschnitt

DNB, K10, GND, WD, WP = "services.dnb.de", "sru.k10plus.de", "lobid.org", "www.wikidata.org", "de.wikipedia.org"
STRASSENBAHN = "9783999991016"
BEISPIEL = Autorfrage(name="Beispiel, Erika", titel=["Die Straßenbahn von Musterstadt"], isbns=[STRASSENBAHN])


def _wikidata(a):
    """Suche, Eintrag Beispiel, sonst Bezüge (Werke, Land) mit Namen."""
    if feld(a, "generator") == "search":
        return antwort(mitschnitt("wikidata_mensch.json"))
    if feld(a, "ids") == "Q900000101":
        return antwort(mitschnitt("wikidata_person.json"))
    namen = {"Q183": "Deutschland", "Q900000102": "Die Straßenbahn von Musterstadt"}
    return antwort({"entities": {n: {"id": n, "labels": {"de": {"value": namen.get(n, f"Werk {n}")}}, "claims": {}} for n in feld(a, "ids").split("|")}})


def _gnd(a):
    q = feld(a, "q")
    return antwort(mitschnitt("gnd_suche.json")) if "999000039" in q or "Beispiel" in q else antwort(mitschnitt("gnd_leer.json"))


@pytest.fixture
def quellen(test_db, netz):
    netz.setze(DNB, antwort(mitschnitt("dnb_isbn.xml")))
    netz.setze(K10, antwort(mitschnitt("k10plus_leer.xml")))
    netz.setze(GND, _gnd)
    netz.setze(WD, _wikidata)
    netz.setze(WP, antwort(mitschnitt("wikipedia_artikel.json")))
    return netz


# -- Suche -------------------------------------------------------------------------------------------------------------
async def test_ueber_die_isbn_steht_der_autor_fest(quellen):
    s = await suche(BEISPIEL)
    a = s.angaben
    assert (a.name, a.wikidata_id, a.birth_year, a.nationality, a.konfidenz) == ("Erika Beispiel", "Q900000101", 1944, "Deutschland", "hoch")
    assert a.verweise["gnd"] == "999000039" and a.verweise["viaf"] == "99900001" and a.verweise["isni"]
    assert "Die Straßenbahn von Musterstadt" in [w.titel for w in a.werke] and a.photo_url.endswith("?width=500")
    assert a.biography.startswith("Erika Beispiel ist") and "## Leben" in a.biography and "### Lehre" in a.biography and "Liste" not in a.biography and "Verweis" not in a.biography
    assert s.hinweise == [] and a.herkunft["biography"] == "wikidata"
    assert quellen.zahl(DNB) == 1 and quellen.zahl(GND) == 1 and quellen.zahl(WD) + quellen.zahl(WP) == 3, "wenige Anfragen je Autor"
    await suche(BEISPIEL)
    assert quellen.zahl() == 5, "ein zweites Mal alles aus dem Vorrat"


async def test_ohne_lexikon_kommt_das_meiste_aus_der_normdatei(quellen, monkeypatch):
    monkeypatch.setattr(settings, "wikipedia_enabled", False)
    a = (await suche(BEISPIEL)).angaben
    assert (a.name, a.birth_year, a.quelle, a.konfidenz, a.wikidata_id) == ("Erika Beispiel", 1944, "gnd", "hoch", "Q900000101") and a.beschreibung
    assert quellen.zahl(WD) == 0


async def test_fachautor_ohne_artikel(test_db, netz):
    netz.setze(DNB, antwort(mitschnitt("dnb_fachbuch.xml")))
    netz.setze(GND, antwort(mitschnitt("gnd_person.json")))
    netz.setze(WD, antwort({"batchcomplete": True}))
    a = (await suche(Autorfrage(name="Max Muster", titel=["Mathematik für Musterbauer"], isbns=["9783999991047"]))).angaben
    assert a.beschreibung.startswith("Mathematiker, Hochschullehrer; Professor für Mathematik") and a.birth_year == 1941 and a.konfidenz == "hoch" and a.verweise["gnd"] == "999000055"


async def test_mehrdeutiger_name_gilt_nicht_ohne_beleg(test_db, netz):
    netz.setze(GND, antwort(mitschnitt("gnd_mehrdeutig.json")))
    netz.setze(WD, antwort({"batchcomplete": True}))
    assert (await suche(Autorfrage(name="Jürgen Mustermann", titel=["Ein anderes Buch"]))).angaben is None
    a = (await suche(Autorfrage(name="Jürgen Mustermann", titel=["Güterverkehr im Beispieltal"]))).angaben
    assert a.verweise["gnd"] == "9990000565" and a.konfidenz == "hoch" and a.beschreibung == "Wirtschaftswissenschaftler"


async def test_nur_namensgleich_ist_nicht_sicher(test_db, netz):
    netz.setze(GND, antwort(mitschnitt("gnd_leer.json")))
    zwei = json.loads(mitschnitt("wikidata_person.json"))
    zwei["entities"]["Q2"] = {**zwei["entities"]["Q900000101"], "id": "Q2"}

    def wikidata(a):
        if feld(a, "generator") == "search":
            return antwort({"query": {"pages": [{"title": "Q900000101", "index": 1, "pageprops": {"wb-sitelinks": "30"}}, {"title": "Q2", "index": 2}]}})
        return antwort(zwei) if "Q900000101" in feld(a, "ids") else _wikidata(a)

    netz.setze(WD, wikidata)
    netz.setze(WP, antwort(mitschnitt("wikipedia_artikel.json")))
    a = (await suche(Autorfrage(name="Erika Beispiel", titel=["Kochen für Anfänger"]))).angaben
    assert a.score >= 15 and a.konfidenz == "mittel", "zwei Menschen dieses Namens, kein Buch als Beleg"
    assert (await suche(Autorfrage(name="Erika Beispiel", titel=["Die Straßenbahn von Musterstadt"]))).angaben.konfidenz == "hoch"


async def test_ausfall_einer_quelle_steht_im_hinweis(quellen):
    quellen.setze(WD, antwort(status=429, retry_after="60"))
    s = await suche(BEISPIEL)
    assert s.ruht and s.angaben.quelle == "gnd" and s.hinweise[0].startswith("Lexikon macht Pause")
    quellen.setze(GND, AUSFALL)
    s = await suche(Autorfrage(name="Jemand Anderes"))
    assert s.angaben is None and len(s.hinweise) == 2


async def test_beides_abgeschaltet(test_db, netz, monkeypatch):
    monkeypatch.setattr(settings, "wikipedia_enabled", False)
    monkeypatch.setattr(settings, "gnd_enabled", False)
    assert (await suche(BEISPIEL)).hinweise == ["Lexikon und Normdatei sind abgeschaltet"] and netz.zahl() == 0


def test_suchname():
    assert suchname("Beispiel, Erika") == "Erika Beispiel" and suchname("Muster, E.T.A. (Hrsg.)") == "E. T. A. Muster" and suchname(" Anna Probe; ") == "Anna Probe"


def test_werte_eines_eintrags():
    def zeit(t, genau=11, rang="normal"):
        return {"rank": rang, "mainsnak": {"datavalue": {"type": "time", "value": {"time": t, "precision": genau}}}}

    assert wiki._werte([zeit("-0427-00-00T00:00:00Z", 9)]) == [-427]
    assert wiki._werte([zeit("+1800-00-00T00:00:00Z", 7)]) == [], "nur das Jahrhundert ist kein Jahr"
    assert wiki._werte([zeit("+1900-01-01T00:00:00Z", rang="deprecated"), zeit("+1901-01-01T00:00:00Z"), zeit("+1902-01-01T00:00:00Z", rang="preferred")]) == [1902, 1901]
    assert wiki._werte([{"rank": "normal", "mainsnak": {}}]) == []


def test_buchtext_ist_einleitung_und_inhalt():
    text = "Ein Roman.\n\n\n== Inhalt ==\n\nEs geschieht etwas.\n\n\n== Rezeption ==\n\nViel Lob."
    assert wiki.buchtext(text) == "Ein Roman.\n\nEs geschieht etwas."


async def test_normdatei_kennung_muss_wie_eine_aussehen(test_db, netz):
    assert await gnd.person('1" OR *') is None and netz.zahl() == 0


# -- Übernahme ---------------------------------------------------------------------------------------------------------
async def _autor(db, name: str, buecher: list[int] = []) -> int:  # noqa: B006
    c = await db.execute("INSERT INTO authors (name, slug) VALUES (?, ?)", (name, uebernahme.slug(name)))
    for b in buecher:
        await db.execute("INSERT INTO book_authors (book_id, author_id) VALUES (?, ?)", (b, c.lastrowid))
    await db.commit()
    return c.lastrowid


async def test_uebernehmen_mit_verweisen_werken_und_belegtem_slug(client, test_db, auth_headers):
    buch = await buch_erstellen(test_db, title="Die Straßenbahn von Musterstadt", isbn=STRASSENBAHN)
    await buch_erstellen(test_db, hash="fremd", title="Die Straßenbahn von Musterstadt, Interpretation", isbn="")
    nr, anderer = await _autor(test_db, "E. Beispiel", [buch]), await _autor(test_db, "Erika Beispiel")
    felder = {"name": "Erika Beispiel", "birth_year": 1944, "verweise": {"gnd": "999000039", "viaf": "99900001", "orcid": "<krumm>"}, "werke": [{"titel": "Die Straßenbahn von Musterstadt", "wikidata_id": "Q1"}, {"titel": "Er"}]}
    r = (await client.post(f"/api/authors/{nr}/anreichern/uebernehmen", json=felder)).json()
    assert r["uebernommen"] and r["werke_gespeichert"] == 2 and "gnd" in r["felder"] and "slug" not in r["felder"]
    a = (await client.get(f"/api/authors/{nr}")).json()
    assert [(v["art"], v["adresse"]) for v in a["verweise"]] == [("gnd", "https://d-nb.info/gnd/999000039"), ("viaf", "https://viaf.org/viaf/99900001")]
    assert {w["titel"]: w["book_id"] for w in a["werke"]} == {"Die Straßenbahn von Musterstadt": buch, "Er": None}, "nur Bücher dieses Autors, kurze Titel nur ganz gleich"
    assert (await client.get("/api/authors/statistik/uebersicht")).json()["mit_normdatei"] == 1
    r = (await client.post(f"/api/authors/{anderer}/anreichern/uebernehmen", json={"verweise": {"gnd": "999000039"}})).json()
    assert r["zusammengefuehrt"] and r["ziel_autor_id"] == nr and (await client.get(f"/api/authors/{anderer}")).status_code == 404


async def test_anreichern_zeigt_vorschlag_und_aendert_nichts(client, test_db, quellen):
    buch = await buch_erstellen(test_db, title="Die Straßenbahn von Musterstadt", isbn=STRASSENBAHN)
    nr = await _autor(test_db, "Erika Beispiel", [buch])
    r = (await client.post(f"/api/authors/{nr}/anreichern")).json()
    assert r["angereichert"] and r["vorschlag"]["verweise"]["gnd"] and r["aktuell"]["verweise"] == {} and r["buecher_im_system"][0]["id"] == buch
    assert (await client.get(f"/api/authors/{nr}")).json()["wikidata_id"] == ""


async def _abgleich(client, weg="/api/authors/scanner/events?auto_uebernehmen=true"):
    r = await client.get(weg)
    return [json.loads(z[6:]) for z in r.text.splitlines() if z.startswith("data: ")]


async def test_abgleich_uebernimmt_sicheres_und_fragt_beim_naechsten_mal_nicht_mehr(client, test_db, quellen):
    buch = await buch_erstellen(test_db, title="Die Straßenbahn von Musterstadt", isbn=STRASSENBAHN)
    nr = await _autor(test_db, "Erika Beispiel", [buch])
    quellen.setze("commons.wikimedia.org", antwort(b"kein bild" * 200))
    e = await _abgleich(client)
    assert [x["typ"] for x in e] == ["start", "suche", "gefunden", "fertig"] and e[2]["uebernommen"] and e[3]["gefunden"] == 1
    assert (await client.get(f"/api/authors/{nr}")).json()["wikidata_id"] == "Q900000101"
    assert (await _abgleich(client))[0]["gesamt"] == 0
    assert (await autoren_hintergrund()) > 0


async def autoren_hintergrund() -> int:
    from backend.app.quellen.abruf import abruf

    return (await abruf().zustaende.von("wikipedia")).hintergrund


async def test_abgleich_endet_mit_grund_wenn_eine_quelle_ruht(client, test_db, quellen):
    for n in range(3):
        await _autor(test_db, f"Autor Nummer{n}", [await buch_erstellen(test_db, hash=f"h{n}", isbn="")])
    quellen.setze(WD, antwort(status=429, retry_after="600"))
    e = await _abgleich(client)
    assert [x["typ"] for x in e] == ["start", "suche", "ruht"] and "Lexikon macht Pause" in e[-1]["grund"]
    assert quellen.zahl(WD) == 1


async def test_abgleich_haelt_mitten_im_warten_an(client, test_db, monkeypatch):
    import asyncio

    from backend.app.api import authors

    await _autor(test_db, "Langsamer Autor", [await buch_erstellen(test_db)])

    async def ewig(_frage):
        await asyncio.sleep(60)

    monkeypatch.setattr(autoren, "suche", ewig)
    lauf = asyncio.create_task(_abgleich(client))
    for _ in range(100):
        await asyncio.sleep(0.01)
        if authors._batch_scan_status["laeuft"] and authors._batch_scan_status["fortschritt"]:
            break
    assert (await client.post("/api/authors/scanner/abbrechen")).json()["abgebrochen"]
    e = await asyncio.wait_for(lauf, 2)
    assert e[-1]["typ"] == "abgebrochen" and not authors._batch_scan_status["laeuft"]


async def test_neubilden_behaelt_autoren_mit_normdatei(client, test_db):
    buch = await buch_erstellen(test_db, author="Max Muster")
    nr = await _autor(test_db, "Max Muster", [buch])
    weg = await _autor(test_db, "Verwaist")
    await uebernahme.verweise_setzen(nr, {"gnd": "999000055"})
    r = (await client.post("/api/authors/resync")).json()
    assert r["beibehalten"] == 1 and (await client.get(f"/api/authors/{nr}")).status_code == 200 and (await client.get(f"/api/authors/{weg}")).status_code == 404
