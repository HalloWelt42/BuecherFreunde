"""Zahlen im Original und in der Übersetzung vergleichen (BF-71), nach Angleichen der Tausender- und Dezimalzeichen.

Englisch schreibt 16,000 und 1.5, Deutsch 16.000 (oder 16 000 mit schmalem Leerzeichen) und 1,5. Verglichen wird in vier
Gängen: erst gleich geschriebene Zahlen (eine Version 3.12 bleibt 3.12), dann gleiche Werte (16,000 = 16.000; 1.5 = 1,5),
dann Zahlwörter der anderen Seite für eine übrige Zahl von eins bis zwölf (4-level: vierstufig, zweifach, dreidimensional;
two-level: 2-stufig), zuletzt die Ziffernfolgen dessen, was übrig ist (ein Datum 11/26/2026 darf 26.11.2026 werden). Was
danach fehlt oder dazukam, ist ein Befund; ebenso eine Zahl, die unverändert stehen blieb, im Deutschen aber anderes heißt
(16,000 hieße 16).

Zahlwörter (vorgaben.json, `zahlwoerter`) gleichen nur Ziffern aus, die sonst fehlten; für sich fordern sie nichts, so ist
"zwei Ebenen" für "two levels" in Ordnung und der Artikel "eine" nie eine fehlende Zahl. Vorzeichen bleiben außen vor."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from backend.app.uebersetzung.vorgaben import zahlwoerter

ZAHL = re.compile(r"\d{1,3}(?:[\u00a0\u202f\u2009]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)*")
_EN_GRUPPEN = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")
_EN_EINFACH = re.compile(r"\d+(?:\.\d+)?")
_DE_GRUPPEN = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?")
_DE_RAUM = re.compile(r"\d{1,3}(?:[\u00a0\u202f\u2009]\d{3})+(?:,\d+)?")
_DE_EINFACH = re.compile(r"\d+(?:,\d+)?")
WORT = re.compile(r"[^\W\d_]+")


def _wert(text: str) -> str | None:
    try:
        return format(Decimal(text).normalize(), "f")
    except InvalidOperation:
        return None


def wert_englisch(roh: str) -> str | None:
    """Der Wert einer englisch geschriebenen Zahl; None, wenn sie keine ist (etwa 3.12.1 oder 1,2,3)."""
    if _EN_GRUPPEN.fullmatch(roh):
        return _wert(roh.replace(",", ""))
    if _EN_EINFACH.fullmatch(roh):
        return _wert(roh)
    return None


def wert_deutsch(roh: str) -> str | None:
    if _DE_GRUPPEN.fullmatch(roh):
        return _wert(roh.replace(".", "").replace(",", "."))
    if _DE_RAUM.fullmatch(roh):
        return _wert(re.sub(r"[\u00a0\u202f\u2009]", "", roh).replace(",", "."))
    if _DE_EINFACH.fullmatch(roh):
        return _wert(roh.replace(",", "."))
    return None


@dataclass(frozen=True)
class Vergleich:
    fehlt: list[str]                                 # im Original, nicht in der Übersetzung
    dazu: list[str]                                  # in der Übersetzung, nicht im Original
    englisch_geschrieben: list[str]                  # unverändert, heißt im Deutschen aber anderes


def _zahlwort_deutsch(wort: str) -> int | None:
    """Die Zahl eines deutschen Zahlworts, auch vorn in einem Wort (vierstufig, Zweifach); None, wenn es keins ist."""
    z, w = zahlwoerter(), wort.lower()
    if w in z.deutsch_allein:
        return z.deutsch_allein[w]
    if w.startswith(z.keine):
        return None
    stamm = next((s for s in sorted(z.deutsch, key=len, reverse=True) if w.startswith(s)), None)
    if stamm is None or w[len(stamm):].startswith(z.groesser):
        return None
    return z.deutsch[stamm]


def zahlwoerter_deutsch(text: str) -> Counter[int]:
    return Counter(n for w in WORT.findall(text) if (n := _zahlwort_deutsch(w)) is not None)


def zahlwoerter_englisch(text: str) -> Counter[int]:
    englisch = zahlwoerter().englisch
    return Counter(englisch[w.lower()] for w in WORT.findall(text) if w.lower() in englisch)


def _ohne_zahlwoerter(rest: list[str], woerter: Counter[int], wert) -> list[str]:
    """Was von übrigen Zahlen bleibt, wenn je Zahlwort der anderen Seite eine mit seinem Wert wegfällt."""
    woerter = woerter.copy()
    uebrig = []
    for roh in rest:
        w = wert(roh)
        n = int(w) if w is not None and w.isdigit() else None
        if n is not None and woerter[n] > 0:
            woerter[n] -= 1
        else:
            uebrig.append(roh)
    return uebrig


def _ziffern(zahlen: list[str]) -> Counter:
    return Counter(str(int(z)) for roh in zahlen for z in re.findall(r"\d+", roh))


def vergleichen(original: str, deutsch: str) -> Vergleich:
    en, de = ZAHL.findall(original), ZAHL.findall(deutsch)
    englisch_geschrieben = []
    for roh in list(en):                             # 1. gleich geschrieben
        if roh in de:
            en.remove(roh)
            de.remove(roh)
            if (d := wert_deutsch(roh)) is not None and d != wert_englisch(roh):
                englisch_geschrieben.append(roh)
    for roh in list(en):                             # 2. gleicher Wert
        w = wert_englisch(roh)
        treffer = next((x for x in de if w is not None and wert_deutsch(x) == w), None)
        if treffer is not None:
            en.remove(roh)
            de.remove(treffer)
    en = _ohne_zahlwoerter(en, zahlwoerter_deutsch(deutsch), wert_englisch)    # 3. Zahlwörter der anderen Seite
    de = _ohne_zahlwoerter(de, zahlwoerter_englisch(original), wert_deutsch)
    if _ziffern(en) == _ziffern(de):                 # 4. Ziffernfolgen des Rests
        return Vergleich(fehlt=[], dazu=[], englisch_geschrieben=englisch_geschrieben)
    return Vergleich(fehlt=en, dazu=de, englisch_geschrieben=englisch_geschrieben)
