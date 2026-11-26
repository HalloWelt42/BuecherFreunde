"""Altersangaben aus den Quellen (BF-78): Lese- oder Interessenalter eines Buchs, nur Hilfe beim Freigeben für Kinder, nie eine
Freigabe. Bibliothekskataloge (MARC 21) nennen es in der Zielgruppe (Feld 521, etwa "ab 8 Jahren", "Lesealter 6 - 8 J.",
"Interessenalter: 10-12") oder als Kennbuchstaben der Zielgruppe (Feld 008, Stelle 22 bei Büchern)."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

HOECHSTENS = 99
# Bindestrich, Gedankenstrich oder "bis" zwischen zwei Zahlen; der Gedankenstrich kommt aus den Daten der Kataloge
_BIS = r"(?:-|\u2013|\u2014|bis|to)"
_JAHRE = r"(?:\s*(?:J\b|J\.|Jahre?n?|Jhr\.?|years?|yrs?\.?))?"
_SPANNE = re.compile(rf"(?<!\d)(\d{{1,2}})\s*{_BIS}\s*(\d{{1,2}})(?!\d){_JAHRE}", re.IGNORECASE)
_AB = re.compile(rf"(?:\bab|\bfrom|\bage[sd]?|\bover)\s*(\d{{1,2}})(?!\d)\s*\+?{_JAHRE}", re.IGNORECASE)
_BIS_ZU = re.compile(rf"\b(?:bis|unter|up to|under)\s*(\d{{1,2}})(?!\d){_JAHRE}", re.IGNORECASE)
_PLUS = re.compile(r"\b(\d{1,2})(?!\d)\s*\+")
_ALTER = re.compile(r"alter|jahr|\bj\b|j\.|age|year|yrs|\+", re.IGNORECASE)
# MARC 21, 008/22 bei Büchern: a Vorschulalter, b Grundschule, c vor der Jugend, d Jugend; j allgemein Kinder (ohne Alter)
_ZIELGRUPPE = {"a": (0, 5), "b": (6, 8), "c": (9, 13), "d": (14, 17)}


class Alter(BaseModel):
    von: int | None = Field(None, ge=0, le=HOECHSTENS)
    bis: int | None = Field(None, ge=0, le=HOECHSTENS)


def _passend(von: int | None, bis: int | None) -> Alter | None:
    if von is not None and not 0 <= von <= HOECHSTENS or bis is not None and not 0 <= bis <= HOECHSTENS:
        return None
    if von is not None and bis is not None and bis < von:
        return None
    return Alter(von=von, bis=bis) if von is not None or bis is not None else None


def aus_text(text: str) -> Alter | None:
    """Das Alter aus einer Angabe zur Zielgruppe; None, wenn darin keins steht."""
    if not text or not _ALTER.search(text):
        return None
    if m := _SPANNE.search(text):
        return _passend(int(m.group(1)), int(m.group(2)))
    if m := _AB.search(text) or _PLUS.search(text):
        return _passend(int(m.group(1)), None)
    if m := _BIS_ZU.search(text):
        return _passend(None, int(m.group(1)))
    return None


def aus_zielgruppe(kennbuchstabe: str) -> Alter | None:
    if spanne := _ZIELGRUPPE.get(kennbuchstabe.strip().lower()):
        return Alter(von=spanne[0], bis=spanne[1])
    return None
