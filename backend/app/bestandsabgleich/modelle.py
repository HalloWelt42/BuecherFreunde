"""Was die Erweiterung schickt und zurückbekommt (BF-119)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from backend.app.models.book import Umschlag

AEHNLICH_AB = 0.8                     # Vorgabe: so nah muss ein Titel sein, um als ähnlich zu gelten (die Erweiterung stellt ein)
TREFFER_JE_ANGEBOT = 3                # so viele Kandidaten zeigt der Einblick zum Blättern
TREFFER_DER_SUCHE = 8

_Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
_Name = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
_Nummer = Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]
_Ab = Annotated[float, Field(ge=0.5, le=0.99)]


class Angebot(BaseModel):
    """Ein Buch, wie eine fremde Seite es anbietet; nur der Titel ist Pflicht."""

    nr: int = Field(ge=0, le=100_000)                        # Lage auf der Seite, die Antwort nennt sie wieder
    titel: _Text
    untertitel: _Text = ""
    autoren: list[_Name] = Field(default_factory=list, max_length=12)
    isbn: list[_Nummer] = Field(default_factory=list, max_length=8)
    jahr: int | None = Field(None, ge=1000, le=2200)
    ausgabe: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ""   # "Taschenbuch", "EPUB": nur zum Zeigen


class Abgleichfrage(BaseModel):
    angebote: list[Angebot] = Field(max_length=300)
    aehnlich_ab: _Ab = AEHNLICH_AB


class Suchfrage(BaseModel):
    """Freier Text, etwa markiert auf einer Seite: ein Titel oder ein Name."""

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=300)]
    aehnlich_ab: _Ab = AEHNLICH_AB


class Fundart(StrEnum):
    """Die Reihenfolge ist die Rangfolge."""

    VORHANDEN = "vorhanden"          # gleiche ISBN, oder Titel und Autor passen
    AEHNLICH = "aehnlich"            # Titel nah, aber Auflage, Autor oder ein Teil weichen ab


FUNDARTEN: tuple[Fundart, ...] = tuple(Fundart)


class Vergleichszeile(BaseModel):
    feld: str                        # Titel, Autor, Auflage, Jahr, ISBN, Format
    seite: str                       # was die fremde Seite nennt
    mein: str                        # was in der Bibliothek steht
    gleich: bool


class Buchkurz(BaseModel):
    """Was der Einblick vom eigenen Buch zeigt; die Felder fürs Deckblatt heißen wie in der Buchliste."""

    id: int
    title: str
    author: str
    year: int | None = None
    publisher: str = ""
    isbn: str = ""
    beschreibung: str = ""           # gekürzt
    formate: list[str] = Field(default_factory=list)
    regale: list[str] = Field(default_factory=list)  # Regale, sonst Kategorien
    typ: str = ""
    gattung: str = ""
    file_format: str = ""
    cover_path: str = ""
    umschlag: Umschlag = "titelseite"
    cover_stand: int = 0
    gelesen: float = 0.0             # 0 bis 1 für dieses Profil
    fertig: bool = False


class Treffer(BaseModel):
    buch: Buchkurz
    art: Fundart
    naehe: float                     # 0 bis 1, Nähe des Titels
    grund: str                       # in wenigen Worten, für den Kopf des Einblicks
    vergleich: list[Vergleichszeile] = Field(default_factory=list)


class Ergebnis(BaseModel):
    nr: int
    treffer: list[Treffer]           # der beste zuerst


class Abgleichantwort(BaseModel):
    ergebnisse: list[Ergebnis]       # nur Angebote mit mindestens einem Treffer
    geprueft: int                    # so viele Angebote kamen an


class Suchantwort(BaseModel):
    treffer: list[Treffer]
