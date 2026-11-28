"""Was die Textansicht über eine Seite liefert: Bausteine in Lesereihenfolge, Codeteile darin, und welche Textschicht gilt."""

from __future__ import annotations

from dataclasses import dataclass, field

import fitz

from backend.app.texterkennung.textschicht import Schichtart


@dataclass
class Codeteil:
    """Ein Teil einer erkannten Codestelle auf dieser Seite (aus dem Begleiter codestellen.json); Code, den die Textansicht
    selbst erkennt (Festbreite, Tafel, lose Codezeilen), trägt keine Kennung."""
    rechteck: fitz.Rect
    kennung: str
    sprache: str | None
    titel: str
    teil: int                   # der wievielte Teil der Stelle, ab 0
    teile: int                  # so viele Teile hat die Stelle (über Seitenwechsel)
    zeilen: list[str]


@dataclass
class Tabelle:
    """Eine Tabelle der Nachbesserung (BF-118): Kopf, Reihen mit je so vielen Zellen, je Spalte, ob sie nur Zahlen trägt."""
    kopf: list[str]
    reihen: list[list[str]]
    zahlen: list[bool]


@dataclass
class Baustein:
    art: str                    # absatz, ueberschrift, unterschrift, kasten, bild, code, tabelle
    oben: float
    links: float
    text: str = ""
    titel: str = ""
    inhalt: list[Baustein] = field(default_factory=list)   # Absätze und Bilder eines Kastens
    rechteck: fitz.Rect | None = None
    bild: int | None = None     # Nummer der Abbildung auf der Seite (Bild-Endpunkt)
    breite_em: float | None = None  # Breite einer Abbildung in Schriftgrößen des Fließtexts
    code: Codeteil | None = None    # bei art "code"
    tabelle: Tabelle | None = None  # bei art "tabelle"


@dataclass
class Textseite:
    """Eine gelesene Dateiseite: ihre Bausteine und woher ihr Text kommt (texterkennung/textschicht.py)."""
    nr: int
    bausteine: list[Baustein]
    schicht: Schichtart
