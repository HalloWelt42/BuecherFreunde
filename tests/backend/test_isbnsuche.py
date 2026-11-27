"""ISBN im Buch (BF-111): Erkennung mit Wortgrenzen und Prüfziffer, Merkmal Druck oder E-Book, Fundort, Zusammenfassen der
Schreibweisen, Stufe aus dem Text und aus der Quelle, Rangfolge, und die eine Regel für die Leser der Annahme. Bücher, Personen
und Nummern sind erfunden."""

import isbnlib
import pytest

from backend.app.isbnsuche import fundort as orte
from backend.app.isbnsuche.erkennung import finde
from backend.app.isbnsuche.kandidaten import als_seiten, beste, kandidaten
from backend.app.isbnsuche.modelle import Ausgabe, Fundort
from backend.app.quellen.abgleich import Stufe, isbn_abgleich, isbn_fund_passt, text_abgleich
from backend.app.quellen.modelle import Angaben, Buchfrage
from backend.app.services.processors.text_processor import TextProcessor


def nummer(n: int, vorn: str = "978399999") -> str:
    kern = f"{vorn}{n:03d}"
    return kern + isbnlib.check_digit13(kern)


def strich(isbn: str) -> str:
    return isbnlib.mask(isbn)


DRUCK, EBOOK, ANMERKUNG, ANZEIGE, LITERATUR, LITERATUR2 = (nummer(n) for n in (241, 255, 183, 118, 402, 893))
TITEL, AUTORIN = "Die Möwen von Musterstadt", "Erika Beispiel"
FRAGE = Buchfrage(titel=TITEL, autoren=[AUTORIN])


def buch() -> list[str]:
    """Ein Roman mit Impressum, Rückseite, Anmerkungen, Literaturliste und Verlagsanzeige."""
    seiten = ["Im Hafen von Musterstadt lag Nebel."] * 320
    seiten[0] = f"{AUTORIN}\n{TITEL}\nRoman"
    seiten[2] = "Inhalt\nErster Teil\nLiteratur\nAnmerkungen"
    seiten[3] = (f"{AUTORIN}, {TITEL}. Roman.\n© 2019 Beispielverlag, Musterstadt.\nISBN {strich(DRUCK)} (Druckausgabe), ISBN {strich(EBOOK)} (E-Book)\n"
                 "Alle Rechte vorbehalten.")
    seiten[296] = f"Literatur\nBrandauer, Mette: Moorkunde für Anfänger. Beispielhausen\n1998. ISBN {isbnlib.mask(isbnlib.to_isbn10(LITERATUR))}"
    seiten[297] = f"Brandauer (2011), Neuausgabe, ISBN {strich(LITERATUR)}\nFehrs, Jakob: Seezeichen der Musterküste. Kiel 2014, ISBN {strich(LITERATUR2)}"
    seiten[304] = f"Anmerkungen\n14 Die Tafel zitiert nach: ISBN {strich(ANMERKUNG)}, Blatt 41."
    seiten[309] = f"Ebenfalls im Beispielverlag: {AUTORIN}, Salz auf der Haut. Roman, 2016. ISBN {strich(ANZEIGE)}"
    seiten[319] = f"Eine Lotsin, die nicht schweigt. ISBN {strich(DRUCK)} 22,00 € (D)\n{DRUCK[0]} {DRUCK[1:7]} {DRUCK[7:]}"
    return seiten


# -- Erkennung ---------------------------------------------------------------------------------------------------------
def test_nur_ganze_nummern_mit_stimmender_pruefziffer():
    zehn = isbnlib.to_isbn10(DRUCK)
    falsch = DRUCK[:-1] + str((int(DRUCK[-1]) + 1) % 10)
    text = (f"Bestellnummer 4{DRUCK}7 und 12{zehn}, Telefon {zehn}, falsch {falsch}. ISBN {zehn} und {isbnlib.mask(zehn)}; "
            f"ohne Striche {EBOOK}, Strichcode {EBOOK[0]} {EBOOK[1:7]} {EBOOK[7:]}")
    funde = finde([text])
    assert [f.form for f in funde] == [zehn, isbnlib.mask(zehn), EBOOK, f"{EBOOK[0]} {EBOOK[1:7]} {EBOOK[7:]}"], "keine Nummer mitten aus einer Zahl, ISBN-10 nur mit ISBN davor oder drei Strichen"
    assert {f.isbn13 for f in funde} == {DRUCK, EBOOK}


@pytest.mark.parametrize(("text", "ausgabe"), [
    ("ISBN {a} (Druckausgabe), ISBN {b} (E-Book)", [Ausgabe.DRUCK, Ausgabe.EBOOK]),
    ("E-Book (PDF): ISBN {a}\nPrint-ISBN {b}", [Ausgabe.EBOOK, Ausgabe.DRUCK]),
    ("eISBN {a}, gebunden: ISBN {b}", [Ausgabe.EBOOK, Ausgabe.DRUCK]),
    ("Ausgabe ISBN {a}. Druck: Musterdruck, ISBN {b}", [Ausgabe.OFFEN, Ausgabe.OFFEN]),
    ("ISBN {a} (Druckausgabe), ISBN {b}\n(E-Book)\nUmschlag", [Ausgabe.DRUCK, Ausgabe.EBOOK]),          # umbrochen
    ("ISBN {a}\nE-Book ISBN {b}", [Ausgabe.OFFEN, Ausgabe.EBOOK]),                                    # ohne Klammern kündigt es an
])
def test_druck_oder_ebook_nur_aus_dem_text_neben_der_nummer(text, ausgabe):
    assert [f.ausgabe for f in finde([text.format(a=strich(DRUCK), b=strich(EBOOK))])] == ausgabe


def test_fundorte():
    seiten = buch()
    lage = orte.lage(seiten)
    ort = {(f.isbn13, f.seite): orte.fundort(lage, f.seite, f.anfang) for f in finde(seiten)}
    assert ort[DRUCK, 3] == ort[EBOOK, 3] == Fundort.IMPRESSUM and ort[DRUCK, 319] == Fundort.RUECKSEITE, "Preis auf der letzten Seite, nach der Verlagsanzeige"
    assert ort[ANMERKUNG, 304] == Fundort.ANMERKUNGEN and ort[ANZEIGE, 309] == Fundort.VERLAGSANZEIGE
    assert ort[LITERATUR, 296] == ort[LITERATUR, 297] == ort[LITERATUR2, 297] == Fundort.LITERATURLISTE
    assert orte.fundort(lage, 100, 0) == Fundort.TEXT and orte.fundort(lage, 1, 0) == Fundort.TITELEI, "das Inhaltsverzeichnis beginnt keine Literaturliste"


@pytest.mark.parametrize("seite", [
    # Verlagsanzeige vorn, darunter das Impressum (E-Book: alles in einem Dokument)
    f"Weitere Titel in dieser Reihe:\nLene Probe: Watt im Nebel\nOkke Probe: Ebbe\n\n1. Auflage 2014\n© 2014 Beispielverlag\nISBN {strich(DRUCK)}",
    # Quellenverzeichnis, dann die Überschrift Impressum
    f"Quellenverzeichnis\nMein Weg zum Deich - Erstveröffentlichung\n\nImpressum\nCover: Atelier Beispiel\nISBN E-Book: {strich(DRUCK)}",
    # Werbung für andere Bücher, dann das Impressum mit "Alle Rechte vorbehalten"
    f"Außerdem im Beispielverlag erschienen: »Das Wehr«, »Die Schleuse«\n\nCovergestaltung: Atelier Beispiel\nAlle Rechte vorbehalten.\nISBN {strich(DRUCK)}",
])
def test_ein_impressum_beendet_die_liste_davor(seite):
    for vorn in (True, False):
        seiten = ["Im Hafen von Musterstadt lag Nebel."] * 30
        seiten[0 if vorn else 25] = seite             # hinten gälte eine Liste sonst auch für die Seiten danach
        lage = orte.lage(seiten)
        f = next(f for f in finde(seiten) if f.isbn13 == DRUCK)
        assert orte.fundort(lage, f.seite, f.anfang) == Fundort.IMPRESSUM
        assert orte.fundort(lage, f.seite + 1, 0) in (Fundort.TITELEI, Fundort.TEXT), "das Impressum gilt nur auf seiner Seite"


# -- Kandidaten --------------------------------------------------------------------------------------------------------
def test_kandidaten_wie_im_entwurf():
    liste = kandidaten(buch(), FRAGE)
    assert [k.isbn13 for k in liste] == [DRUCK, EBOOK, ANMERKUNG, ANZEIGE, LITERATUR, LITERATUR2]
    druck, ebook, anm, anzeige, literatur, _ = liste
    assert (druck.isbn, druck.ausgabe, druck.funde, druck.fundort, len(druck.stellen)) == (strich(DRUCK), Ausgabe.DRUCK, 3, Fundort.IMPRESSUM, 2)
    assert druck.formen == [f"{DRUCK[0]} {DRUCK[1:7]} {DRUCK[7:]}"] and druck.stellen[1].funde == 2, "Strichcode und Nummer auf der Rückseite sind eine Stelle"
    assert druck.stellen[0].seite == 4 and f"<mark>{strich(DRUCK)}</mark>" in druck.stellen[0].ausschnitt and f"<mark>{strich(EBOOK)}" not in druck.stellen[0].ausschnitt
    assert (druck.text.stufe, ebook.text.stufe, ebook.ausgabe) == (Stufe.PASST, Stufe.PASST, Ausgabe.EBOOK), "Druck vor E-Book im Impressum"
    assert druck.text.was == f"{AUTORIN}, {TITEL}" and druck.text.basis == "im Text"
    assert (anm.text.stufe, anm.text.was) == (Stufe.UNBEKANNT, "kein Titel daneben")
    assert (anzeige.text.stufe, anzeige.text.warum) == (Stufe.FREMD, "anderer Titel, gleicher Autor")
    assert anzeige.text.was == f"{AUTORIN}, <mark>Salz auf der Haut. Roman, 2016</mark>", "der fremde Titel markiert, der eigene Name nicht"
    assert (literatur.funde, literatur.formen, literatur.text.stufe) == (2, [isbnlib.mask(isbnlib.to_isbn10(LITERATUR))], Stufe.FREMD), "ISBN-10 und ISBN-13 sind ein Kandidat"
    assert "Moorkunde für Anfänger" in literatur.text.was and "ISBN" not in literatur.text.was


def test_ohne_text_und_ohne_seiten():
    assert kandidaten([], FRAGE) == [] and kandidaten(["kein Buch"], FRAGE) == []
    assert len(als_seiten("Wort " * 1400)) == 3 and als_seiten("a\fb") == ["a", "b"] and als_seiten("") == []
    text = "Nebel " * 499 + f"ISBN {strich(DRUCK)}\nLiteratur\n" + "Nebel " * 600
    assert all(not s.startswith(("99", "-")) for s in als_seiten(text, 3)) and len(finde(als_seiten(text, 3))) == 1, "kein Schnitt mitten durch die Nummer"


# -- Stufe -------------------------------------------------------------------------------------------------------------
def test_stufe_aus_dem_text():
    stufe = lambda umfeld, fremd=False, frage=FRAGE: text_abgleich(frage, umfeld, fremd).stufe  # noqa: E731
    assert stufe(f"{AUTORIN}: {TITEL}") is Stufe.PASST
    assert stufe(f"{TITEL}. Roman") is Stufe.AEHNLICH, "der Autor steht nicht daneben"
    assert stufe("Möwen von Musterstadt, Beispiel") is Stufe.AEHNLICH, "ohne Artikel"
    assert stufe("Blatt 41") is Stufe.UNBEKANNT and stufe("Blatt 41", True) is Stufe.FREMD
    assert stufe(f"{AUTORIN}, Salz auf der Haut", True) is Stufe.FREMD
    assert stufe(TITEL, True, Buchfrage(titel=TITEL)) is Stufe.AEHNLICH, "in einer Liste genügt der Titel ohne Autor nicht"


def test_stufe_aus_der_quelle_ist_dieselbe_regel_wie_isbn_fund_passt():
    def abgleich(titel, autoren, frage=FRAGE):
        return isbn_abgleich(frage, Angaben(titel=titel, autoren=autoren))

    assert abgleich(TITEL, [AUTORIN]).stufe is Stufe.PASST and abgleich(TITEL, ["Beispiel, Erika"]).stufe is Stufe.PASST
    a = abgleich("Möwen von Musterstadt", ["E. Beispiel"])
    assert (a.stufe, a.gruende, a.titel_anders, a.autor_anders) == (Stufe.AEHNLICH, ["Titel ohne Artikel", "Vorname abgekürzt"], True, True)
    assert abgleich(TITEL, []).gruende == ["Autor fehlt"]
    f = abgleich("Salz auf der Haut", [AUTORIN])
    assert (f.stufe, f.gruende) == (Stufe.FREMD, ["anderer Titel", "gleicher Autor"]), "ein anderes Buch derselben Autorin"
    assert abgleich("", [], Buchfrage(titel="scan_0001.pdf")).stufe is Stufe.UNBEKANNT
    for titel, autoren in ((TITEL, [AUTORIN]), ("Salz auf der Haut", [AUTORIN]), ("Möwen von Musterstadt", ["Hans Fremd"])):
        fund = Angaben(titel=titel, autoren=autoren)
        assert isbn_fund_passt(FRAGE, fund) is (isbn_abgleich(FRAGE, fund).stufe is not Stufe.FREMD)


# -- Annahme -----------------------------------------------------------------------------------------------------------
def test_die_annahme_nimmt_die_eigene_isbn_nicht_die_kleinste():
    assert min(DRUCK, EBOOK, ANMERKUNG, ANZEIGE, LITERATUR, LITERATUR2) == ANZEIGE, "früher kam die kleinste, die der Verlagsanzeige"
    assert beste(buch(), TITEL, AUTORIN) == DRUCK
    nur_fremde = ["Titel"] * 10 + [f"Literatur\nFehrs, Jakob: Seezeichen. Kiel 2014, ISBN {strich(LITERATUR2)}"]
    assert beste(nur_fremde, TITEL, AUTORIN) == "", "eine ISBN aus der Literaturliste gehört einem anderen Buch"


def test_textdatei_beim_aufnehmen(tmp_path):
    datei = tmp_path / "moewen.txt"
    datei.write_text("\n".join(buch()), encoding="utf-8")
    assert TextProcessor().process(datei).isbn == DRUCK
