"""Fassungen eines Buchs und ihre Übersetzung (BF-71): was die Schnittstelle zeigt und annimmt (docs/neubau/UEBERSETZUNG.md)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, model_validator

from backend.app.models.grenzen import BEGRIFF, BEGRIFF_GRUND, BLOCKTEXT
from backend.app.uebersetzung.modelle import Befund

Stand = Literal["laeuft", "pause", "teilweise", "fertig", "fehler"]
Blockstand = Literal["wartet", "uebersetzt", "nacharbeit", "bestanden", "nachgearbeitet", "offen", "angenommen", "gesetzt"]
Stationsname = Literal["Zerlegen", "Begriffe", "Übersetzen", "Prüfen", "Nacharbeit", "Setzen"]
Stationsstand = Literal["wartet", "laeuft", "fertig"]
Herkunft = Literal["regel", "ki", "hand", "vorgabe"]
Begriffsart = Literal["begriff", "einheit"]

#: Blöcke, deren deutscher Text in der Fassung steht
MIT_DEUTSCH: tuple[Blockstand, ...] = ("bestanden", "nachgearbeitet", "angenommen", "gesetzt")
#: Blöcke, an denen der Lauf noch arbeitet
IN_ARBEIT: tuple[Blockstand, ...] = ("wartet", "uebersetzt", "nacharbeit")
#: Blöcke, die die KI hervorgebracht hat; eine Änderung der Begriffsliste setzt nur sie zurück
VON_DER_KI: tuple[Blockstand, ...] = ("uebersetzt", "nacharbeit", "bestanden", "nachgearbeitet", "offen")


class FassungEintrag(BaseModel):
    id: int | None                                   # das Original: None
    sprache: str
    original: bool
    stand: Stand
    kapitel_fertig: int | None = None
    kapitel_gesamt: int | None = None
    fertig_gegen: str | None = None                  # geschätzt, Zeitpunkt (UTC, ISO)
    modell: str = ""
    pruefmodell: str = ""
    angelegt: str
    geaendert: str


class Ablageort(BaseModel):
    ort: Literal["kellerwolke", "geraet"]
    pfad: str                                        # in der Kellerwolke, sonst auf dem Gerät


class Folgen(BaseModel):
    """Rückfrage vor dem Start: was das Übersetzen bedeutet; `geht` false mit Grund, wenn es nicht geht."""
    seiten: int = 0
    kapitel: int = 0
    bloecke: int = 0
    begriffe: int = 0
    abbildungen: int = 0
    dauer_s: float = 0
    fertig_gegen: str | None = None
    tempo_s_je_seite: float = 0
    ablage: Ablageort | None = None
    geht: bool
    grund: str = ""


class Station(BaseModel):
    name: Stationsname
    stand: Stationsstand
    text: str = ""


class KapitelStand(BaseModel):
    nr: int
    titel: str
    stand: Stationsstand
    dauer_s: float                                   # gemessen, oder (geschaetzt) gemessen und erwartet
    geschaetzt: bool
    bloecke: int
    fertig: int                                      # mit Ergebnis: übersetzt, offen, angenommen oder gesetzt
    geprueft: int                                    # vom KI-Prüfer beurteilt
    nachgearbeitet: int
    offen: int


class Zahlen(BaseModel):
    bloecke: int = 0
    uebersetzt: int = 0                              # deutscher Text in der Fassung (bestanden, nachgearbeitet, angenommen, gesetzt)
    bestanden: int = 0                               # im ersten Versuch durch alle Prüfungen
    nachgearbeitet: int = 0                          # nach Nacharbeit durch alle Prüfungen
    offen: int = 0                                   # im Original, im Bericht


class FassungStand(BaseModel):
    id: int
    stand: Stand
    begonnen: str | None = None
    bisher_s: float = 0
    noch_s: float = 0
    fertig_gegen: str | None = None
    tempo_s_je_seite: float = 0
    kapitel_jetzt: int | None = None
    block_jetzt: str | None = None
    stationen: list[Station]
    kapitel: list[KapitelStand]
    zahlen: Zahlen
    grund: str = ""


class OffeneStelle(BaseModel):
    kennung: str
    kapitel: int
    ort: str                                         # für Menschen, etwa "Getting Started, Absatz 4"
    seite_original: int | None = None                # nur bei PDF
    original: str                                    # Vorlage mit Marken
    deutsch: str                                     # die letzte Übersetzung, mit Marken; leer, wenn keine kam
    befunde: list[Befund]


class Bericht(BaseModel):
    zahlen: Zahlen
    offen: list[OffeneStelle]


class BlockAktion(BaseModel):
    aktion: Literal["neu", "annehmen", "setzen"]
    text: Annotated[str, StringConstraints(max_length=BLOCKTEXT)] | None = None

    @model_validator(mode="after")
    def _text_bei_setzen(self) -> BlockAktion:
        if self.aktion == "setzen" and not (self.text or "").strip():
            raise ValueError("Zum Setzen gehört ein Text")
        return self


class BlockAntwort(BaseModel):
    kennung: str
    stand: Blockstand
    deutsch: str
    befunde: list[Befund]


class BegriffEintrag(BaseModel):
    id: int
    englisch: str
    deutsch: str
    bleibt: bool
    herkunft: Herkunft
    stellen: int
    grund: str
    art: Begriffsart = "begriff"


Englisch = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=BEGRIFF)]
Deutsch = Annotated[str, StringConstraints(strip_whitespace=True, max_length=BEGRIFF)]
Grund = Annotated[str, StringConstraints(strip_whitespace=True, max_length=BEGRIFF_GRUND)]


class BegriffNeu(BaseModel):
    englisch: Englisch
    deutsch: Deutsch = ""
    bleibt: bool = False
    grund: Grund = ""
    art: Begriffsart = "begriff"

    @model_validator(mode="after")
    def _form(self) -> BegriffNeu:
        if not self.bleibt and not self.deutsch:
            raise ValueError("Ein Begriff bleibt englisch oder hat eine deutsche Form")
        return self


class BegriffAenderung(BaseModel):
    englisch: Englisch | None = None
    deutsch: Deutsch | None = None
    bleibt: bool | None = None
    grund: Grund | None = None
    art: Begriffsart | None = None
