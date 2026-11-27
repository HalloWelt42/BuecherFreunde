"""Formen des Vorlesens: Stimmen und ihre Bereiche, wie die Vertonung sie anbietet, die Beschreibung ihrer Einstellungen und die
Form gespeicherter Stimmwerte.

Eine Stimme heißt, wie die Vertonung sie schreibt: `katalog:<name>` für eine eingebaute, die Kennung (UUID) für eine Klonstimme,
privat oder fremd. Dazu kommt `geraet`, die Stimme des Geräts als ausdrückliche Wahl; die spricht die Oberfläche selbst. Im Leser
nennt ein Erwachsener auch eine bestimmte Stimme seines Browsers (`geraet:<Name der Stimme>`)."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from appkern.vorlesen import KATALOG
from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt, StringConstraints

GERAET = "geraet"
#: was die Vertonung spricht: eine eingebaute Stimme oder eine Klonstimme
VERTONT = r"katalog:.{1,150}|[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}"

# eine Stimme der Vertonung, die des Geräts oder keine (feste Ansagen, Stimme der Familie, Stimme eines Kindes)
Stimmwahl = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200, pattern=rf"^(?:{VERTONT}|{GERAET})?$")]
# im Leser dazu eine bestimmte Stimme des Browsers
Leserstimme = Annotated[str, StringConstraints(strip_whitespace=True, max_length=220, pattern=rf"^(?:{VERTONT}|{GERAET}(?::.{{1,200}})?)?$")]

Bereich = Literal["privat", "fremd", "katalog"]
Sprechwert = StrictBool | StrictInt | StrictFloat | Annotated[str, StringConstraints(max_length=500)]
Wertname = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]
Sprechwerte = Annotated[dict[Wertname, Sprechwert], Field(max_length=30)]


def vertont(stimme: str) -> bool:
    """Spricht die Vertonung diese Stimme? (Die des Geräts spricht die Oberfläche, ohne Stimme spricht niemand.)"""
    return bool(re.fullmatch(VERTONT, stimme))


def name_im_katalog(stimme: str) -> str:
    return stimme.removeprefix(KATALOG)


# -- Stimmen ----------------------------------------------------------------------------------------------------------------------

class Stimme(BaseModel):
    id: str                                   # wie die Vertonung sie schreibt
    name: str
    bereich: Bereich
    sprache: str | None = None                # die Sprache der Probe einer Klonstimme


class Bereichsstand(BaseModel):
    bereich: Bereich
    frei: bool                                # gibt die Vertonung ihn dieser App frei?
    hinweis: str = ""                         # gesperrt: Grund und Weg zur Freigabe


class Stimmenliste(BaseModel):
    da: bool                                  # die Vertonung ist eingetragen und hat geantwortet
    stimmen: list[Stimme]
    bereiche: list[Bereichsstand]             # in der Folge der Vertonung: privat, fremd, eingebaut
    hinweis: str = ""                         # warum es keine oder nicht alle gibt


# -- Beschreibung der Einstellungen ----------------------------------------------------------------------------------------------

Feldart = Literal["zahl", "ganzzahl", "schalter", "text", "wahl"]


class Wahlwert(BaseModel):
    wert: str
    name: str


class Feld(BaseModel):
    """Eine Einstellung zum Sprechen, so wie die Vertonung sie beschreibt; Name aus beschriftungen.json, sonst ihr eigener."""

    schluessel: str                           # so heißt das Feld bei der Vertonung
    name: str
    art: Feldart
    von: float | None = None                  # Grenzen einer Zahl
    bis: float | None = None
    vorgabe: Sprechwert | None = None         # was gilt, wenn nichts gewählt ist
    werte: list[Wahlwert] = Field(default_factory=list)   # bei einer Wahl
    erklaerung: str = ""
    mehr: bool = False                        # unbekannt: steht unter "Mehr"


class Beschreibung(BaseModel):
    da: bool                                  # die Vertonung hat sie geliefert
    felder: list[Feld]
    hinweis: str = ""                         # warum es keine gibt


# -- je Profil -------------------------------------------------------------------------------------------------------------------

class Vorlesewahl(BaseModel):
    """Gespeichert je Profil (profil.einstellungen.vorlesen): im Leser die Stimme eines Erwachsenen (ein Kind hört die Wahl der
    Eltern, `lesehilfen.stimme`) und die Werte nach der Beschreibung der Vertonung."""

    stimme: Leserstimme | None = None         # leer: noch keine Wahl, es gilt die Stimme ab Werk der Vertonung
    werte: Sprechwerte = Field(default_factory=dict)


class Vorlesestand(BaseModel):
    """Was für das aktive Profil gilt (`GET /api/familie/ich`, `vorlesen`)."""

    stimme: str                               # leer: die Stimme ab Werk der Vertonung
    werte: dict[str, Sprechwert]
    eigene_wahl: bool                         # das Profil wählt im Leser selbst (Erwachsene), sonst die Eltern
