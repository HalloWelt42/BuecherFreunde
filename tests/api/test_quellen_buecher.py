"""Die Anschlüsse der Buchquellen gegen Mitschnitte: Zuordnung der Felder, ISBN, Titelsuche, Fehlerwege (BF-23)."""

import json

import pytest

from backend.app.core.config import settings
from backend.app.quellen import auskunft, gutenberg, isbn
from backend.app.quellen.abgleich import autor_passt, bester, namen_gleich, norm, suchbar, titel_naehe
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

VORLESER = "9783257229530"
DNB, K10, OL, GB, CR, WD, WP = "services.dnb.de", "sru.k10plus.de", "openlibrary.org", "www.googleapis.com", "api.crossref.org", "www.wikidata.org", "de.wikipedia.org"


@pytest.fixture(autouse=True)
def datenbank(test_db):
    return test_db


# -- Bausteine ---------------------------------------------------------------------------------------------------------
def test_isbn_in_allen_schreibweisen():
    assert isbn.formen("3-257-22953-4") == ["9783257229530", "3257229534"] == isbn.formen("978-3-257-22953-0")
    assert isbn.mit_strichen("9783257229530") == "978-3-257-22953-0" and isbn.mit_strichen("3257229534") == "3-257-22953-4"
    assert isbn.gleich("3257229534", "978-3-257-22953-0") and not isbn.gleich("", "") and not isbn.gleich("9783257229530", "9783257228007")
    assert isbn.sauber("12345") == "" and isbn.formen("kaputt") == []
    assert isbn.deutschsprachig("3257229534") and not isbn.deutschsprachig("9780132350884")


@pytest.mark.parametrize(("wert", "ergebnis"), [("ger", "de"), ("Deutsch", "de"), ("de-DE", "de"), ("/languages/ger", "de"), ("eng", "en"), ("", ""), ("mul", ""), ("Klingonisch", "Klingonisch")])
def test_sprachen_als_kuerzel(wert, ergebnis):
    assert kuerzel(wert) == ergebnis


def test_titel_mit_untertitel_umlauten_und_baenden():
    assert titel_naehe("Python 3 - Das umfassende Handbuch", "Python 3", "das umfassende Handbuch") >= 0.95
    assert titel_naehe("EINFÜHRUNG IN DIE INFORMATIK", "Einführung in die Informatik") == 1.0
    assert titel_naehe("Mathematik für Ingenieure, Band 1", "Mathematik für Ingenieure, Band 2") < 0.8
    assert titel_naehe("Einführung in die Informatik", "Klausurvorbereitung zur Einführung in die Informatik") < 0.8
    assert norm("Größe & Maß_2") == "grosse mass 2"


def test_dateinamen_werden_nicht_gesucht():
    assert suchbar("Der Vorleser") and suchbar("C++ Primer")
    assert not any(map(suchbar, ("handbuch_v2_final", "Microsoft Word - Bericht.doc", "untitled", "scan0001.pdf", "ab")))


def test_autoren_vergleichen_und_zerlegen():
    assert namen_gleich("Schlink, Bernhard", "Bernhard Schlink") and namen_gleich("J. K. Rowling", "Joanne Rowling") and not namen_gleich("Thomas Müller", "Peter Müller")
    assert autor_passt(["Süskind, Patrick"], ["Patrick Süskind"]) and autor_passt(["A B"], []) is None
    assert zerlegen("Kehlmann, Daniel") == ["Daniel Kehlmann"] and zerlegen("Heinz-Peter Gumm, Manfred Sommer") == ["Heinz-Peter Gumm", "Manfred Sommer"]
    assert zerlegen("Gumm, Heinz-Peter; Sommer, Manfred") == ["Heinz-Peter Gumm", "Manfred Sommer"] and zerlegen("") == []


def test_sachgruppen():
    assert aus_dnb(["510"]) == ["Mathematik"] and aus_dnb(["59", "810", "820", "830", "839", "B"]) == ["Belletristik"] and aus_dnb(["1", "2", "3", "830"]) == []
    assert aus_dewey("005.1") == "Informatik" and aus_dewey("519") == "Mathematik" and aus_dewey("621.38") == "Elektrotechnik" and aus_dewey("SK 110") == ""


def test_doi_aus_dem_text():
    assert doi_aus_text("Siehe https://doi.org/10.1038/nature14539.") == "10.1038/nature14539"
    assert doi_aus_text("DOI 10.1007/978-3-658-05620-9_3, Kapitel 3") == "10.1007/978-3-658-05620-9"
    assert doi_aus_text("(doi:10.1000/abc(1))") == "10.1000/abc(1)" and doi_aus_text("Version 10.15 von 2020") == ""


# -- Nationalbibliothek und Verbundkatalog -----------------------------------------------------------------------------
async def test_dnb_nach_isbn(netz):
    netz.setze(DNB, antwort(mitschnitt("dnb_isbn.xml")))
    a = await QUELLEN["dnb"].nach_isbn("3-257-22953-4")
    assert (a.titel, a.untertitel, a.autoren, a.verlag, a.jahr, a.seiten, a.sprache, a.fund) == ("Der Vorleser", "Roman", ["Bernhard Schlink"], "Diogenes", 1997, 206, "de", "isbn")
    assert a.kategorien[0] == "Belletristik" and "Gegenwartsliteratur ab 1945" in a.kategorien and not any("(" in k for k in a.kategorien)
    assert a.personen == {"Bernhard Schlink": "115673784"}
    assert "Straßenbahn" in a.roh["freie_schlagworte"] and not any(w.startswith("(") for w in a.roh["freie_schlagworte"])
    frage = feld(netz.anfragen[0], "query")
    assert "NUM=9783257229530" in frage and "NUM=3257229534" in frage


async def test_dnb_umlaute_zusammengesetzt_band_und_auflage(netz):
    netz.setze(DNB, antwort(mitschnitt("dnb_fachbuch.xml")))
    a = await QUELLEN["dnb"].nach_isbn("9783658056193")
    assert a.titel == "Mathematik für Ingenieure und Naturwissenschaftler, Band 1" and a.seiten == 854 and a.kategorien == ["Mathematik"]
    assert a.roh["auflage"] == "14., überarb. und erw. Aufl."
    netz.setze(DNB, antwort(mitschnitt("dnb_isbn10.xml")))
    assert (await QUELLEN["dnb"].nach_isbn("3257228007")).autoren == ["Patrick Süskind"]


async def test_dnb_nichts_und_krumme_anfrage(netz):
    netz.setze(DNB, antwort(mitschnitt("dnb_leer.xml")))
    assert await QUELLEN["dnb"].nach_isbn("9783999999996") is None and await QUELLEN["dnb"].nach_isbn("kaputt") is None
    netz.setze(DNB, antwort(mitschnitt("dnb_anfragefehler.xml")))
    with pytest.raises(Ausgefallen, match="liefert Unlesbares"):
        await QUELLEN["dnb"].nach_isbn("9783257228007")
    netz.setze(DNB, antwort("kein xml"))
    with pytest.raises(Ausgefallen):
        await QUELLEN["dnb"].nach_isbn(VORLESER)


async def test_dnb_titelsuche_waehlt_das_buch_nicht_die_sekundaerliteratur(netz):
    netz.setze(DNB, antwort(mitschnitt("dnb_titel.xml")))
    a = await QUELLEN["dnb"].nach_titel(Buchfrage(titel='Die Vermessung der Welt: "Roman"', autoren=["Daniel Kehlmann"], sprache="de"))
    assert a.autoren == ["Daniel Kehlmann"] and a.fund == "titel" and a.sicher and a.titel == "Die Vermessung der Welt"
    frage = feld(netz.anfragen[0], "query")
    assert frage == 'TIT="Die Vermessung der Welt" and MAT=books and PER="kehlmann" and SPR=ger'
    netz.setze(DNB, antwort(mitschnitt("dnb_titel_umlaut.xml")))
    frage = Buchfrage(titel="Einführung in die Informatik", autoren=["Heinz-Peter Gumm", "Manfred Sommer"], jahr=2013)
    assert (await QUELLEN["dnb"].nach_titel(frage)).verlag == "Oldenbourg"
    assert await QUELLEN["dnb"].nach_titel(frage.model_copy(update={"autoren": ["Erika Beispiel"]})) is None


async def test_k10plus_fachbuch_und_englisches(netz):
    netz.setze(K10, antwort(mitschnitt("k10plus_fachbuch.xml")))
    a = await QUELLEN["k10plus"].nach_isbn("9783658056193")
    assert (a.titel, a.verlag, a.jahr, a.personen) == ("Mathematik für Ingenieure und Naturwissenschaftler, Band 1", "Springer Vieweg", 2014, {"Lothar Papula": "106931628"})
    netz.setze(K10, antwort(mitschnitt("k10plus_englisch.xml")))
    a = await QUELLEN["k10plus"].nach_isbn("9780132350884")
    assert (a.titel, a.sprache, a.kategorien, a.seiten) == ("Clean code", "en", ["Informatik"], 431)
    netz.setze(K10, antwort(mitschnitt("k10plus_leer.xml")))
    assert await QUELLEN["k10plus"].nach_isbn("9783999999996") is None


# -- Open Library, Google, Crossref ------------------------------------------------------------------------------------
async def test_open_library_nach_isbn(netz):
    netz.setze(OL, antwort(mitschnitt("openlibrary_isbn.json")))
    a = await OpenLibrary().nach_isbn(VORLESER)
    assert (a.titel, a.autoren, a.verlag, a.jahr, a.seiten) == ("Der Vorleser", ["Bernhard Schlink"], "Diogenes", 2000, 206)
    assert a.umschlag == "https://covers.openlibrary.org/b/id/10527919-L.jpg" and 0 < len(a.kategorien) <= 12
    assert isinstance(a.roh["subjects"][0], str) and "Deutschland" in a.roh["subject_places"], "Listen lassen sich als Regale übernehmen"
    netz.setze(OL, antwort({}))
    assert await OpenLibrary().nach_isbn("9783999999996") is None


async def test_open_library_umlaute_getrennt_geliefert(netz):
    daten = json.loads(mitschnitt("openlibrary_isbn10.json"))
    netz.setze(OL, antwort({"ISBN:9783257228007": next(iter(daten.values()))}))
    a = await OpenLibrary().nach_isbn("3257228007")
    assert a.autoren == ["Patrick Süskind"] and a.untertitel == "Die Geschichte eines Mörders"


async def test_open_library_suche_nimmt_die_passende_ausgabe(netz):
    netz.setze(OL, antwort(mitschnitt("openlibrary_suche.json")))
    a = await OpenLibrary().nach_titel(Buchfrage(titel="Die Vermessung der Welt", autoren=["Daniel Kehlmann"], sprache="de"))
    assert (a.isbn, a.sprache, a.jahr, a.verlag) == ("9783499332708", "de", 2009, "Rowohlt-Taschenbuch-Verl.")
    assert feld(netz.anfragen[0], "lang") == "de" and "editions.isbn" in feld(netz.anfragen[0], "fields")


async def test_open_library_sammelt_viele_isbn_in_einer_anfrage(netz):
    buch = next(iter(json.loads(mitschnitt("openlibrary_isbn.json")).values()))
    netz.setze(OL, antwort({f"ISBN:{VORLESER}": buch}))
    await OpenLibrary().vorwaermen([VORLESER, "3257228007", "", "3257229534"])
    assert netz.zahl() == 1 and feld(netz.anfragen[0], "bibkeys") == f"ISBN:{VORLESER},ISBN:9783257228007"
    assert (await OpenLibrary().nach_isbn(VORLESER)).titel == "Der Vorleser" and await OpenLibrary().nach_isbn("3257228007") is None
    await OpenLibrary().vorwaermen([VORLESER, "3257228007"])
    assert netz.zahl() == 1, "alles aus dem Vorrat"


async def test_umschlag_ueber_die_isbn_nur_wenn_es_einen_gibt(netz):
    netz.setze("covers.openlibrary.org", antwort(status=302), antwort(status=404))
    assert (await OpenLibrary().umschlag("3257229534")).endswith("/b/isbn/9783257229530-L.jpg?default=false")
    assert await OpenLibrary().umschlag("3257228007") == "" and await OpenLibrary().umschlag("") == ""
    assert {a.methode for a in netz.anfragen} == {"HEAD"}


BAND = {"volumeInfo": {"title": "Der Vorleser", "subtitle": "Roman", "authors": ["Bernhard Schlink"], "publisher": "Diogenes", "publishedDate": "1997-05", "pageCount": 206, "language": "de",
                       "description": "<p>Ein <b>Buch</b></p>", "categories": ["Fiction / General", "Fiction / Romance"], "industryIdentifiers": [{"type": "ISBN_10", "identifier": "3257229534"}, {"type": "ISBN_13", "identifier": VORLESER}],
                       "imageLinks": {"thumbnail": "http://books.google.com/books/content?id=x&zoom=1&edge=curl&source=gbs_api"}}}


async def test_google_nur_mit_schluessel_im_kopf_und_nur_die_gefragte_isbn(netz, monkeypatch):
    monkeypatch.setattr(settings, "google_books_api_key", "geheim")
    fremd = {"volumeInfo": {"title": "Anderes", "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9783257228007"}]}}
    netz.setze(GB, antwort({"totalItems": 2, "items": [fremd, BAND]}))
    a = await GoogleBooks().nach_isbn("3257229534")
    assert (a.titel, a.isbn, a.jahr, a.beschreibung, a.kategorien) == ("Der Vorleser", VORLESER, 1997, "Ein **Buch**", ["Fiction", "Romance"])
    assert a.umschlag == "https://books.google.com/books/content?id=x&zoom=1&source=gbs_api"
    anfrage = netz.anfragen[0]
    assert anfrage.kopf["X-Goog-Api-Key"] == "geheim" and "geheim" not in str(anfrage.felder)
    netz.setze(GB, antwort({"totalItems": 1, "items": [fremd]}))
    assert await GoogleBooks().nach_isbn("9783499013225") is None
    netz.setze(GB, antwort({"totalItems": 0}))
    assert await GoogleBooks().nach_isbn("9783999999996") is None


async def test_google_verbrauchte_tagesmenge_ruht_bis_zum_naechsten_tag(netz, monkeypatch):
    monkeypatch.setattr(settings, "google_books_api_key", "geheim")
    netz.setze(GB, antwort(mitschnitt("google_tagesmenge.json"), status=429))
    with pytest.raises(Pausiert, match="Tagesmenge des Schlüssels ist verbraucht"):
        await GoogleBooks().nach_isbn(VORLESER)
    with pytest.raises(Pausiert):
        await GoogleBooks().nach_titel(Buchfrage(titel="Der Vorleser"))
    assert netz.zahl() == 1


async def test_crossref_artikel_buch_und_suche(netz):
    netz.setze(CR, antwort(mitschnitt("crossref_artikel.json")))
    a = await QUELLEN["crossref"].nach_doi("10.1038/nature14539")
    assert (a.titel, a.autoren[0], len(a.autoren), a.jahr, a.fund) == ("Deep learning", "Yann LeCun", 3, 2015, "doi")
    assert (a.roh["zeitschrift"], a.roh["heft"], a.roh["seitenbereich"]) == ("Nature", "7553", "436-444")
    netz.setze(CR, antwort(mitschnitt("crossref_buch.json")))
    b = await QUELLEN["crossref"].nach_isbn("9783658056193")
    assert (b.titel, b.doi, b.autoren) == ("Mathematik für Ingenieure und Naturwissenschaftler Band 1", "10.1007/978-3-658-05620-9", ["Lothar Papula"])
    netz.setze(CR, antwort(mitschnitt("crossref_artikel_deutsch.json")))
    c = await QUELLEN["crossref"].nach_titel(Buchfrage(titel="Künstliche Intelligenz im Unterricht", autoren=["Sonja Hensel"]))
    assert c.roh["zeitschrift"] == "Pädagogik" and c.beschreibung == "Worum es geht.\n\nWas dabei herauskam."
    netz.setze(CR, antwort(b"Resource not found.", status=404))
    assert await QUELLEN["crossref"].nach_doi("10.5555/x") is None


# -- Lexikon -----------------------------------------------------------------------------------------------------------
def _wikidata(*namen: str):
    """Antworten der Wikidata-Schnittstelle: Suche, Eintrag, Bezüge."""
    def beantworte(a):
        if feld(a, "generator") == "search":
            return antwort({"query": {"pages": [{"title": "Q87031740", "index": 1, "pageprops": {"wb-sitelinks": "0"}}]}})
        if feld(a, "ids") == "Q87031740":
            return antwort(mitschnitt("wikidata_ausgabe.json"))
        return antwort({"entities": {n: {"id": n, "labels": {"de": {"value": f"Name {n}"}}, "claims": {}} for n in feld(a, "ids").split("|")}})
    return beantworte


async def test_lexikon_fragt_die_isbn_mit_strichen(netz):
    netz.setze(WD, _wikidata())
    a = await Lexikon().nach_isbn("9783411708512")
    assert a.isbn == "9783411708512" and a.fund == "isbn" and a.titel and a.jahr and netz.zahl() == 3
    assert "P212=978-3-411-70851-2" in feld(netz.anfragen[0], "gsrsearch") and "P957=3-411-70851-4" in feld(netz.anfragen[0], "gsrsearch")


async def test_lexikon_fehler_mit_status_200_und_abweisung(netz):
    netz.setze(WD, antwort({"error": {"code": "maxlag", "info": "x"}}, retry_after="11.000"))
    with pytest.raises(Pausiert, match="gerade überlastet"):
        await Lexikon().nach_isbn(VORLESER)
    assert netz.zahl() == 1


async def test_lexikon_abgewiesen(netz):
    netz.setze(WD, antwort(mitschnitt("wikimedia_abgewiesen.txt"), status=403))
    with pytest.raises(Pausiert, match="Lexikon macht Pause .* weist die Anfrage ab"):
        await Lexikon().nach_isbn(VORLESER)


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
    s = await suche(Buchfrage(isbn=VORLESER, titel="Der Vorleser", autoren=["Bernhard Schlink"]), auskunft.ALLE)
    a = s.angaben
    assert (a.titel, a.jahr, a.verlag) == ("Der Vorleser", 1997, "Diogenes")
    assert a.herkunft["titel"] == "dnb" and a.herkunft["umschlag"] == "open_library" and a.herkunft["kategorien"] == "dnb"
    assert a.quelle == "alle" and a.fund == "isbn" and s.hinweise == [] and alle_antworten.zahl(GB) == 0
    assert any(k.startswith("Verzeichnis 3, ") for k in a.roh)


async def test_faellt_eine_quelle_aus_liefern_die_uebrigen_mit_hinweis(alle_antworten):
    alle_antworten.setze(DNB, AUSFALL)
    s = await suche(Buchfrage(isbn=VORLESER, titel="Der Vorleser"), auskunft.ALLE)
    assert s.angaben.herkunft["titel"] == "open_library" and s.hinweise == ["Verzeichnis 3: antwortet nicht rechtzeitig"] and not s.ruht


async def test_ohne_angabe_die_erste_die_etwas_weiss(alle_antworten):
    s = await suche(Buchfrage(isbn=VORLESER))
    assert s.angaben.quelle == "dnb" and alle_antworten.zahl() == 1


def test_ausgaben_werden_nicht_gemischt():
    genau = Angaben(quelle="open_library", fund="isbn", titel="Der Vorleser", verlag="Diogenes", isbn=VORLESER)
    andere = Angaben(quelle="dnb", fund="titel", titel="Der Vorleser", verlag="Schulbuchverlag", jahr=2010, beschreibung="Worum es geht", seiten=99)
    a = zusammenfuehren([andere, genau], Buchfrage(isbn=VORLESER, titel="Der Vorleser"))
    assert (a.verlag, a.jahr, a.seiten, a.beschreibung, a.herkunft["beschreibung"]) == ("Diogenes", None, 0, "Worum es geht", "dnb")


async def test_ergaenzen_fragt_nur_so_viele_wie_noetig(alle_antworten):
    with hintergrund():
        s = await ergaenze(Buchfrage(isbn=VORLESER), {"verlag", "jahr"})
    assert s.angaben.jahr == 1997 and alle_antworten.zahl() == 1
    with hintergrund():
        s = await ergaenze(Buchfrage(isbn=VORLESER), {"umschlag"})
    assert s.angaben.umschlag and alle_antworten.zahl(OL) == 1 and alle_antworten.zahl(DNB) == 1, "DNB aus dem Vorrat"


async def test_ergaenzen_ohne_isbn_nimmt_ausgabe_nur_bei_gleichem_jahr_oder_umfang(netz):
    for rechner in (OL, K10, CR):
        netz.setze(rechner, antwort({"docs": [], "message": {"items": []}}) if rechner != K10 else antwort(mitschnitt("k10plus_leer.xml")))
    netz.setze(DNB, antwort(mitschnitt("dnb_titel.xml")))
    frage = Buchfrage(titel="Die Vermessung der Welt", autoren=["Daniel Kehlmann"])
    s = await ergaenze(frage, {"isbn", "verlag", "sprache"})
    assert (s.angaben.isbn, s.angaben.verlag, s.angaben.sprache) == ("", "", "de")
    s = await ergaenze(frage.model_copy(update={"jahr": 2023}), {"isbn", "verlag"})
    assert s.angaben.isbn == "9783499013225" and s.angaben.verlag.startswith("Rowohlt")


@pytest.mark.parametrize("k10_antwortet", [False, True])
async def test_ergaenzen_ruht_erst_wenn_alle_gefragten_ruhen(netz, k10_antwortet):
    for rechner in (DNB, OL, K10, CR):
        netz.setze(rechner, antwort(status=429, retry_after="600"))
    if k10_antwortet:
        netz.setze(K10, antwort(mitschnitt("k10plus_leer.xml")))
    s = await ergaenze(Buchfrage(isbn=VORLESER), {"jahr"})
    assert s.ruht is not k10_antwortet and s.angaben is None and len(s.hinweise) == (3 if k10_antwortet else 4)


def test_bester_verwirft_unpassendes():
    frage = Buchfrage(titel="Der Vorleser", autoren=["Bernhard Schlink"])
    assert bester(frage, []) is None
    assert bester(frage, [Angaben(titel="Der Vorleser", autoren=["Peter Anders"]), Angaben(titel="Ganz anderes", autoren=["Bernhard Schlink"])]) is None
    assert bester(Buchfrage(titel="Faust"), [Angaben(titel="Faust und seine Zeit")]) is None


def test_vorschlag_behaelt_titel_mit_untertitel_und_schreibweise_der_isbn():
    a = Angaben(quelle="dnb", fund="isbn", titel="Das Parfum", untertitel="die Geschichte eines Mörders", autoren=["Patrick Süskind"], isbn="9783257228007", herkunft={"autoren": "dnb", "umschlag": "open_library"})
    v = vorschlag(a, {"title": "Das Parfum - Die Geschichte eines Mörders"})
    assert v["titel"] == "Das Parfum - Die Geschichte eines Mörders" and v["raw"]["untertitel"] and v["herkunft"] == {"autor": "dnb", "cover_url": "open_library"}
    assert vorschlag(a, {"title": "DAS PARFUM"})["titel"] == "Das Parfum"


# -- Gemeinfreie Bücher ------------------------------------------------------------------------------------------------
async def test_gemeinfreie_suche_und_seite_hinter_der_letzten(netz):
    netz.setze("gutendex.com", antwort(mitschnitt("gutendex_suche.json")), antwort({"detail": "Invalid page."}, status=404))
    liste = await gutenberg.suche("Faust", " DE, en ")
    erstes = liste.buecher[0]
    assert (liste.gesamt, erstes.autor, erstes.download_format, erstes.sprachen) == (7, "Goethe, Johann Wolfgang von", "epub", ["de"])
    assert dict(netz.anfragen[0].felder) == {"search": "Faust", "languages": "de,en"}
    assert (await gutenberg.suche("Faust", "de", seite=99)).buecher == []


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
