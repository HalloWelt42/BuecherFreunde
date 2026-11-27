"""Was die Texterkennung über eine Seite festhält: eine Zeile in `erkennung.jsonl` (ablage.py)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Herkunft = Literal["klassisch", "ki"]           # klassisch: das Programm der Erkennung; ki: die Nachbesserung (später)
Lage = tuple[float, float, float, float]        # x0, y0, x1, y1 in PDF-Punkten, wie die Textschicht der Seite


class Wort(BaseModel):
    text: str
    lage: Lage
    sicherheit: int = Field(ge=0, le=100)       # wie sicher das Programm ist, 0 bis 100


class ErkannteZeile(BaseModel):
    """Eine Zeile, wie das Programm sie gliedert: in Block und Absatz, die Wörter von links nach rechts."""
    block: int
    absatz: int
    zeile: int
    woerter: list[Wort]


class Seitenerkennung(BaseModel):
    """Eine erkannte Dateiseite (ab 1) mit Herkunft, Werkzeug, Fassung und Zeit; `flaechen` sind Blöcke ohne Text (Bilder,
    Linien), wie das Programm sie abgrenzt."""
    seite: int = Field(ge=1)
    herkunft: Herkunft = "klassisch"
    werkzeug: str
    fassung: str
    sprachen: str
    dpi: int
    erkannt_am: str                             # Zeitpunkt in UTC, ISO 8601
    dauer_s: float
    zeilen: list[ErkannteZeile] = Field(default_factory=list)
    flaechen: list[Lage] = Field(default_factory=list)


Erkennungen = dict[int, Seitenerkennung]        # je Dateiseite die geltende (jüngste) Erkennung
