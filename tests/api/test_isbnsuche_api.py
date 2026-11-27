"""Die Wege der ISBN-Suche (BF-111, BF-112): Kandidaten im Buch, Prüfen bei den Quellen, Angaben zu einer bestimmten ISBN, die
Quelle "Datei", das Deckblatt ins Formular, der Lauf "ISBN" mit ISBN zur Wahl. Bücher, Personen und Nummern sind erfunden."""

import asyncio
import io
import zipfile

import isbnlib
import pytest
from PIL import Image

from backend.app.core.config import settings
from backend.app.services.storage import get_storage_path, save_fulltext
from tests.api.conftest import buch_erstellen
from tests.quellen_netz import antwort, mitschnitt

STRASSENBAHN = "9783999991016"          # kennen die Mitschnitte: "Die Straßenbahn von Musterstadt" von Erika Beispiel, 1997
DNB, K10, OL, CR, WD, BILDER = "services.dnb.de", "sru.k10plus.de", "openlibrary.org", "api.crossref.org", "www.wikidata.org", "covers.openlibrary.org"


def nummer(n: int) -> str:
    kern = f"978399999{n:03d}"
    return kern + isbnlib.check_digit13(kern)


def strich(isbn: str) -> str:
    return isbnlib.mask(isbn)


@pytest.fixture
def orte(tmp_path, monkeypatch):
    for ort in ("storage_dir", "umschlaege_dir"):
        monkeypatch.setattr(settings, ort, tmp_path / ort)
    monkeypatch.setattr(settings, "google_books_api_key", "")
    return tmp_path


@pytest.fixture
def quellen(netz, orte):
    netz.setze(DNB, antwort(mitschnitt("dnb_isbn.xml")))
    netz.setze(OL, antwort({}))
    netz.setze(K10, antwort(mitschnitt("k10plus_leer.xml")))
    netz.setze(CR, antwort({"message": {"items": []}}))
    netz.setze(WD, antwort({"query": {"search": []}}))
    netz.setze(BILDER, antwort(status=404))
    return netz


async def buch_mit_text(test_db, kennung: str, seiten: list[str], **angaben) -> int:
    save_fulltext(kennung, "\f".join(seiten))
    return await buch_erstellen(test_db, hash=kennung, isbn="", page_count=len(seiten), **angaben)


def roman(titel: str, autor: str, *, impressum: str = "", anmerkungen: str = "", literatur: str = "") -> list[str]:
    seiten = ["Im Hafen von Musterstadt lag Nebel."] * 40
    seiten[0] = f"{autor}\n{titel}"
    if impressum:
        seiten[3] = f"{autor}, {titel}. © 2019 Beispielverlag. {impressum}"
    if anmerkungen:
        seiten[35] = f"Anmerkungen\n{anmerkungen}"
    if literatur:
        seiten[37] = f"Literatur\n{literatur}"
    return seiten


# -- ISBN im Buch ------------------------------------------------------------------------------------------------------
async def test_kandidaten_mit_fundstellen_statt_doppelter_formen(client, test_db, orte):
    druck, fremd = nummer(241), nummer(402)
    seiten = roman("Die Möwen von Musterstadt", "Erika Beispiel", impressum=f"ISBN {strich(druck)} (Druckausgabe)",
                   literatur=f"Brandauer, Mette: Moorkunde. 1998. ISBN {isbnlib.mask(isbnlib.to_isbn10(fremd))}\nNeuausgabe, ISBN {fremd}")
    seiten[-1] = f"ISBN {druck} 22,00 €"
    nr = await buch_mit_text(test_db, "moewen", seiten, title="Die Möwen von Musterstadt", author="Erika Beispiel")
    r = await client.post(f"/api/books/{nr}/isbn-scan")
    assert r.status_code == 200
    a = r.json()
    assert (a["funde"], a["aktuell"], a["seiten"]) == (4, "", 40)
    eigen, anders = a["kandidaten"]
    assert (eigen["isbn"], eigen["ausgabe"], eigen["fundort"], eigen["funde"], eigen["formen"]) == (strich(druck), "druck", "impressum", 2, [druck])
    assert eigen["text"] == {"stufe": "passt", "quelle": "", "basis": "im Text", "was": "Erika Beispiel, Die Möwen von Musterstadt", "warum": ""}
    assert [s["seite"] for s in eigen["stellen"]] == [4, 40] and eigen["stellen"][1]["fundort"] == "rueckseite" and eigen["quelle"] is None
    assert (anders["isbn13"], anders["funde"], anders["text"]["stufe"], len(anders["stellen"])) == (fremd, 2, "fremd", 1), "ISBN-10 und ISBN-13 sind eine Zeile"
    assert (await client.post("/api/books/9999/isbn-scan")).status_code == 404


async def test_ohne_text_im_buch_steht_keine(client, test_db, orte):
    nr = await buch_erstellen(test_db, hash="leer", isbn="")
    assert (await client.post(f"/api/books/{nr}/isbn-scan")).json() == {"kandidaten": [], "funde": 0, "aktuell": "", "seiten": 0}


async def test_pruefen_fragt_die_quellen_bis_zum_ersten_fund(client, test_db, quellen):
    eigen = await buch_erstellen(test_db, hash="bahn", title="Die Straßenbahn von Musterstadt", author="Erika Beispiel", isbn="")
    anders = await buch_erstellen(test_db, hash="knoten", title="Knoten für Musterkinder", author="Erika Beispiel", isbn="")
    p = (await client.post(f"/api/books/{eigen}/isbn-pruefen", json={"isbn": strich(STRASSENBAHN)})).json()
    assert p["einstufung"]["stufe"] == "passt" and p["einstufung"]["basis"] == "Verzeichnis 3" and p["hinweise"] == [] and quellen.zahl() == 1
    f = (await client.post(f"/api/books/{anders}/isbn-pruefen", json={"isbn": STRASSENBAHN})).json()
    assert (f["einstufung"]["stufe"], f["einstufung"]["warum"]) == ("fremd", "anderer Titel, gleicher Autor") and "<mark>Die Straßenbahn" in f["einstufung"]["was"]
    assert quellen.zahl() == 1, "die zweite Frage kommt aus dem Vorrat"
    unbekannt = (await client.post(f"/api/books/{eigen}/isbn-pruefen", json={"isbn": nummer(183)})).json()
    assert unbekannt["einstufung"] is None and not unbekannt["ruht"]
    assert (await client.post(f"/api/books/{eigen}/isbn-pruefen", json={"isbn": "9783999991017"})).status_code == 422


async def test_pruefen_sagt_wenn_die_quellen_ruhen(client, test_db, netz, orte):
    for rechner in (DNB, OL, K10, CR, WD):
        netz.setze(rechner, antwort(status=429, retry_after="600"))
    nr = await buch_erstellen(test_db, title="Die Straßenbahn von Musterstadt", isbn="")
    p = (await client.post(f"/api/books/{nr}/isbn-pruefen", json={"isbn": STRASSENBAHN})).json()
    assert p["einstufung"] is None and p["ruht"] and "Pause" in p["hinweise"][0]


# -- Angaben zu dieser ISBN --------------------------------------------------------------------------------------------
async def test_angaben_zu_einer_bestimmten_isbn(client, test_db, quellen):
    nr = await buch_erstellen(test_db, title="Knoten für Musterkinder", author="Lene Probe", isbn="")
    r = (await client.post(f"/api/metadata/buch/{nr}/anreichern?quelle=alle", json={"isbn": strich(STRASSENBAHN)})).json()
    assert r["angereichert"] and r["vorschlag"]["fund"] == "isbn" and r["vorschlag"]["isbn"] == strich(STRASSENBAHN)
    assert r["abgleich"]["stufe"] == "fremd", "das gefundene Buch ist ein anderes"
    passt = (await client.post(f"/api/metadata/buch/{nr}/anreichern?quelle=dnb", json={"isbn": STRASSENBAHN, "titel": "Die Straßenbahn von Musterstadt",
                                                                                         "autor": "Erika Beispiel"})).json()
    assert passt["abgleich"]["stufe"] == "passt", "geprüft wird gegen Titel und Autor im Formular"
    keiner = (await client.post(f"/api/metadata/buch/{nr}/anreichern", json={"isbn": nummer(183)})).json()
    assert not keiner["angereichert"] and keiner["grund"] == f"Keine Quelle kennt die ISBN {strich(nummer(183))}.", "nur über die ISBN, nie über den Titel"
    assert all("NUM=" in str(a.felder) or "isbn" in str(a.felder).lower() or "ISBN" in a.adresse for a in quellen.anfragen if "dnb" in a.adresse)
    assert (await client.post(f"/api/metadata/buch/{nr}/anreichern", json={"isbn": "12345"})).status_code == 422


def epub(pfad, kapitel: tuple[str, ...] = ("Nebel über Musterstadt. " * 30,), **meta) -> None:
    angaben = "".join(f"<dc:{k}>{w}</dc:{k}>" for k, w in meta.items())
    items = "".join(f'<item id="k{n}" href="k{n}.xhtml" media-type="application/xhtml+xml"/>' for n in range(len(kapitel)))
    spine = "".join(f'<itemref idref="k{n}"/>' for n in range(len(kapitel)))
    opf = ('<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">'
           f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">{angaben}</metadata><manifest>{items}</manifest><spine>{spine}</spine></package>')
    container = ('<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                 '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    with zipfile.ZipFile(pfad, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        for n, text in enumerate(kapitel):
            absaetze = "".join(f"<p>{zeile}</p>" for zeile in text.split("\n"))
            z.writestr(f"OEBPS/k{n}.xhtml", f"<html xmlns='http://www.w3.org/1999/xhtml'><body>{absaetze}</body></html>")


async def test_ohne_volltext_wird_er_erst_gelesen_mit_seiten(client, test_db, orte):
    """Ohne Volltext liest die Suche ihn aus der Datei; danach gelten die Seiten des Buchs, nicht eine einzige (sonst wäre alles Impressum)."""
    ordner = get_storage_path("ohnetext")
    ordner.mkdir(parents=True)
    kapitel = ("Okke Probe\nDeiche bauen in Beispielhausen", f"Okke Probe: Deiche bauen in Beispielhausen.\n© 2021 Beispielverlag\nISBN {strich(nummer(207))}",
               *("Der Deich hält die See, solange die Grasnarbe dicht bleibt. " * 30 for _ in range(10)), f"Literatur\nProbe, Autor: Beispielthema. 1990. ISBN {strich(nummer(600))}")
    epub(ordner / "deiche.epub", kapitel, title="Deiche bauen in Beispielhausen", creator="Okke Probe")
    nr = await buch_erstellen(test_db, hash="ohnetext", file_format="epub", title="Deiche bauen in Beispielhausen", author="Okke Probe", isbn="", page_count=0)
    a = (await client.post(f"/api/books/{nr}/isbn-scan")).json()
    assert [(k["isbn13"], k["fundort"], k["text"]["stufe"]) for k in a["kandidaten"]] == [(nummer(207), "impressum", "passt"), (nummer(600), "literaturliste", "fremd")]
    assert a["seiten"] > 1


async def test_quelle_datei_liest_die_angaben_neu(client, test_db, orte):
    ordner = get_storage_path("datei")
    ordner.mkdir(parents=True)
    epub(ordner / "moewen.epub", identifier=strich(nummer(255)), title="Die Möwen von Musterstadt", creator="Erika Beispiel", publisher="Beispielverlag",
         date="2019-03-01", language="de")
    nr = await buch_erstellen(test_db, hash="datei", file_format="epub", title="Möwen", author="", publisher="", year=None, isbn="")
    r = (await client.post(f"/api/metadata/buch/{nr}/anreichern?quelle=datei")).json()
    v = r["vorschlag"]
    assert r["angereichert"] and r["quelle"] == "datei" and r["abgleich"] is None
    assert (v["titel"], v["autor"], v["verlag"], v["jahr"], v["isbn"], v["sprache"], v["fund"]) == ("Die Möwen von Musterstadt", "Erika Beispiel", "Beispielverlag", 2019,
                                                                                                    strich(nummer(255)), "de", "")
    assert v["herkunft"]["verlag"] == "datei" and not v.get("seiten"), "eine EPUB nennt keine Seiten"
    ohne = await buch_erstellen(test_db, hash="fehlt", file_format="epub", isbn="")
    assert not (await client.post(f"/api/metadata/buch/{ohne}/anreichern?quelle=datei")).json()["angereichert"]


async def test_deckblatt_aus_der_datei_erst_ins_formular(client, test_db, orte):
    import fitz

    ordner = get_storage_path("blatt")
    ordner.mkdir(parents=True)
    puffer = io.BytesIO()
    Image.effect_noise((600, 900), 60).convert("RGB").save(puffer, format="PNG")
    doc = fitz.open()
    seite = doc.new_page(width=400, height=600)
    seite.insert_image(seite.rect, stream=puffer.getvalue())
    doc.save(ordner / "blatt.pdf")
    nr = await buch_erstellen(test_db, hash="blatt", isbn="", cover_path="")
    r = await client.get(f"/api/books/{nr}/cover/aus-datei")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8"
    assert (await test_db.fetch_one("SELECT cover_path FROM books WHERE id = ?", (nr,)))["cover_path"] == "", "nichts gespeichert"


# -- Lauf "ISBN" -------------------------------------------------------------------------------------------------------
async def _lauf(client) -> dict:
    assert (await client.post("/api/books/rescan", params={"typen": "isbn"})).json()["gestartet"]
    for _ in range(300):
        stand = (await client.get("/api/books/rescan/status")).json()
        if not stand["laeuft"]:
            return stand
        await asyncio.sleep(0.05)
    raise AssertionError("Der Lauf endet nicht")


def _gefragte_isbn(netz) -> set[str]:
    gefragt = set()
    for a in netz.anfragen:
        roh = str(a.felder) + a.adresse
        gefragt |= {n for n in (STRASSENBAHN, *(nummer(i) for i in range(100, 999))) if n in roh}
    return gefragt


async def test_lauf_traegt_nur_ein_was_passt(client, test_db, quellen):
    passt = await buch_mit_text(test_db, "a", roman("Die Möwen von Musterstadt", "Erika Beispiel", impressum=f"ISBN {strich(nummer(241))}"),
                                title="Die Möwen von Musterstadt", author="Erika Beispiel")
    bestaetigt = await buch_mit_text(test_db, "b", roman("Die Straßenbahn von Musterstadt", "Erika Beispiel", anmerkungen=f"1 Nach: ISBN {strich(STRASSENBAHN)}"),
                                     title="Die Straßenbahn von Musterstadt", author="Erika Beispiel")
    zur_wahl = await buch_mit_text(test_db, "c", roman("Knoten für Musterkinder", "Lene Probe", anmerkungen="\n".join(f"{n} Siehe ISBN {strich(nummer(n))}" for n in (300, 301, 302))),
                                   title="Knoten für Musterkinder", author="Lene Probe")
    nur_fremd = await buch_mit_text(test_db, "d", roman("Bernstein am Musterstrand", "Femke Probe", literatur=f"Fehrs, Jakob: Seezeichen. 2014, ISBN {strich(nummer(400))}"),
                                    title="Bernstein am Musterstrand", author="Femke Probe")
    stand = await _lauf(client)
    assert (stand["isbn_gefunden"], stand["isbn_zur_wahl"], stand["isbn_ungeprueft"], stand["isbn_grund"], stand["fehler"]) == (2, 1, 0, "", 0), stand
    isbn = {z["id"]: z["isbn"] for z in await test_db.fetch_all("SELECT id, isbn FROM books")}
    assert isbn == {passt: strich(nummer(241)), bestaetigt: strich(STRASSENBAHN), zur_wahl: "", nur_fremd: ""}
    assert _gefragte_isbn(quellen) == {STRASSENBAHN, nummer(300), nummer(301)}, "nur zu den zwei besten Funden, nie zur Literaturliste, nie bei passendem Text"

    seite = (await client.get("/api/books/rescan/isbn-wahl")).json()
    assert seite["gesamt"] == 1 and seite["zeilen"][0]["buch"]["id"] == zur_wahl and seite["zeilen"][0]["weitere"] == 2
    assert seite["zeilen"][0]["kandidat"]["isbn13"] == nummer(300) and seite["zeilen"][0]["kandidat"]["text"]["stufe"] == "unbekannt"
    assert [k["isbn13"] for k in (await client.get(f"/api/books/{zur_wahl}/isbn-wahl")).json()] == [nummer(300), nummer(301), nummer(302)]
    scan = (await client.post(f"/api/books/{zur_wahl}/isbn-scan")).json()
    assert scan["kandidaten"][0]["quelle"] is None, "keine Quelle kannte sie, darum bleibt die Stufe aus dem Text"

    assert (await client.post("/api/books/rescan/isbn-wahl/ablehnen", json={"buecher": [zur_wahl]})).json() == {"betroffen": 1}
    assert (await client.get("/api/books/rescan/isbn-wahl")).json()["gesamt"] == 0
    await _lauf(client)
    assert (await client.get("/api/books/rescan/isbn-wahl")).json()["gesamt"] == 0, "abgelehnte kommen nicht wieder"


async def test_isbn_zur_wahl_annehmen(client, test_db, netz, orte):
    for rechner in (DNB, OL, K10, CR, WD):
        netz.setze(rechner, antwort(status=429, retry_after="600"))
    nr = await buch_mit_text(test_db, "e", roman("Nebel über dem Musterpriel", "Tade Probe", anmerkungen=f"2 ISBN {strich(nummer(500))}"),
                             title="Nebel über dem Musterpriel", author="Tade Probe")
    stand = await _lauf(client)
    assert (stand["isbn_zur_wahl"], stand["isbn_ungeprueft"]) == (1, 1) and "Pause" in stand["isbn_grund"], stand
    assert (await client.post("/api/books/rescan/isbn-wahl/annehmen", json={"buecher": [nr]})).json() == {"betroffen": 1}
    assert (await test_db.fetch_one("SELECT isbn FROM books WHERE id = ?", (nr,)))["isbn"] == strich(nummer(500))
    assert (await client.get(f"/api/books/{nr}/isbn-wahl")).json() == [] and (await client.get("/api/books/rescan/isbn-wahl")).json()["gesamt"] == 0
