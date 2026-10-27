"""Textansicht eines PDF: Seiten als Folge von Bausteinen (Absätze, Überschriften, Kästen, Abbildungen)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TextBaustein(BaseModel):
    """Ein Baustein einer Seite. Abbildungen tragen ihre Nummer auf der Seite (Bild-Endpunkt) und das Seitenverhältnis,
    damit die Oberfläche den Platz freihält, bevor das Bild geladen ist."""

    art: Literal["absatz", "ueberschrift", "unterschrift", "kasten", "bild"]
    text: str = ""
    titel: str = ""
    inhalt: list[TextBaustein] = Field(default_factory=list)
    bild: int | None = None
    verhaeltnis: float | None = None


class TextSeite(BaseModel):
    """Eine Dateiseite; ohne Bausteine, wenn sie keinen lesbaren Text und keine Abbildung trägt (Scan)."""

    nr: int
    gedruckt: str = ""
    bausteine: list[TextBaustein]


class TextSeitenAntwort(BaseModel):
    """Ein Ausschnitt der Seiten ab einer Dateiseite."""

    gesamt: int
    seiten: list[TextSeite]
