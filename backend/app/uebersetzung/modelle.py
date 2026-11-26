"""Was die Fachschicht der Übersetzung kennt (BF-71): Blöcke, Befunde, Begriffe und die Anfrage an die KI."""

from __future__ import annotations

import hashlib
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from backend.app.uebersetzung.bloecke import Art

#: Arten von Befunden: die neun festen Prüfungen, eine unbrauchbare Antwort, die Arten des KI-Prüfers
Befundart = Literal["marken", "zahlen", "einheiten", "bezeichner", "begriffe", "sprache", "laenge", "vollstaendigkeit", "zeichen",
                    "antwort", "sinn", "ausgelassen", "hinzugefuegt", "begriff", "grammatik", "pruefer"]
KI_ARTEN: tuple[Befundart, ...] = ("sinn", "ausgelassen", "hinzugefuegt", "begriff", "grammatik")


class Befund(BaseModel):
    art: Befundart
    quelle: Literal["pruefung", "ki"]
    text: str                                        # ein deutscher Satz
    stelle: str = ""                                 # das beanstandete Stück im deutschen Text


class Block(BaseModel):
    """Ein Block zum Übersetzen. Die Kennung verbindet Original und Übersetzung: Kapitel und Stelle im Kapitel."""
    kennung: str                                     # etwa "3.17"
    kapitel: int
    nr: int                                          # ab 1 im Kapitel
    art: Art
    stufe: int = 0
    vorlage: str                                     # Text mit Marken
    woerter: int = 0

    @property
    def pruefsumme(self) -> str:
        return pruefsumme(self.vorlage)


def pruefsumme(vorlage: str) -> str:
    return hashlib.sha256(vorlage.encode("utf-8")).hexdigest()


class Begriff(BaseModel):
    """Ein Eintrag der Begriffsliste: bleibt englisch, oder hat eine vereinbarte deutsche Form."""
    englisch: str
    deutsch: str = ""
    bleibt: bool = False
    art: Literal["begriff", "einheit"] = "begriff"


class Kandidat(BaseModel):
    """Ein Begriff, den Regeln oder die KI vorschlagen, mit Grund und wie oft er im Buch steht."""
    englisch: str
    deutsch: str = ""
    bleibt: bool = True
    grund: str = ""
    stellen: int = 0
    herkunft: Literal["regel", "ki"] = "regel"


class Laengengrenzen(BaseModel):
    """Verhältnis der Länge Deutsch zu Englisch je Block; erst ab `ab_zeichen` im Original sagt es etwas."""
    kleinst: float = Field(0.8, gt=0)
    groesst: float = Field(1.8, gt=0)
    ab_zeichen: int = Field(60, ge=0)


class Unbrauchbar(Exception):
    """Diese eine Antwort der KI taugt nicht (Form, Anzahl, nicht lesbar); andere Anfragen können gelingen."""


class Anfrage(Protocol):
    """Eine Anfrage an die KI mit fester Antwortform; wirft Unbrauchbar, wenn nur diese Antwort nicht taugt. Alles andere
    (die KI ist weg, ein Mensch ist gefragt) geht unverändert an den Rufer des Laufs."""

    async def __call__(self, system: str, nutzer: str, *, schema_name: str, schema: dict[str, Any], titel: str,
                       modell: str = "") -> Any: ...
