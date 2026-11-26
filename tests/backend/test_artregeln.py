"""Feste Regeln für die Art eines Werks (BF-77). Titel und Dateinamen sind erfunden."""

import pytest

from backend.app.services.artregeln import Werk, urteil


def werk(titel: str = "Ohne Besonderheit", **angaben) -> Werk:
    return Werk(**{"id": 1, "hash": "h", "title": titel, **angaben})


def art(w: Werk) -> tuple[str, str] | None:
    u = urteil(w)
    return (u.typ, u.grund) if u else None


def test_buch_mit_isbn_und_vielen_seiten_nur_ohne_schlichten_umschlag():
    assert art(werk(isbn="9783000000000", page_count=212, umschlag_schlicht=0)) == ("", "ISBN und 212 Seiten")
    assert art(werk(isbn="9783000000000", page_count=212, umschlag_schlicht=1)) is None      # das Deckblatt braucht die Gattung
    assert art(werk(isbn="9783000000000", page_count=212)) is None                           # Umschlag noch nicht geprüft
    assert werk(umschlag_schlicht=1).gattung_gefragt and not werk(umschlag_schlicht=0).gattung_gefragt and not werk().gattung_gefragt
    assert art(werk(isbn="9783000000000", page_count=40, umschlag_schlicht=0)) is None       # nicht mehr als 40 Seiten
    assert art(werk("Grundlagen des Rechnungswesens", isbn="9783000000000", page_count=20)) is None   # mit ISBN kein Dokument


@pytest.mark.parametrize(("angaben", "erwartet"), [
    ({"title": "Microsoft Word - Protokoll Sitzung"}, "Der Titel stammt aus einem Schreibprogramm"),
    ({"title": "Microsoft PowerPoint - Jahresrückblick"}, "Der Titel stammt aus einem Folienprogramm"),
    ({"title": "Ablage", "file_name": "Umsatz_2023.xlsx.pdf"}, "Endung .xlsx im Dateinamen"),
    ({"title": "Entwurf.docx"}, "Endung .docx im Titel"),
    ({"title": "Rechnung 2024-03 Werkstatt"}, "\"Rechnung\" im Titel, keine ISBN"),
    ({"title": "Scan", "file_name": "scan_RECHNUNG_mai.pdf"}, "\"RECHNUNG\" im Dateinamen, keine ISBN"),
    ({"title": "Datenblatt Schrittmotor"}, "\"Datenblatt\" im Titel, keine ISBN"),
    ({"title": "Pump Datasheet Rev B"}, "\"Datasheet\" im Titel, keine ISBN"),
    ({"title": "Folien zur Vorlesung"}, "\"Folien\" im Titel, keine ISBN"),
    ({"title": "Lecture 7: Graphs"}, "\"Lecture\" im Titel, keine ISBN"),
    ({"title": "Einladung", "page_count": 2}, "2 Seiten und keine ISBN"),
    ({"title": "Zettel", "page_count": 1}, "1 Seite und keine ISBN"),
])
def test_dokument_nach_namen_und_seiten(angaben, erwartet):
    assert art(werk(**angaben)) == ("dokument", erwartet)


@pytest.mark.parametrize(("angaben", "erwartet"), [
    ({"title": "Gebrauchsanweisung Toaster"}, "\"Gebrauchsanweisung\" im Titel, keine ISBN"),
    ({"title": "Kaffeemaschine User Manual"}, "\"User Manual\" im Titel, keine ISBN"),
    ({"title": "Scan", "file_name": "Regal_Montageanleitung.pdf"}, "\"Montageanleitung\" im Dateinamen, keine ISBN"),
    ({"title": "Microsoft Word - Bedienungsanleitung Funkwecker"}, "\"Bedienungsanleitung\" im Titel, keine ISBN"),
    ({"title": "Quick Start Guide Router", "page_count": 2}, "\"Quick Start Guide\" im Titel, keine ISBN"),
])
def test_anleitung_nach_namen(angaben, erwartet):
    """Seit BF-80 eine eigene Art neben dem Dokument, vor allen Regeln für Dokumente."""
    assert art(werk(**angaben)) == ("anleitung", erwartet)


def test_keine_regel_sicher():
    assert art(werk("Nebel über der Marsch", page_count=180)) is None
    assert art(werk("Die Vorrechnungen", page_count=0)) is None                             # nicht am Wortanfang, Seiten unbekannt
    assert art(werk("Unbelegte Gerüchte")) is None
