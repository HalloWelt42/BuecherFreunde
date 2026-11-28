"""Textansicht eines PDF: Seiten als Folge von Bausteinen (Absätze, Überschriften, Kästen, Abbildungen)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TextTabelle(BaseModel):
    """Eine Tabelle (aus der Nachbesserung, BF-118): Kopf, Reihen, je Spalte, ob sie nur Zahlen trägt (rechtsbündig)."""

    kopf: list[str]
    reihen: list[list[str]]
    zahlen: list[bool]


class TextBaustein(BaseModel):
    """Ein Baustein einer Seite. Abbildungen tragen ihre Nummer auf der Seite (Bild-Endpunkt), das Seitenverhältnis
    (damit die Oberfläche den Platz freihält, bevor das Bild geladen ist) und ihre Breite im Verhältnis zur Schrift des
    Fließtexts, damit Formeln und Abbildungen mit der eingestellten Schriftgröße mitwachsen. Codestellen kommen als "code"
    mit ihren Zeilen statt als Ausschnitt."""

    art: Literal["absatz", "ueberschrift", "unterschrift", "kasten", "bild", "code", "tabelle"]
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
    tabelle: TextTabelle | None = None


class TextSeite(BaseModel):
    """Eine Dateiseite; ohne Bausteine, wenn sie keinen lesbaren Text und keine Abbildung trägt (Scan). `schicht` sagt, woher
    ihr Text kommt (BF-109): aus der Textschicht des PDF, aus ihrer Erkennung, noch gar nicht (die Erkennung kommt, mit
    Vorrang über POST /api/books/{id}/texterkennung/vorrang) oder nie (ohne lesbaren Text und ohne Erkennung)."""

    nr: int
    gedruckt: str = ""
    bausteine: list[TextBaustein]
    schicht: Literal["pdf", "erkannt", "wartet", "ohne"] = "pdf"
    # Nachbesserung einer erkannten Seite (BF-118): welche Fassung gilt, ob es die andere gibt, und wo die Nachbesserung steht
    fassung: Literal["klassisch", "ki"] | None = None
    andere_fassung: bool = False
    nachbesserung: Literal["", "wartet", "fehler"] = ""
    nachbesserung_grund: str = ""


class TextSeitenAntwort(BaseModel):
    """Ein Ausschnitt der Seiten ab einer Dateiseite."""

    gesamt: int
    seiten: list[TextSeite]
