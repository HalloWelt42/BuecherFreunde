"""Textansicht: feste PDF-Zeilen werden zu Absätzen, Kopf- und Fußzeilen fallen weg."""

from backend.app.services.textansicht import absaetze, wiederkehrende_randzeilen

ZEILEN = [
    "Am Morgen ging die Sonne über dem kleinen Dorf auf, und die Bauern zogen",
    "mit ihren Wagen hinaus auf die Felder, die noch nass vom Tau der Nacht",
    "waren. Niemand ahnte, was an diesem Tag geschehen würde, denn alles war",
    "wie immer.",
    "Erst gegen Mittag kam ein Reiter den Weg herauf, staubig und müde von der",
    "langen Reise, und hielt vor dem Wirtshaus an der Ecke des Marktplatzes.",
]


def seite(nr: int, rumpf: list[str]) -> str:
    return "\n".join(["Das Dorf am Fluss", *rumpf, str(nr)])


NAMEN = ["Anna", "Bruno", "Clara", "David", "Emil", "Frieda", "Gustav", "Hanna", "Ida", "Jakob", "Karl", "Lena",
         "Max", "Nora", "Otto", "Paula", "Quirin", "Rosa", "Simon", "Tilda"]


def buch() -> list[str]:
    # je Seite anderer Inhalt, nur Kopfzeile und Seitenzahl kehren wieder
    return [seite(nr, [f"{name} {zeile}" for zeile in ZEILEN]) for nr, name in enumerate(NAMEN, 1)]


def test_kopfzeile_wird_erkannt():
    assert wiederkehrende_randzeilen(buch()) == {"das dorf am fluss"}


def test_wenige_seiten_ohne_erkennung():
    assert wiederkehrende_randzeilen(buch()[:3]) == set()


def test_absaetze_ohne_rand_und_mit_umbruch():
    text = seite(7, ZEILEN)
    ergebnis = absaetze(text, wiederkehrende_randzeilen(buch()))
    assert ergebnis == [
        " ".join(ZEILEN[:4]),
        " ".join(ZEILEN[4:]),
    ]


def test_trennstrich_wird_verbunden():
    text = "Das ist ein sehr langer Satz mit einem Wort, das am Ende getrennt wer-\nden muss, weil die Zeile endet."
    assert absaetze(text, set()) == ["Das ist ein sehr langer Satz mit einem Wort, das am Ende getrennt werden muss, "
                                     "weil die Zeile endet."]


def test_bindestrich_vor_grossbuchstabe_bleibt():
    text = "Ein Satz über Nord-\nSüd-Verbindungen und mehr Text, damit die Zeile lang genug ist."
    assert absaetze(text, set()) == ["Ein Satz über Nord-Süd-Verbindungen und mehr Text, damit die Zeile lang genug ist."]


def test_leerzeile_trennt_absaetze():
    assert absaetze("Erster Absatz.\n\nZweiter Absatz.", set()) == ["Erster Absatz.", "Zweiter Absatz."]


def test_leere_seite():
    assert absaetze("", set()) == []
