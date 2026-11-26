"""Zahlen im Original und in der Übersetzung vergleichen (BF-71), nach Angleichen der Tausender- und Dezimalzeichen.

Englisch schreibt 16,000 und 1.5, Deutsch 16.000 (oder 16 000 mit schmalem Leerzeichen) und 1,5. Verglichen wird in drei
Gängen: erst gleich geschriebene Zahlen (eine Version 3.12 bleibt 3.12), dann gleiche Werte (16,000 = 16.000; 1.5 = 1,5),
zuletzt die Ziffernfolgen dessen, was übrig ist (ein Datum 11/26/2026 darf 26.11.2026 werden). Was danach fehlt oder dazukam,
ist ein Befund; ebenso eine Zahl, die unverändert stehen blieb, im Deutschen aber anderes heißt (16,000 hieße 16).

Nur Ziffern zählen; Zahlwörter (three, drei) und Vorzeichen bleiben außen vor."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

ZAHL = re.compile(r"\d{1,3}(?:[\u00a0\u202f\u2009]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)*")
_EN_GRUPPEN = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")
_EN_EINFACH = re.compile(r"\d+(?:\.\d+)?")
_DE_GRUPPEN = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?")
_DE_RAUM = re.compile(r"\d{1,3}(?:[\u00a0\u202f\u2009]\d{3})+(?:,\d+)?")
_DE_EINFACH = re.compile(r"\d+(?:,\d+)?")


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
    if _ziffern(en) == _ziffern(de):                 # 3. Ziffernfolgen des Rests
        return Vergleich(fehlt=[], dazu=[], englisch_geschrieben=englisch_geschrieben)
    return Vergleich(fehlt=en, dazu=de, englisch_geschrieben=englisch_geschrieben)
