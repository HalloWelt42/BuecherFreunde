"""Was alle Quellen gemeinsam verstehen und liefern: die Frage nach einem Buch, Angaben mit Herkunft je Feld, Angaben zu
einem Autor."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Fund = Literal["isbn", "doi", "titel", ""]


class Buchfrage(BaseModel):
    isbn: str = ""
    titel: str = ""
    autoren: list[str] = Field(default_factory=list)
    jahr: int | None = None
    sprache: str = ""
    seiten: int = 0
    doi: str = ""


class Angaben(BaseModel):
    """Angaben zu einem Buch aus einer Quelle oder, mit Herkunft je Feld, aus mehreren."""

    quelle: str = ""
    fund: Fund = ""                                    # worüber gefunden
    sicher: bool = True                                # bei Titelsuche: Titel und Autor stimmen genau
    titel: str = ""
    untertitel: str = ""
    autoren: list[str] = Field(default_factory=list)
    verlag: str = ""
    jahr: int | None = None
    seiten: int = 0
    isbn: str = ""
    isbns: list[str] = Field(default_factory=list)     # alle Schreibweisen und Ausgaben des Fundes
    doi: str = ""
    sprache: str = ""
    beschreibung: str = ""
    kategorien: list[str] = Field(default_factory=list)
    umschlag: str = ""                                 # Adresse eines Bildes
    personen: dict[str, str] = Field(default_factory=dict)      # Name -> Kennung in der Normdatei
    herkunft: dict[str, str] = Field(default_factory=dict)      # Feld -> Kennung der Quelle
    roh: dict[str, Any] = Field(default_factory=dict)


FELDER = ("titel", "untertitel", "autoren", "verlag", "jahr", "seiten", "isbn", "doi", "sprache", "beschreibung", "kategorien", "umschlag")


class Werk(BaseModel):
    titel: str
    wikidata_id: str = ""


class Autorfrage(BaseModel):
    name: str
    titel: list[str] = Field(default_factory=list)
    isbns: list[str] = Field(default_factory=list)


class Autorangaben(BaseModel):
    """Angaben zu einem Autor, wie sie der Vergleich zeigt; `verweise` sind Kennungen in Normdateien (gnd, viaf, isni)."""

    name: str = ""
    wikidata_id: str = ""
    biography: str = ""
    beschreibung: str = ""
    birth_year: int | None = None
    death_year: int | None = None
    nationality: str = ""
    photo_url: str = ""
    wikipedia_url: str = ""
    website: str = ""
    konfidenz: str = "niedrig"
    score: int = 0
    quelle: str = ""
    werke: list[Werk] = Field(default_factory=list)
    verweise: dict[str, str] = Field(default_factory=dict)
    herkunft: dict[str, str] = Field(default_factory=dict)
