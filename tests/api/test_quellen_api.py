"""Die Wege der API rund um die Quellen: Vergleich, Übernahme, Stand, Ergänzen, Aufnahme, gemeinfreie Bücher (BF-23)."""

import asyncio
import io

import pytest
from PIL import Image

from backend.app.annahme import angaben
from backend.app.annahme.auswertung import Ergebnis
from backend.app.core.config import settings
from backend.app.services import rescan_service
from tests.api.conftest import buch_erstellen
from tests.quellen_netz import AUSFALL, antwort, mitschnitt

STRASSENBAHN = "9783999991016"
DNB, K10, OL, CR = "services.dnb.de", "sru.k10plus.de", "openlibrary.org", "api.crossref.org"


def bild(breite=900, hoehe=1400, modus="RGB") -> bytes:
    puffer = io.BytesIO()
    Image.effect_noise((breite, hoehe), 60).convert(modus).save(puffer, format="PNG")
    return puffer.getvalue()


@pytest.fixture
def orte(tmp_path, monkeypatch):
    for ort in ("storage_dir", "umschlaege_dir"):
        monkeypatch.setattr(settings, ort, tmp_path / ort)
    monkeypatch.setattr(settings, "google_books_api_key", "")
    return tmp_path


@pytest.fixture
def quellen(netz, orte):
    netz.setze(DNB, antwort(mitschnitt("dnb_isbn.xml")))
    netz.setze(OL, antwort(mitschnitt("openlibrary_isbn.json")))
    netz.setze(K10, antwort(mitschnitt("k10plus_leer.xml")))
    netz.setze(CR, antwort({"message": {"items": []}}))
    return netz


# -- Vergleich ---------------------------------------------------------------------------------------------------------
async def test_vergleich_einer_quelle(client, test_db, quellen):
    nr = await buch_erstellen(test_db, title="Die Straßenbahn von Musterstadt", author="Beispiel, Erika", isbn="3-99999-101-1", year=None)
    r = (await client.post(f"/api/metadata/buch/{nr}/anreichern?quelle=dnb")).json()
    v = r["vorschlag"]
    assert r["angereichert"] and r["quelle"] == "dnb" and r["hinweise"] == [] and r["aktuell"]["titel"] == "Die Straßenbahn von Musterstadt"
    assert (v["titel"], v["autor"], v["jahr"], v["sprache"], v["fund"], v["isbn"]) == ("Die Straßenbahn von Musterstadt", "Erika Beispiel", 1997, "de", "isbn", "3-99999-101-1"), "die ISBN behält ihre Schreibweise"
    assert v["herkunft"]["jahr"] == "dnb" and v["raw"]["untertitel"] == "Roman" and "Belletristik" in v["kategorien"]
    assert quellen.zahl() == 1


async def test_vergleich_alle_quellen(client, test_db, quellen):
    quellen.setze("www.wikidata.org", antwort({"batchcomplete": True}))
    nr = await buch_erstellen(test_db, title="Die Straßenbahn von Musterstadt", author="Erika Beispiel", isbn=STRASSENBAHN)
    r = (await client.post(f"/api/metadata/buch/{nr}/anreichern?quelle=alle")).json()
    assert r["quelle"] == "alle" and r["vorschlag"]["herkunft"]["cover_url"] == "open_library" and r["vorschlag"]["cover_url"].endswith("-L.jpg")


async def test_grund_nichts_gefunden_und_quelle_antwortet_nicht(client, test_db, quellen):
    nr = await buch_erstellen(test_db, title="Ein ganz anderes Buch", author="Niemand", isbn="9783999999996")
    r = (await client.post(f"/api/metadata/buch/{nr}/anreichern?quelle=k10plus")).json()
    assert r == {"angereichert": False, "grund": "Verzeichnis 4 kennt dieses Buch nicht.", "hinweise": []}
    quellen.setze(DNB, AUSFALL)
    r = (await client.post(f"/api/metadata/buch/{nr}/anreichern?quelle=dnb")).json()
    assert not r["angereichert"] and r["grund"] == "Verzeichnis 3: antwortet nicht rechtzeitig"
    r = (await client.post(f"/api/metadata/buch/{nr}/anreichern?quelle=google_books")).json()
    assert r["grund"] == "Verzeichnis 1 antwortet nur mit eigenem Schlüssel (GOOGLE_BOOKS_API_KEY)"
    assert (await client.post(f"/api/metadata/buch/{nr}/anreichern?quelle=gibtesnicht")).status_code == 422
    assert (await client.post("/api/metadata/buch/99999/anreichern")).status_code == 404


async def test_fachartikel_ueber_die_doi_im_text(client, test_db, quellen):
    from backend.app.services.storage import save_fulltext

    nr = await buch_erstellen(test_db, hash="ab" * 32, title="example14539", author="", isbn="")
    save_fulltext("ab" * 32, "Sample learning\nhttps://doi.org/10.5555/example14539\n...")
    quellen.setze(CR, antwort(mitschnitt("crossref_artikel.json")))
    r = (await client.post(f"/api/metadata/buch/{nr}/anreichern?quelle=crossref")).json()
    assert r["vorschlag"]["titel"] == "Sample learning" and r["vorschlag"]["fund"] == "doi" and r["vorschlag"]["doi"] == "10.5555/example14539"


async def test_uebernehmen_mit_umschlag_und_mit_grund_wenn_er_fehlt(client, test_db, quellen):
    nr = await buch_erstellen(test_db, title="Alt", isbn=STRASSENBAHN)
    adresse = "https://covers.openlibrary.org/b/id/99000101-L.jpg"
    quellen.setze("covers.openlibrary.org", antwort(bild(modus="LA")))
    r = (await client.post(f"/api/metadata/buch/{nr}/uebernehmen", json={"titel": "Die Straßenbahn von Musterstadt", "kategorien": ["Belletristik"], "cover_url": adresse, "quelle": "open_library"})).json()
    assert r == {"uebernommen": True, "felder": ["title"], "kategorien_erstellt": 1, "cover_gespeichert": True, "hinweis": ""}
    with Image.open(next(settings.umschlaege_dir.rglob("cover.jpg"))) as b:
        assert b.width <= 800 and b.height <= 1200 and b.mode == "RGB"
    for antwort_, hinweis in ((AUSFALL, "antwortet nicht rechtzeitig"), (antwort(b"klein"), "Dort liegt kein brauchbares Bild")):
        quellen.setze("covers.openlibrary.org", antwort_)
        r = (await client.post(f"/api/metadata/buch/{nr}/uebernehmen", json={"cover_url": adresse})).json()
        assert not r["cover_gespeichert"] and r["hinweis"] == hinweis


async def test_bilder_nur_von_bekannten_quellen(client, test_db, netz, orte):
    nr = await buch_erstellen(test_db)
    for adresse in ("http://127.0.0.1:8080/geheim", "https://boese.example/bild.jpg", "file:///etc/passwd"):
        r = (await client.post(f"/api/metadata/buch/{nr}/uebernehmen", json={"cover_url": adresse})).json()
        assert not r["cover_gespeichert"] and r["hinweis"]
    assert netz.zahl() == 0


# -- Stand -------------------------------------------------------------------------------------------------------------
async def test_einstellungen_fragen_keine_quelle(client, netz, monkeypatch):
    monkeypatch.setattr(settings, "google_books_api_key", "")
    monkeypatch.setattr(settings, "crossref_enabled", False)
    alle = {q["kennung"]: q for q in (await client.get("/api/metadata/quellen")).json()}
    assert list(alle) == ["google_books", "open_library", "dnb", "k10plus", "crossref", "wikipedia", "gnd", "gutenberg"]
    assert (alle["google_books"]["bereit"], alle["google_books"]["wort"]) == (False, "Schlüssel fehlt") and alle["crossref"]["wort"] == "Aus" and alle["dnb"]["wort"] == "Noch nicht gefragt"
    kurz = (await client.get("/api/metadata/verbindungsstatus")).json()
    assert kurz["crossref"] == {"erreichbar": False, "grund": "Deaktiviert"} and not kurz["open_library"]["erreichbar"]
    assert (await client.get("/api/gutenberg/status")).json() == {"erreichbar": False, "url": "https://gutendex.com", "info": "Noch nicht gefragt"}
    assert netz.zahl() == 0


async def test_neu_pruefen_fragt_nur_die_eine_quelle(client, netz):
    netz.setze("gutendex.com", antwort(mitschnitt("gutendex_suche.json")))
    for _ in range(2):
        r = (await client.post("/api/metadata/quellen/gutenberg/pruefen")).json()
    assert r["erreichbar"] and r["anfragen_heute"] == 1 and netz.zahl() == 1
    assert (await client.post("/api/metadata/quellen/gibtesnicht/pruefen")).status_code == 404
    assert (await client.get("/api/gutenberg/status")).json()["erreichbar"]


# -- Gemeinfreie Bücher ------------------------------------------------------------------------------------------------
async def test_gemeinfreie_suche_mit_klarem_grund(client, netz):
    netz.setze("gutendex.com", antwort(mitschnitt("gutendex_suche.json")), AUSFALL)
    r = await client.get("/api/gutenberg/suche", params={"q": "Musterstadt", "sprache": "de"})
    assert r.status_code == 200 and r.json()["gesamt"] == 7 and r.json()["buecher"][0]["gutenberg_id"] == 2229
    r = await client.get("/api/gutenberg/suche", params={"q": "Zahlenreich"})
    assert r.status_code == 502 and r.json()["detail"] == "Gutendex antwortet gerade nicht, der Dienst ist überlastet. Später erneut versuchen."   # ohne eigenen Katalog (BF-98)


# -- Bibliothek ergänzen -----------------------------------------------------------------------------------------------
async def _fertig():
    for _ in range(300):
        await asyncio.sleep(0.02)
        if not rescan_service.status["laeuft"]:
            return
    raise AssertionError("Das Ergänzen endet nicht")


async def test_ergaenzen_fuellt_nur_leeres_mit_wenigen_anfragen(client, test_db, quellen):
    quellen.setze("covers.openlibrary.org", antwort(bild()))
    nr = await buch_erstellen(test_db, title="Mein Titel", author="", isbn=STRASSENBAHN, publisher="", year=None, language="", description="")
    await buch_erstellen(test_db, hash="voll", title="Voll", cover_path="cover.jpg")
    await buch_erstellen(test_db, hash="ohne", title="Ohne ISBN", isbn="")
    assert (await rescan_service.vorschau(["metadaten"]))["typen"] == {"metadaten": 1}, "nur Bücher, denen etwas fehlt"
    assert (await rescan_service.vorschau_kategorien(["metadaten"]))[0]["anzahl"] == 1
    assert (await client.post("/api/books/rescan?typen=metadaten")).json() == {"gestartet": True, "anzahl": 1}
    await _fertig()
    b = (await client.get(f"/api/books/{nr}")).json()
    assert (b["title"], b["author"], b["publisher"], b["year"], b["language"], b["cover_path"]) == ("Mein Titel", "Erika Beispiel", "Musterhaus", 1997, "de", "cover.jpg")
    assert b["categories"] == [] and rescan_service.status["metadaten_aktualisiert"] == 1 and rescan_service.status["grund"] == ""
    vorher = quellen.zahl()
    await client.post("/api/books/rescan?typen=metadaten")
    await _fertig()
    assert quellen.zahl() == vorher, "ein zweiter Lauf fragt nichts neu"


async def test_ergaenzen_hoert_auf_wenn_alle_quellen_ruhen(client, test_db, quellen):
    for rechner in (DNB, OL, K10, CR):
        quellen.setze(rechner, antwort(status=429, retry_after="900"))
    for n in range(5):
        await buch_erstellen(test_db, hash=f"b{n}", isbn=f"978399996{n}", publisher="")
    await client.post("/api/books/rescan?typen=metadaten")
    await _fertig()
    assert "macht Pause" in rescan_service.status["grund"] and all(quellen.zahl(r) <= 1 for r in (DNB, OL, K10, CR))


async def test_ergaenzen_laesst_sich_mitten_im_warten_anhalten(client, test_db, monkeypatch):
    nr = await buch_erstellen(test_db, isbn=STRASSENBAHN, publisher="")

    async def ewig(*_):
        await asyncio.sleep(60)

    monkeypatch.setattr(rescan_service, "_vorwaermen", ewig)
    await client.post("/api/books/rescan?typen=metadaten")
    await asyncio.sleep(0.05)
    assert (await client.post("/api/books/rescan/abbrechen")).json() == {"abgebrochen": True}
    await asyncio.wait_for(asyncio.gather(*rescan_service._aufgaben), 2)
    assert (await client.get(f"/api/books/{nr}")).json()["publisher"] == ""


# -- Aufnahme ----------------------------------------------------------------------------------------------------------
async def test_aufnahme_fuellt_leeres_und_behaelt_was_in_der_datei_steht(test_db, quellen):
    e = Ergebnis(title="die strassenbahn scan", isbn=STRASSENBAHN, author="", publisher="Verlag der Datei", fulltext="x")
    await angaben.ergaenzen(e, "die_strassenbahn-scan")
    assert (e.title, e.author, e.publisher, e.year, e.language, e.isbn) == ("Die Straßenbahn von Musterstadt", "Erika Beispiel", "Verlag der Datei", 1997, "de", STRASSENBAHN)


async def test_aufnahme_geht_ohne_quellen_weiter(test_db, netz, orte, monkeypatch):
    for rechner in (DNB, OL, K10, CR):
        netz.setze(rechner, AUSFALL)
    e = Ergebnis(title="Ein Titel", isbn=STRASSENBAHN, fulltext="x")
    await angaben.ergaenzen(e, "datei")
    assert (e.title, e.author) == ("Ein Titel", "")
    for schalter in ("dnb_enabled", "openlibrary_enabled", "k10plus_enabled", "crossref_enabled", "google_books_enabled"):
        monkeypatch.setattr(settings, schalter, False)
    vorher = netz.zahl()
    await angaben.ergaenzen(e, "datei")
    assert netz.zahl() == vorher
