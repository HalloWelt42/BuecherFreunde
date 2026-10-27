"""Textansicht eines PDF: der Text je Dateiseite als umfließende Absätze, zum Lesen am Telefon.

Ein PDF hat feste Zeilen; für die Textansicht werden sie zu Absätzen verbunden:
- Kopf- und Fußzeilen fallen weg: Zeilen am Rand einer Seite, die (Ziffern nicht gezählt) auf vielen Seiten gleich
  wiederkehren, sowie einzelne Seitenzahlen am Rand.
- Trennstriche am Zeilenende werden verbunden, wenn die nächste Zeile klein weitergeht ("Bei-" + "spiel"); vor einem
  Großbuchstaben bleibt der Bindestrich ("Nord-" + "Süd").
- Ein neuer Absatz beginnt nach einer Leerzeile oder nach einer deutlich kürzeren Zeile, die mit einem Satzzeichen
  endet; alle anderen Zeilen gehören zum laufenden Absatz.

Bilder, Tabellen und Formeln gehen dabei verloren; dafür bleibt die Originalansicht.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter

_RANDZEILEN = 2                 # so viele Zeilen oben und unten können Kopf- oder Fußzeile sein
_WIEDERKEHR_ANTEIL = 0.3        # ab diesem Anteil der Seiten gilt eine Randzeile als Kopf- oder Fußzeile
_MINDEST_SEITEN = 5             # darunter keine Erkennung wiederkehrender Zeilen
_KURZE_ZEILE = 0.75             # kürzer als dieser Anteil der üblichen Zeilenlänge: Absatzende möglich
_SATZENDE = tuple('.!?:")') + tuple(map(chr, (0x201C, 0x201D, 0xBB, 0xAB)))  # auch typografische Anführungen
_ZIFFERN = re.compile(r"\d+")
_STRICHE = "\\-" + chr(0x2013) + chr(0x2014)  # Bindestrich, Halbgeviert- und Geviertstrich
_SEITENZAHL = re.compile(rf"^[\s{_STRICHE}]*(\d{{1,4}}|[ivxlcdm]{{1,7}})[\s{_STRICHE}]*$", re.IGNORECASE)


def _muster(zeile: str) -> str:
    """Randzeile ohne Ziffern und Leerraum: "Kapitel 3 · 112" und "Kapitel 3 · 113" sind dieselbe Kopfzeile."""
    return _ZIFFERN.sub("#", " ".join(zeile.split())).lower()


def _zeilen(text: str) -> list[str]:
    return [z.rstrip() for z in text.splitlines()]


def _rand_indizes(zeilen: list[str]) -> list[int]:
    belegt = [i for i, z in enumerate(zeilen) if z.strip()]
    return belegt[:_RANDZEILEN] + belegt[-_RANDZEILEN:]


def wiederkehrende_randzeilen(seiten: list[str]) -> set[str]:
    """Muster der Randzeilen, die auf vielen Seiten wiederkehren (Kopf- und Fußzeilen des ganzen Buchs)."""
    if len(seiten) < _MINDEST_SEITEN:
        return set()
    zaehler: Counter[str] = Counter()
    for text in seiten:
        zeilen = _zeilen(text)
        zaehler.update({_muster(zeilen[i]) for i in _rand_indizes(zeilen)})
    grenze = max(3, int(len(seiten) * _WIEDERKEHR_ANTEIL))
    return {m for m, n in zaehler.items() if n >= grenze and m.strip("# ")}


def _ohne_rand(zeilen: list[str], wiederkehrend: set[str]) -> list[str]:
    weg = {i for i in _rand_indizes(zeilen)
           if _muster(zeilen[i]) in wiederkehrend or _SEITENZAHL.match(zeilen[i])}
    return [z for i, z in enumerate(zeilen) if i not in weg]


def absaetze(text: str, wiederkehrend: set[str]) -> list[str]:
    """Die Absätze einer Seite als Fließtext."""
    zeilen = _ohne_rand(_zeilen(text), wiederkehrend)
    laengen = [len(z.strip()) for z in zeilen if len(z.strip()) > 20]
    ueblich = statistics.median(laengen) if laengen else 0

    ergebnis: list[str] = []
    laufend = ""
    for roh in zeilen:
        zeile = " ".join(roh.split())
        if not zeile:
            if laufend:
                ergebnis.append(laufend)
                laufend = ""
            continue
        if not laufend:
            laufend = zeile
        elif laufend.endswith("-") and len(laufend) > 1 and laufend[-2].isalpha():
            # "Bei-" + "spiel" ist getrennt, "Nord-" + "Süd" bleibt verbunden
            laufend = (laufend[:-1] if zeile[0].islower() else laufend) + zeile
        else:
            laufend = f"{laufend} {zeile}"
        if ueblich and len(zeile) < ueblich * _KURZE_ZEILE and zeile.endswith(_SATZENDE):
            ergebnis.append(laufend)
            laufend = ""
    if laufend:
        ergebnis.append(laufend)
    return ergebnis
