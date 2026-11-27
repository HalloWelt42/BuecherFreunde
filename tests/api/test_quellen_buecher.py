"""Die Anschlüsse der Buchquellen gegen Mitschnitte: Zuordnung der Felder, ISBN, Titelsuche, Fehlerwege (BF-23)."""

import json
import xml.etree.ElementTree as ET

import pytest

from backend.app.core.config import settings
from backend.app.quellen import auskunft, gutenberg, isbn, marc
from backend.app.quellen.abgleich import autor_passt, bester, isbn_fund_passt, namen_gleich, norm, suchbar, titel_naehe
from backend.app.quellen.auskunft import QUELLEN, ergaenze, suche, zusammenfuehren
from backend.app.quellen.crossref import doi_aus_text
from backend.app.quellen.fehler import Ausgefallen, Pausiert, QuelleFehler
from backend.app.quellen.google_books import GoogleBooks
from backend.app.quellen.lexikon import Lexikon
from backend.app.quellen.modelle import Angaben, Buchfrage
from backend.app.quellen.open_library import OpenLibrary
from backend.app.quellen.sachgruppen import aus_dewey, aus_dnb
from backend.app.quellen.sprache import kuerzel
from backend.app.quellen.vorrang import hintergrund
from backend.app.quellen.vorschlag import vorschlag
from backend.app.services.autorennamen import zerlegen
from tests.quellen_netz import AUSFALL, antwort, feld, mitschnitt

STRASSENBAHN = "9783999991016"
DNB, K10, OL, GB, CR, WD, WP = "services.dnb.de", "sru.k10plus.de", "openlibrary.org", "www.googleapis.com", "api.crossref.org", "www.wikidata.org", "de.wikipedia.org"


@pytest.fixture(autouse=True)
def datenbank(test_db):
    return test_db


# -- Bausteine ---------------------------------------------------------------------------------------------------------
def test_isbn_in_allen_schreibweisen():
    assert isbn.formen("3-99999-101-1") == ["9783999991016", "3999991011"] == isbn.formen("978-3-99999-101-6")
    assert isbn.mit_strichen("9783999991016") == "978-3-99999-101-6" and isbn.mit_strichen("3999991011") == "3-99999-101-1"
    assert isbn.gleich("3999991011", "978-3-99999-101-6") and not isbn.gleich("", "") and not isbn.gleich("9783999991016", "9783999991030")
    assert isbn.sauber("12345") == "" and isbn.formen("kaputt") == []
    assert isbn.deutschsprachig("3999991011") and not isbn.deutschsprachig("9780999999912")


@pytest.mark.parametrize(("wert", "ergebnis"), [("ger", "de"), ("Deutsch", "de"), ("de-DE", "de"), ("/languages/ger", "de"), ("eng", "en"), ("", ""), ("mul", ""), ("Klingonisch", "Klingonisch")])
def test_sprachen_als_kuerzel(wert, ergebnis):
    assert kuerzel(wert) == ergebnis


def test_titel_mit_untertitel_umlauten_und_baenden():
    assert titel_naehe("Tragwerk - Professionelle Webanwendungen mit Symfony", "Tragwerk", "professionelle Webanwendungen mit Symfony") >= 0.95
    assert titel_naehe("ZAHLENREICH FÜR DIE OBERSTUFE", "Zahlenreich für die Oberstufe") == 1.0
    assert titel_naehe("Zahlenreich für die Oberstufe, Band 1", "Zahlenreich für die Oberstufe, Band 2") < 0.8
    assert titel_naehe("Grundstein - Einführung in modernes PHP", "Klausurvorbereitung zu Grundstein - Einführung in modernes PHP") < 0.8
    assert norm("Größe & Maß_2") == "grosse mass 2"


def test_dateinamen_werden_nicht_gesucht():
    assert suchbar("Tragwerk") and suchbar("C++ Grundkurs")
    assert not any(map(suchbar, ("handbuch_v2_final", "Microsoft Word - Bericht.doc", "untitled", "scan0001.pdf", "ab")))


def test_autoren_vergleichen_und_zerlegen():
    assert namen_gleich("Beispiel, Erika", "Erika Beispiel") and namen_gleich("P. M. Probe", "Paula Probe") and not namen_gleich("Jürgen Mustermann", "Peter Mustermann")
    assert autor_passt(["Mustermüller, Jörg"], ["Jörg Mustermüller"]) and autor_passt(["A B"], []) is None
    assert zerlegen("Probe, Paula") == ["Paula Probe"] and zerlegen("Heinz-Peter Musterkurs, Manfred Probewinter") == ["Heinz-Peter Musterkurs", "Manfred Probewinter"]
    assert zerlegen("Musterkurs, Heinz-Peter; Probewinter, Manfred") == ["Heinz-Peter Musterkurs", "Manfred Probewinter"] and zerlegen("") == []


def test_sachgruppen():
    assert aus_dnb(["510"]) == ["Mathematik"] and aus_dnb(["59", "810", "820", "830", "839", "B"]) == ["Belletristik"] and aus_dnb(["1", "2", "3", "830"]) == []
    assert aus_dewey("005.1") == "Informatik" and aus_dewey("519") == "Mathematik" and aus_dewey("621.38") == "Elektrotechnik" and aus_dewey("SK 110") == ""


def test_doi_aus_dem_text():
    assert doi_aus_text("Siehe https://doi.org/10.5555/example14539.") == "10.5555/example14539"
    assert doi_aus_text("DOI 10.5555/978-3-99999-105-4_3, Kapitel 3") == "10.5555/978-3-99999-105-4"
    assert doi_aus_text("(doi:10.1000/abc(1))") == "10.1000/abc(1)" and doi_aus_text("Version 10.15 von 2020") == ""


# -- Nationalbibliothek und Verbundkatalog -----------------------------------------------------------------------------
async def test_dnb_nach_isbn(netz):
    netz.setze(DNB, antwort(mitschnitt("dnb_isbn.xml")))
    a = await QUELLEN["dnb"].nach_isbn("3-99999-101-1")
    assert (a.titel, a.untertitel, a.autoren, a.verlag, a.jahr, a.seiten, a.sprache, a.fund) == ("Die Straßenbahn von Musterstadt", "Roman", ["Erika Beispiel"], "Musterhaus", 1997, 206, "de", "isbn")
    assert a.kategorien[0] == "Belletristik" and "Gegenwartsliteratur ab 1945" in a.kategorien and not any("(" in k for k in a.kategorien)
    assert a.personen == {"Erika Beispiel": "999000039"}
    assert "Straßenbahn" in a.roh["freie_schlagworte"] and not any(w.startswith("(") for w in a.roh["freie_schlagworte"])
    frage = feld(netz.anfragen[0], "query")
    assert "NUM=9783999991016" in frage and "NUM=3999991011" in frage


async def test_dnb_umlaute_zusammengesetzt_band_und_auflage(netz):
    netz.setze(DNB, antwort(mitschnitt("dnb_fachbuch.xml")))
    a = await QUELLEN["dnb"].nach_isbn("9783999991047")
    assert a.titel == "Mathematik für Musterbauer und Beispielforscher, Band 1" and a.seiten == 854 and a.kategorien == ["Mathematik"]
    assert a.roh["auflage"] == "14., überarb. und erw. Aufl."
    netz.setze(DNB, antwort(mitschnitt("dnb_isbn10.xml")))
    assert (await QUELLEN["dnb"].nach_isbn("3999991038")).autoren == ["Jörg Mustermüller"]


def test_dnb_auslassung_statt_bandnummer_kommt_nicht_in_den_titel():
    # BF-17: fehlt die Nummer des Bandes, schreibt die Normdatei "[...]"
    satz = ('<record xmlns="http://www.loc.gov/MARC21/slim"><datafield tag="245" ind1="1" ind2="0"><subfield code="a">Nordlicht</subfield>'
            '<subfield code="n">{band}</subfield><subfield code="p">Die Glutwächter</subfield></datafield></record>')
    for band, titel in (("[...]", "Nordlicht"), ("[…]", "Nordlicht"), ("2", "Nordlicht, Band 2"), ("Bd. 2", "Nordlicht, Band 2")):
        a = marc.angaben(marc.Satz(ET.fromstring(satz.format(band=band))), "dnb")
        assert (a.titel, a.untertitel) == (titel, "Die Glutwächter")

async def test_dnb_nichts_und_krumme_anfrage(netz):
    netz.setze(DNB, antwort(mitschnitt("dnb_leer.xml")))
    assert await QUELLEN["dnb"].nach_isbn("9783999999996") is None and await QUELLEN["dnb"].nach_isbn("kaputt") is None
    netz.setze(DNB, antwort(mitschnitt("dnb_anfragefehler.xml")))
    with pytest.raises(Ausgefallen, match="liefert Unlesbares"):
        await QUELLEN["dnb"].nach_isbn("9783999991030")
    netz.setze(DNB, antwort("kein xml"))
    with pytest.raises(Ausgefallen):
        await QUELLEN["dnb"].nach_isbn(STRASSENBAHN)


async def test_dnb_titelsuche_waehlt_das_buch_nicht_die_sekundaerliteratur(netz):
    netz.setze(DNB, antwort(mitschnitt("dnb_titel.xml")))
    a = await QUELLEN["dnb"].nach_titel(Buchfrage(titel='Die Reise nach Beispielhausen: "Roman"', autoren=["Paula Probe"], sprache="de"))
    assert a.autoren == ["Paula Probe"] and a.fund == "titel" and a.sicher and a.titel == "Die Reise nach Beispielhausen"
    frage = feld(netz.anfragen[0], "query")
    assert frage == 'TIT="Die Reise nach Beispielhausen" and MAT=books and PER="probe" and SPR=ger'
    netz.setze(DNB, antwort(mitschnitt("dnb_titel_umlaut.xml")))
    frage = Buchfrage(titel="Einführung in die Beispielkunde", autoren=["Heinz-Peter Musterkurs", "Manfred Probewinter"], jahr=2013)
    assert (await QUELLEN["dnb"].nach_titel(frage)).verlag == "Musterdruck"
    assert await QUELLEN["dnb"].nach_titel(frage.model_copy(update={"autoren": ["Erika Beispiel"]})) is None


async def test_k10plus_fachbuch_und_englisches(netz):
    netz.setze(K10, antwort(mitschnitt("k10plus_fachbuch.xml")))
    a = await QUELLEN["k10plus"].nach_isbn("9783999991047")
    assert (a.titel, a.verlag, a.jahr, a.personen) == ("Mathematik für Musterbauer und Beispielforscher, Band 1", "Fachverlag Beispiel", 2014, {"Max Muster": "999000055"})
    netz.setze(K10, antwort(mitschnitt("k10plus_englisch.xml")))
    a = await QUELLEN["k10plus"].nach_isbn("9780999999912")
    assert (a.titel, a.sprache, a.kategorien, a.seiten) == ("Example code", "en", ["Informatik"], 431)
    netz.setze(K10, antwort(mitschnitt("k10plus_leer.xml")))
    assert await QUELLEN["k10plus"].nach_isbn("9783999999996") is None


# -- Open Library, Google, Crossref ------------------------------------------------------------------------------------
async def test_open_library_nach_isbn(netz):
    netz.setze(OL, antwort(mitschnitt("openlibrary_isbn.json")))
    a = await OpenLibrary().nach_isbn(STRASSENBAHN)
    assert (a.titel, a.autoren, a.verlag, a.jahr, a.seiten) == ("Die Straßenbahn von Musterstadt", ["Erika Beispiel"], "Musterhaus", 2000, 206)
    assert a.umschlag == "https://covers.openlibrary.org/b/id/99000101-L.jpg" and 0 < len(a.kategorien) <= 12
    assert isinstance(a.roh["subjects"][0], str) and "Deutschland" in a.roh["subject_places"], "Listen lassen sich als Regale übernehmen"
    netz.setze(OL, antwort({}))
    assert await OpenLibrary().nach_isbn("9783999999996") is None


async def test_open_library_umlaute_getrennt_geliefert(netz):
    daten = json.loads(mitschnitt("openlibrary_isbn10.json"))
    netz.setze(OL, antwort({"ISBN:9783999991030": next(iter(daten.values()))}))
    a = await OpenLibrary().nach_isbn("3999991038")
    assert a.autoren == ["Jörg Mustermüller"] and a.untertitel == "Die Geschichte eines Gärtners"


async def test_open_library_suche_nimmt_die_passende_ausgabe(netz):
    netz.setze(OL, antwort(mitschnitt("openlibrary_suche.json")))
    a = await OpenLibrary().nach_titel(Buchfrage(titel="Die Reise nach Beispielhausen", autoren=["Paula Probe"], sprache="de"))
    assert (a.isbn, a.sprache, a.jahr, a.verlag) == ("9783999991092", "de", 2009, "Beispiel-Taschenbuch-Verl.")
    assert feld(netz.anfragen[0], "lang") == "de" and "editions.isbn" in feld(netz.anfragen[0], "fields")


async def test_open_library_sammelt_viele_isbn_in_einer_anfrage(netz):
    buch = next(iter(json.loads(mitschnitt("openlibrary_isbn.json")).values()))
    netz.setze(OL, antwort({f"ISBN:{STRASSENBAHN}": buch}))
    await OpenLibrary().vorwaermen([STRASSENBAHN, "3999991038", "", "3999991011"])
    assert netz.zahl() == 1 and feld(netz.anfragen[0], "bibkeys") == f"ISBN:{STRASSENBAHN},ISBN:9783999991030"
    assert (await OpenLibrary().nach_isbn(STRASSENBAHN)).titel == "Die Straßenbahn von Musterstadt" and await OpenLibrary().nach_isbn("3999991038") is None
    await OpenLibrary().vorwaermen([STRASSENBAHN, "3999991038"])
    assert netz.zahl() == 1, "alles aus dem Vorrat"


async def test_umschlag_ueber_die_isbn_nur_wenn_es_einen_gibt(netz):
    netz.setze("covers.openlibrary.org", antwort(status=302), antwort(status=404))
    assert (await OpenLibrary().umschlag("3999991011")).endswith("/b/isbn/9783999991016-L.jpg?default=false")
    assert await OpenLibrary().umschlag("3999991038") == "" and await OpenLibrary().umschlag("") == ""
    assert {a.methode for a in netz.anfragen} == {"HEAD"}


BAND = {"volumeInfo": {"title": "Die Straßenbahn von Musterstadt", "subtitle": "Roman", "authors": ["Erika Beispiel"], "publisher": "Musterhaus", "publishedDate": "1997-05", "pageCount": 206, "language": "de",
                       "description": "<p>Ein <b>Buch</b></p>", "categories": ["Fiction / General", "Fiction / Romance"], "industryIdentifiers": [{"type": "ISBN_10", "identifier": "3999991011"}, {"type": "ISBN_13", "identifier": STRASSENBAHN}],
                       "imageLinks": {"thumbnail": "http://books.google.com/books/content?id=x&zoom=1&edge=curl&source=gbs_api"}}}


async def test_google_nur_mit_schluessel_im_kopf_und_nur_die_gefragte_isbn(netz, monkeypatch):
    monkeypatch.setattr(settings, "google_books_api_key", "geheim")
    fremd = {"volumeInfo": {"title": "Anderes", "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9783999991030"}]}}
    netz.setze(GB, antwort({"totalItems": 2, "items": [fremd, BAND]}))
    a = await GoogleBooks().nach_isbn("3999991011")
    assert (a.titel, a.isbn, a.jahr, a.beschreibung, a.kategorien) == ("Die Straßenbahn von Musterstadt", STRASSENBAHN, 1997, "Ein **Buch**", ["Fiction", "Romance"])
    assert a.umschlag == "https://books.google.com/books/content?id=x&zoom=1&source=gbs_api"
    anfrage = netz.anfragen[0]
    assert anfrage.kopf["X-Goog-Api-Key"] == "geheim" and "geheim" not in str(anfrage.felder)
    netz.setze(GB, antwort({"totalItems": 1, "items": [fremd]}))
    assert await GoogleBooks().nach_isbn("9783999991078") is None
    netz.setze(GB, antwort({"totalItems": 0}))
    assert await GoogleBooks().nach_isbn("9783999999996") is None


async def test_google_verbrauchte_tagesmenge_ruht_bis_zum_naechsten_tag(netz, monkeypatch):
    monkeypatch.setattr(settings, "google_books_api_key", "geheim")
    netz.setze(GB, antwort(mitschnitt("google_tagesmenge.json"), status=429))
    with pytest.raises(Pausiert, match="Tagesmenge des Schlüssels ist verbraucht"):
        await GoogleBooks().nach_isbn(STRASSENBAHN)
    with pytest.raises(Pausiert):
        await GoogleBooks().nach_titel(Buchfrage(titel="Die Straßenbahn von Musterstadt"))
    assert netz.zahl() == 1


async def test_crossref_artikel_buch_und_suche(netz):
    netz.setze(CR, antwort(mitschnitt("crossref_artikel.json")))
    a = await QUELLEN["crossref"].nach_doi("10.5555/example14539")
    assert (a.titel, a.autoren[0], len(a.autoren), a.jahr, a.fund) == ("Sample learning", "Sam DeSample", 3, 2015, "doi")
    assert (a.roh["zeitschrift"], a.roh["heft"], a.roh["seitenbereich"]) == ("Example Letters", "7553", "436-444")
    netz.setze(CR, antwort(mitschnitt("crossref_buch.json")))
    b = await QUELLEN["crossref"].nach_isbn("9783999991047")
    assert (b.titel, b.doi, b.autoren) == ("Mathematik für Musterbauer und Beispielforscher Band 1", "10.5555/978-3-99999-105-4", ["Max Muster"])
    netz.setze(CR, antwort(mitschnitt("crossref_artikel_deutsch.json")))
    c = await QUELLEN["crossref"].nach_titel(Buchfrage(titel="Künstliche Intelligenz im Beispielunterricht", autoren=["Sonja Beispielmann"]))
    assert c.roh["zeitschrift"] == "Beispielpädagogik" and c.beschreibung == "Worum es geht.\n\nWas dabei herauskam."
    netz.setze(CR, antwort(b"Resource not found.", status=404))
    assert await QUELLEN["crossref"].nach_doi("10.5555/x") is None


# -- Lexikon -----------------------------------------------------------------------------------------------------------
def _wikidata(*namen: str):
    """Antworten der Wikidata-Schnittstelle: Suche, Eintrag, Bezüge."""
    def beantworte(a):
        if feld(a, "generator") == "search":
            return antwort({"query": {"pages": [{"title": "Q900000201", "index": 1, "pageprops": {"wb-sitelinks": "0"}}]}})
        if feld(a, "ids") == "Q900000201":
            return antwort(mitschnitt("wikidata_ausgabe.json"))
        return antwort({"entities": {n: {"id": n, "labels": {"de": {"value": f"Name {n}"}}, "claims": {}} for n in feld(a, "ids").split("|")}})
    return beantworte


async def test_lexikon_fragt_die_isbn_mit_strichen(netz):
    netz.setze(WD, _wikidata())
    a = await Lexikon().nach_isbn("9783999991238")
    assert a.isbn == "9783999991238" and a.fund == "isbn" and a.titel and a.jahr and netz.zahl() == 3
    assert "P212=978-3-99999-123-8" in feld(netz.anfragen[0], "gsrsearch") and "P957=3-99999-123-2" in feld(netz.anfragen[0], "gsrsearch")


async def test_lexikon_fehler_mit_status_200_und_abweisung(netz):
    netz.setze(WD, antwort({"error": {"code": "maxlag", "info": "x"}}, retry_after="11.000"))
    with pytest.raises(Pausiert, match="gerade überlastet"):
        await Lexikon().nach_isbn(STRASSENBAHN)
    assert netz.zahl() == 1


async def test_lexikon_abgewiesen(netz):
    netz.setze(WD, antwort(mitschnitt("wikimedia_abgewiesen.txt"), status=403))
    with pytest.raises(Pausiert, match="Lexikon macht Pause .* weist die Anfrage ab"):
        await Lexikon().nach_isbn(STRASSENBAHN)


# -- Zusammen ----------------------------------------------------------------------------------------------------------
@pytest.fixture
def alle_antworten(netz, monkeypatch):
    monkeypatch.setattr(settings, "google_books_api_key", "")
    netz.setze(DNB, antwort(mitschnitt("dnb_isbn.xml")))
    netz.setze(OL, antwort(mitschnitt("openlibrary_isbn.json")))
    netz.setze(K10, antwort(mitschnitt("k10plus_leer.xml")))
    netz.setze(CR, antwort({"message": {"items": []}}))
    netz.setze(WD, antwort({"batchcomplete": True}))
    return netz


async def test_alle_quellen_je_feld_die_beste_mit_herkunft(alle_antworten):
    s = await suche(Buchfrage(isbn=STRASSENBAHN, titel="Die Straßenbahn von Musterstadt", autoren=["Erika Beispiel"]), auskunft.ALLE)
    a = s.angaben
    assert (a.titel, a.jahr, a.verlag) == ("Die Straßenbahn von Musterstadt", 1997, "Musterhaus")
    assert a.herkunft["titel"] == "dnb" and a.herkunft["umschlag"] == "open_library" and a.herkunft["kategorien"] == "dnb"
    assert a.quelle == "alle" and a.fund == "isbn" and s.hinweise == [] and alle_antworten.zahl(GB) == 0
    assert any(k.startswith("Verzeichnis 3, ") for k in a.roh)


async def test_faellt_eine_quelle_aus_liefern_die_uebrigen_mit_hinweis(alle_antworten):
    alle_antworten.setze(DNB, AUSFALL)
    s = await suche(Buchfrage(isbn=STRASSENBAHN, titel="Die Straßenbahn von Musterstadt"), auskunft.ALLE)
    assert s.angaben.herkunft["titel"] == "open_library" and s.hinweise == ["Verzeichnis 3: antwortet nicht rechtzeitig"] and not s.ruht


async def test_ohne_angabe_die_erste_die_etwas_weiss(alle_antworten):
    s = await suche(Buchfrage(isbn=STRASSENBAHN))
    assert s.angaben.quelle == "dnb" and alle_antworten.zahl() == 1


def test_ausgaben_werden_nicht_gemischt():
    genau = Angaben(quelle="open_library", fund="isbn", titel="Die Straßenbahn von Musterstadt", verlag="Musterhaus", isbn=STRASSENBAHN)
    andere = Angaben(quelle="dnb", fund="titel", titel="Die Straßenbahn von Musterstadt", verlag="Schulbuchverlag", jahr=2010, beschreibung="Worum es geht", seiten=99)
    a = zusammenfuehren([andere, genau], Buchfrage(isbn=STRASSENBAHN, titel="Die Straßenbahn von Musterstadt"))
    assert (a.verlag, a.jahr, a.seiten, a.beschreibung, a.herkunft["beschreibung"]) == ("Musterhaus", None, 0, "Worum es geht", "dnb")


async def test_ergaenzen_fragt_nur_so_viele_wie_noetig(alle_antworten):
    with hintergrund():
        s = await ergaenze(Buchfrage(isbn=STRASSENBAHN), {"verlag", "jahr"})
    assert s.angaben.jahr == 1997 and alle_antworten.zahl() == 1
    with hintergrund():
        s = await ergaenze(Buchfrage(isbn=STRASSENBAHN), {"umschlag"})
    assert s.angaben.umschlag and alle_antworten.zahl(OL) == 1 and alle_antworten.zahl(DNB) == 1, "DNB aus dem Vorrat"


async def test_ergaenzen_ohne_isbn_nimmt_ausgabe_nur_bei_gleichem_jahr_oder_umfang(netz):
    for rechner in (OL, K10, CR):
        netz.setze(rechner, antwort({"docs": [], "message": {"items": []}}) if rechner != K10 else antwort(mitschnitt("k10plus_leer.xml")))
    netz.setze(DNB, antwort(mitschnitt("dnb_titel.xml")))
    frage = Buchfrage(titel="Die Reise nach Beispielhausen", autoren=["Paula Probe"])
    s = await ergaenze(frage, {"isbn", "verlag", "sprache"})
    assert (s.angaben.isbn, s.angaben.verlag, s.angaben.sprache) == ("", "", "de")
    s = await ergaenze(frage.model_copy(update={"jahr": 2023}), {"isbn", "verlag"})
    assert s.angaben.isbn == "9783999991078" and s.angaben.verlag.startswith("Beispiel")


def test_ein_fund_ueber_die_isbn_muss_zum_buch_passen():
    """BF-111: eine ISBN aus dem Buch kann einem anderen gehören (Literaturliste); dann zählt ihr Fund nicht."""
    fund = Angaben(titel="Die Straßenbahn von Musterstadt", untertitel="Eine Geschichte", autoren=["Erika Beispiel"])
    passt = lambda **frage: isbn_fund_passt(Buchfrage(isbn=STRASSENBAHN, **frage), fund)    # noqa: E731
    assert passt(titel="Die Straßenbahn von Musterstadt 2021")
    assert passt(titel="Straßenbahnen in Musterstadt, ein Bildband", autoren=["Beispiel, Erika"]), "anderer Titel, gleicher Autor"
    assert not passt(titel="Kochbuch aus Beispielhausen", autoren=["Hans Fremd"]), "ein fremdes Buch aus der Literaturliste"
    assert not passt(titel="Kochbuch aus Beispielhausen"), "lesbarer Titel ohne Ähnlichkeit, kein Autor"
    assert passt(titel="scan_0001.pdf"), "ohne lesbaren Titel und Autor spricht nichts dagegen"
    assert passt(titel="scan_0001.pdf", autoren=["Unbekannt"]), "ein Platzhalter ist kein Autor"
    assert not passt(titel="scan_0001.pdf", autoren=["Hans Fremd"])


async def test_ergaenzen_verwirft_den_fund_einer_fremden_isbn(alle_antworten):
    with hintergrund():
        fremd = await ergaenze(Buchfrage(isbn=STRASSENBAHN, titel="Kochbuch aus Beispielhausen", autoren=["Hans Fremd"]), {"verlag", "jahr"})
        eigen = await ergaenze(Buchfrage(isbn=STRASSENBAHN, titel="Die Straßenbahn von Musterstadt"), {"verlag", "jahr"})
    assert fremd.angaben is None and eigen.angaben.jahr == 1997


@pytest.mark.parametrize("k10_antwortet", [False, True])
async def test_ergaenzen_ruht_erst_wenn_alle_gefragten_ruhen(netz, k10_antwortet):
    for rechner in (DNB, OL, K10, CR):
        netz.setze(rechner, antwort(status=429, retry_after="600"))
    if k10_antwortet:
        netz.setze(K10, antwort(mitschnitt("k10plus_leer.xml")))
    s = await ergaenze(Buchfrage(isbn=STRASSENBAHN), {"jahr"})
    assert s.ruht is not k10_antwortet and s.angaben is None and len(s.hinweise) == (3 if k10_antwortet else 4)


def test_bester_verwirft_unpassendes():
    frage = Buchfrage(titel="Die Straßenbahn von Musterstadt", autoren=["Erika Beispiel"])
    assert bester(frage, []) is None
    assert bester(frage, [Angaben(titel="Die Straßenbahn von Musterstadt", autoren=["Peter Anders"]), Angaben(titel="Ganz anderes", autoren=["Erika Beispiel"])]) is None
    assert bester(Buchfrage(titel="Grundstein"), [Angaben(titel="Grundstein und seine Zeit")]) is None


def test_vorschlag_behaelt_titel_mit_untertitel_und_schreibweise_der_isbn():
    a = Angaben(quelle="dnb", fund="isbn", titel="Grundstein", untertitel="modernes PHP für Einsteiger", autoren=["HalloWelt42"], isbn="9783999991269", herkunft={"autoren": "dnb", "umschlag": "open_library"})
    v = vorschlag(a, {"title": "Grundstein - Modernes PHP für Einsteiger"})
    assert v["titel"] == "Grundstein - Modernes PHP für Einsteiger" and v["raw"]["untertitel"] and v["herkunft"] == {"autor": "dnb", "cover_url": "open_library"}
    assert vorschlag(a, {"title": "GRUNDSTEIN"})["titel"] == "Grundstein"


# -- Gemeinfreie Bücher ------------------------------------------------------------------------------------------------
async def test_gemeinfreie_suche_und_seite_hinter_der_letzten(netz):
    netz.setze("gutendex.com", antwort(mitschnitt("gutendex_suche.json")), antwort({"detail": "Invalid page."}, status=404))
    liste = await gutenberg.suche("Musterstadt", " DE, en ")
    erstes = liste.buecher[0]
    assert (liste.gesamt, erstes.autor, erstes.download_format, erstes.sprachen) == (7, "Beispiel, Erika", "epub", ["de"])
    assert dict(netz.anfragen[0].felder) == {"search": "Musterstadt", "languages": "de,en"}
    assert (await gutenberg.suche("Musterstadt", "de", seite=99)).buecher == []


async def test_gemeinfreie_dateien_kommen_von_den_spiegeln(netz):
    netz.setze("gutenberg.pglaf.org", antwort("<html>Fehler</html>"))
    netz.setze("aleph.pglaf.org", antwort(b"PK\x03\x04inhalt"))
    pfad = await gutenberg.download_buch(2229, "https://www.gutenberg.org/ebooks/2229.epub3.images")
    assert pfad.suffix == ".epub" and pfad.read_bytes().startswith(b"PK") and not any("www.gutenberg.org" in a.adresse for a in netz.anfragen)
    pfad.unlink()
    netz.setze("aleph.pglaf.org", antwort(status=404))
    with pytest.raises(QuelleFehler):
        await gutenberg.download_buch(2229, "https://www.gutenberg.org/ebooks/2229.epub3.images")
    with pytest.raises(QuelleFehler, match="keine Datei"):
        await gutenberg.download_buch(1, "")
