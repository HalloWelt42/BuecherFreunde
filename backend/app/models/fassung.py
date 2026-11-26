"""Fassungen eines Buchs und ihre Übersetzung (BF-71): was die Schnittstelle zeigt und annimmt (docs/neubau/UEBERSETZUNG.md)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from backend.app.models.grenzen import AUSWAHL_HOECHSTENS, BEGRIFF, BEGRIFF_GRUND, BLOCKTEXT, Leseposition, Nr
from backend.app.uebersetzung.modelle import Anrede, Befund

Stand = Literal["laeuft", "pause", "teilweise", "fertig", "fehler"]
Zielsprache = Literal["de"]                          # Sprachen, in die übersetzt wird
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
#: Blöcke der KI mit einem Urteil der festen Prüfungen; ändern sich die Prüfungen, werden sie neu geprüft
NACHZUPRUEFEN: tuple[Blockstand, ...] = ("uebersetzt", "bestanden", "nachgearbeitet", "offen")


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
    gewaehlt: bool = False                           # diese Fassung öffnet "Lesen" auf der Buchseite
    anrede: Anrede | None = None                     # so spricht die Fassung den Leser an; beim Original None


class Fassungswahl(BaseModel):
    """Welche Fassung "Lesen" öffnet; die Wahl gilt je Buch auf jedem Gerät."""
    sprache: Zielsprache | None = None               # None: das Original


class LaufEintrag(BaseModel):
    """Eine Fassung in Arbeit (läuft, Pause oder Fehler), für die Liste der Aufträge."""
    id: int
    buch_id: int
    titel: str                                       # Titel des Buchs
    sprache: str
    stand: Stand
    anteil: float                                    # Blöcke mit Ergebnis an allen, 0 bis 1; 0 vor dem Zerlegen
    kapitel_fertig: int = 0
    kapitel_gesamt: int = 0
    fertig_gegen: str | None = None                  # geschätzt, Zeitpunkt (UTC, ISO), nur solange sie läuft
    grund: str = ""


class Lesestand(BaseModel):
    """Wo man in einer Übersetzung liest; der Lesestand des Originals bleibt davon unberührt."""
    position: str = ""                               # wie die Leseposition eines Buchs, leer: noch nicht gelesen
    gelesen_am: str | None = None


class LesestandNeu(BaseModel):
    position: Leseposition


class FassungStart(BaseModel):
    """Was der Start annehmen kann: die Anrede für eine neue Fassung; ohne Angabe die Vorgabe (UEBERSETZEN_ANREDE)."""
    anrede: Anrede | None = None


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
    anrede: Anrede = "du"                            # die Vorgabe für eine neue Fassung, sonst die der Fassung
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
    verworfen: int = 0                               # Einwände des KI-Prüfers anderer Art (Begriffe, Schreibung), die nicht gelten


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
    seite_original: int | None = None                # nur bei PDF: die Seite im PDF (zum Springen)
    seite_gedruckt: str = ""                         # nur bei PDF: ihre gedruckte Beschriftung (für Menschen)
    original: str                                    # Vorlage mit Marken
    deutsch: str                                     # die letzte Übersetzung, mit Marken; leer, wenn keine kam
    befunde: list[Befund]


class Bericht(BaseModel):
    zahlen: Zahlen
    offen: list[OffeneStelle]
    begriffe_fragwuerdig: list[BegriffEintrag] = Field(default_factory=list)   # gelten nicht, bis der Nutzer entscheidet


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
    fragwuerdig: str = ""                            # warum ein Eintrag von Regel oder KI die Regeln nicht besteht; leer: gilt


class FragwuerdigeWeg(BaseModel):
    """Welche fragwürdigen Einträge eines Buchs weg sollen: die, die die Vorschau zeigte."""
    ids: list[Nr] = Field(min_length=1, max_length=AUSWAHL_HOECHSTENS)


class FragwuerdigeEntfernt(BaseModel):
    entfernt: list[int]                              # was inzwischen nicht mehr fragwürdig ist, bleibt


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
