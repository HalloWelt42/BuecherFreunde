"""Lücken in Sammlungen (BF-75) ohne Datenbank: was Bandnummern bedeuten (auch 3.5, 3a, Doppelbände), welche Plätze fehlen, die
kurzen Sätze, was aus den Funden eines Katalogs gilt, die Suchadresse und das Lesen der Reihe aus MARC 21. Alle Reihen, Titel und
Namen sind erfunden."""

from __future__ import annotations

import pytest

from backend.app.luecken.bandnummer import lesen
from backend.app.luecken.rechnen import aus_den_quellen, belegt, bereiche, fehlen_satz, fehlende, lueckenzeile, vorschlagszeile
from backend.app.luecken.suchadresse import FalscheVorlage, fuellen, pruefen
from backend.app.quellen import marc
from backend.app.quellen.reihen import KATALOGE, Reihenfrage, Reihenfund, funde_im_satz, passende, reihenname
from tests.luecken_kataloge import antwort_mit, satz


@pytest.mark.parametrize(("text", "von", "bis", "zwischen", "plaetze"), [
    ("3", 3, 3, False, [3]), ("03", 3, 3, False, [3]), ("Band 3", 3, 3, False, [3]), ("Bd. 3", 3, 3, False, [3]),
    ("3.", 3, 3, False, [3]), ("[3]", 3, 3, False, [3]), ("3. Band", 3, 3, False, [3]), ("Teil 12", 12, 12, False, [12]),
    ("3.0", 3, 3, False, [3]),
    ("3.5", 3, 3, True, []), ("3,5", 3, 3, True, []), ("3a", 3, 3, True, []), ("3 b", 3, 3, True, []),
    ("1-2", 1, 2, False, [1, 2]), ("1/2", 1, 2, False, [1, 2]),
    ("0", 0, 0, False, []),                                          # vor Band 1, die Zählung beginnt bei 1
    ("Sonderband", None, None, False, []), ("", None, None, False, []),
    ("22953", 22953, 22953, False, []),                              # Nummer einer Verlagsreihe: keine Reihe zählt so weit
])
def test_bandnummern(text, von, bis, zwischen, plaetze):
    b = lesen(text)
    assert (b.von, b.bis, b.zwischen, list(b.plaetze)) == (von, bis, zwischen, plaetze)


def test_folge_der_baende():
    texte = ["Sonderband", "", "10", "3a", "3", "3.5", "1-2", "0", "4"]
    assert sorted(texte, key=lambda t: lesen(t).ordnung) == ["0", "1-2", "3", "3.5", "3a", "4", "10", "Sonderband", ""]


def test_fehlende_mit_und_ohne_zahl():
    plaetze = belegt(lesen(t) for t in ("3", "3a", "5", "1-2", "8.5"))
    assert plaetze == {1, 2, 3, 5}
    assert fehlende(plaetze, None) == [4]                            # ohne Zahl nur zwischen dem ersten und dem letzten
    assert fehlende(plaetze, 8) == [4, 6, 7, 8]                      # mit Zahl ab 1 bis zu ihr
    assert fehlende(plaetze, 8, {7}) == [4, 6, 8]                    # ausgeblendet fehlt nie
    assert fehlende({4, 6}, None) == [5]                             # ohne Zahl zählt der Anfang nicht
    assert fehlende({4, 6}, 6) == [1, 2, 3, 5]
    assert fehlende({2, 9}, 3) == [1, 3]                             # was über die Zahl hinausgeht, ist einfach da
    assert fehlende(set(), 12) == []                                 # ohne Nummern keine Folge, also keine Lücke


def test_saetze():
    assert bereiche([1, 2, 3, 4, 5, 8]) == ["1 bis 5", "8"]
    assert bereiche([6, 7]) == ["6", "7"]
    assert lueckenzeile({1, 2, 3, 4, 5, 8}, [6, 7]) == "vorhanden 1 bis 5 und 8, es fehlen 6 und 7"
    assert fehlen_satz([4]) == "es fehlt 4"
    assert fehlen_satz([4, 9, 11, 12]) == "es fehlen 4, 9, 11 und 12"
    assert fehlen_satz([6, 7, 8, 9]) == "es fehlen 6 bis 9"
    assert lueckenzeile({1, 2, 3}, []) == ""


def test_vorschlagszeile_je_sprache():
    de = [lesen(t) for t in ("1", "2", "3", "5")]
    assert vorschlagszeile({"de": de}) == "vorhanden 1 bis 3 und 5, es fehlt 4"
    assert vorschlagszeile({"de": de, "en": [lesen("1"), lesen("3")]}) == \
        "Deutsch: vorhanden 1 bis 3 und 5, es fehlt 4; Englisch: vorhanden 1 und 3, es fehlt 2"
    assert vorschlagszeile({"de": de, "en": [lesen("1"), lesen("2")]}) == "Deutsch: vorhanden 1 bis 3 und 5, es fehlt 4"
    assert vorschlagszeile({"de": [lesen("1"), lesen("2")]}) == ""


def _fund(band: str, titel: str = "", isbn: str = "", jahr: int | None = None) -> Reihenfund:
    return Reihenfund(reihe="Leuchtfeuerkai", band=band, titel=titel, autoren=["Henrike Sandvoss"], isbn=isbn, jahr=jahr, quelle="dnb")


def test_aus_den_quellen():
    e = aus_den_quellen([_fund("1", "Nebel am Kai"), _fund("Bd. 2", "Ebbe", jahr=2019), _fund("2", "Ebbe", "9783999990026", 2021),
                         _fund("2", "Ebbe", "9783999990019", 2018), _fund("3.5", "Novelle"), _fund("5-6", "Doppelband")])
    assert e.gesamt == 6                                             # der höchste belegte Platz, auch aus einem Doppelband
    assert [(b.nummer, b.titel, b.isbn) for b in e.baende] == [(1, "Nebel am Kai", ""), (2, "Ebbe", "9783999990026")]
    assert e.baende[0].autor == "Henrike Sandvoss"
    assert aus_den_quellen([]).gesamt is None


# -- Suchadresse ------------------------------------------------------------------------------------------------------------

def test_suchadresse_mit_sonderzeichen():
    vorlage = pruefen("https://katalog.example/suche?q={titel} {autor}&isbn={isbn}&n={nummer}&r={sammlung}")
    adresse = fuellen(vorlage, {"titel": "Möwen & Nebel/Teil #2+", "autor": "Henrike Sandvoß", "isbn": "9783999990040", "band": "4",
                                "reihe": "Kai 100%"})
    assert adresse == ("https://katalog.example/suche?q=M%C3%B6wen%20%26%20Nebel%2FTeil%20%232%2B%20Henrike%20Sandvo%C3%9F"
                       "&isbn=9783999990040&n=4&r=Kai%20100%25")
    assert fuellen("", {"titel": "x"}) is None
    assert fuellen("https://katalog.example/isbn/{isbn}", {}) == "https://katalog.example/isbn/"     # Unbekanntes bleibt leer


@pytest.mark.parametrize(("vorlage", "grund"), [
    ("https://katalog.example/?q={titl}", "unbekannter Platzhalter {titl}"),
    ("javascript:alert({titel})", "http:// oder https://"),
    ("katalog.example/?q={titel}", "http:// oder https://"),
    ("https://katalog.example/?q={titel", "geschweifte Klammern"),
])
def test_falsche_vorlagen(vorlage, grund):
    with pytest.raises(FalscheVorlage, match=grund.replace("{", r"\{").replace("}", r"\}")):
        pruefen(vorlage)


# -- Reihen in MARC 21 --------------------------------------------------------------------------------------------------------

def test_reihe_aus_allen_feldern():
    saetze = marc.saetze(antwort_mit(
        satz("Nebel am Kai", reihe="Leuchtfeuerkai", band="1"),                                    # 490 mit $v
        satz("Ebbe", reihe="Leuchtfeuerkai ; Bd. 2", band=""),                                     # Band im Namen
        satz("Der stille Kai", reihe="Die Leuchtfeuerkai-Saga", band="3", feld="830"),
        satz("Leuchtfeuerkai", teil="4", teiltitel="Sturm über Hallig", reihe=""),                # mehrbändiges Werk
        satz("Krabbenkutter", reihe="Taschenbuch", band="22953"),                                 # Verlagsreihe
    ))
    funde = [f for s in saetze for f in funde_im_satz(s, "dnb")]
    assert [(f.reihe, f.band, f.titel) for f in funde] == [
        ("Leuchtfeuerkai", "1", "Nebel am Kai"), ("Leuchtfeuerkai", "Bd. 2", "Ebbe"), ("Die Leuchtfeuerkai-Saga", "3", "Der stille Kai"),
        ("Leuchtfeuerkai", "4", "Sturm über Hallig"), ("Taschenbuch", "22953", "Krabbenkutter")]
    frage = Reihenfrage(reihe="Leuchtfeuerkai", sprache="de")
    assert [f.band for f in passende(funde, frage)] == ["1", "Bd. 2", "4"]
    assert reihenname("Die Leuchtfeuerkai Saga") == reihenname("Leuchtfeuerkai-Saga")


def test_anfragen_der_kataloge():
    frage = Reihenfrage(reihe='Leuchtfeuer "Kai"', autor="Sandvoss, Henrike", sprache="de")
    assert KATALOGE["dnb"].anfrage(frage) == 'TIT="Leuchtfeuer Kai" and PER="sandvoss" and MAT=books and SPR=ger'
    assert KATALOGE["k10plus"].anfrage(frage) == 'pica.tit="Leuchtfeuer Kai" and pica.per="sandvoss"'
    assert KATALOGE["dnb"].anfrage(Reihenfrage(reihe="Leuchtfeuerkai")) == 'TIT="Leuchtfeuerkai" and MAT=books'
