"""Textansicht eines PDF: Seiten als Folge von Bausteinen (Absätze, Überschriften, Kästen, Abbildungen)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TextBaustein(BaseModel):
    """Ein Baustein einer Seite. Abbildungen tragen ihre Nummer auf der Seite (Bild-Endpunkt), das Seitenverhältnis
    (damit die Oberfläche den Platz freihält, bevor das Bild geladen ist) und ihre Breite im Verhältnis zur Schrift des
    Fließtexts, damit Formeln und Abbildungen mit der eingestellten Schriftgröße mitwachsen. Codestellen kommen als "code"
    mit ihren Zeilen statt als Ausschnitt."""

    art: Literal["absatz", "ueberschrift", "unterschrift", "kasten", "bild", "code"]
    text: str = ""
    titel: str = ""
    inhalt: list[TextBaustein] = Field(default_factory=list)
    bild: int | None = None
    verhaeltnis: float | None = None
    breite_em: float | None = None
    # Codestellen (BF-29): die Zeilen dieses Teils, die Sprache (None: unbekannt), die Kennung der Stelle wie unter
    # /api/books/{id}/codestellen und der wievielte Teil von wie vielen (über Seitenwechsel; aufeinanderfolgende Teile einer
    # Stelle gehören am Stück gezeichnet)
    zeilen: list[str] = Field(default_factory=list)
    sprache: str | None = None
    kennung: str = ""
    teil: int | None = None
    teile: int | None = None


class TextSeite(BaseModel):
    """Eine Dateiseite; ohne Bausteine, wenn sie keinen lesbaren Text und keine Abbildung trägt (Scan)."""

    nr: int
    gedruckt: str = ""
    bausteine: list[TextBaustein]


class TextSeitenAntwort(BaseModel):
    """Ein Ausschnitt der Seiten ab einer Dateiseite."""

    gesamt: int
    seiten: list[TextSeite]
