"""Stufen und Rollen aus `stufen.json` (BF-78): eine Datei für alle Fähigkeiten, Darstellungen und Vorgaben, keine Regel im
Code. Beim Laden wird geprüft, dass jede genannte Fähigkeit beschrieben ist, die Stufen nach Alter aufsteigen und keine
Stufe KI erlaubt (Entscheidung: keine KI für Kinder)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

DATEI = Path(__file__).with_name("stufen.json")
Rollenname = Literal["verwaltung", "erwachsen", "kind"]
ERWACHSENE: tuple[Rollenname, ...] = ("verwaltung", "erwachsen")
NIE_FUER_KINDER = frozenset({"ki"})                # Entscheidung vom 26.11.2026: keine KI für Kinder
# Was die Eltern sehen: titel, lesezeit (heute), fortschritt (genau), grober_fortschritt, zuletzt; geteiltes: nur Bücher,
# die das Kind teilt
Einblickart = Literal["titel", "lesezeit", "fortschritt", "grober_fortschritt", "zuletzt", "geteiltes"]
Schriftwahl = Literal["klein", "mittel", "gross"]  # Schrift des Kindes, ausgehend von der Größe seiner Stufe
Uhrzeit = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]       # 07:30


class Darstellung(BaseModel):
    schrift: str                                    # kinderschrift, serifenlos
    groesse_px: int
    fett: bool
    woerter_je_zeile: int | None                    # am Anfang: Umbruch nach so vielen Wörtern
    zeichen_je_zeile: int | None                    # später: höchstens so viele Zeichen
    zeilenabstand: float
    absatz: float                                   # Abstände als Teil der Schriftgröße
    buchstabe: float
    wort: float
    tippflaeche_px: int
    symbole: bool                                   # Symbole statt Text


class Lesehilfen(BaseModel):
    mitlesen: bool                                  # Vorlesen mit Mitlesen
    tempo: float                                    # Tempo des Vorlesens, 1 wie gewohnt
    silben: bool                                    # farbige Silben
    lesezeile: bool
    schrift: Schriftwahl
    hinweise_sprechen: bool                         # Hinweise werden gesprochen (feste Ansagen, familie/ansagen.py)
    tasten_ansagen: bool                            # eine gewählte Taste sagt, was sie tut
    stimme: str = ""                                # katalog:<name> oder geraet; leer: die Vorlesestimme der Familie (familie/ansagen.py)


class Stufe(BaseModel):
    schluessel: str
    name: str
    alter: str                                      # für Menschen, etwa "Klasse 1 und 2"
    ab_alter: int = Field(ge=0)                     # Vorschlag aus dem Geburtsjahr
    faehigkeiten: list[str]
    lesezeichen_je_buch: int | None = Field(ge=1)   # leer: so viele, wie man will
    darstellung: Darstellung
    lesehilfen: Lesehilfen
    einblick: list[Einblickart]
    katze_name: Literal["vorschlaege", "tippen"]    # Vorlesealter: aus vorgelesenen Vorschlägen wählen


class Rolle(BaseModel):
    name: str
    faehigkeiten: list[str]


class Lesestandregel(BaseModel):
    fertig_ab: float = Field(gt=0, le=1)            # ab diesem Anteil ist ein Buch fertig gelesen (familie/lesestand.py)


class LesezeitNachAlter(BaseModel):
    alter_von: int = Field(ge=0)
    alter_bis: int | None = Field(ge=0)             # leer: nach oben offen
    minuten: int = Field(ge=1)
    an: bool                                        # aus: ohne Grenze am Tag, die Minuten nur als Vorschlag
    schlafen: Uhrzeit


class LesezeitVorgaben(BaseModel):
    nach_alter: list[LesezeitNachAlter]
    ruhe_vor_schlafen_min: int = Field(ge=0)
    aufstehen: Uhrzeit
    vorlesen_zaehlt: bool
    hinweis_vor_ende_min: int = Field(ge=0)
    takt_hoechstens_s: int = Field(ge=1)            # so viele Sekunden darf der Leser auf einmal melden


class Zugang(BaseModel):
    pin_stellen_von: int = Field(ge=4)
    pin_stellen_bis: int = Field(ge=4)
    bild_pin_anzahl: int = Field(ge=2)
    bilder: list[str] = Field(min_length=4)
    fehlversuche_frei: int = Field(ge=1)
    warten_ab_s: int = Field(ge=1)
    warten_hoechstens_s: int = Field(ge=1)
    geraet_offen_s: int = Field(ge=10)              # so lange öffnet die Eltern-PIN ein gebundenes Gerät für die Profilwahl


class KatzeVorgaben(BaseModel):
    name_hoechstens: int = Field(ge=1)
    vorschlaege: list[str]
    nennung: str


class Gestaltung(BaseModel):
    kontrast_mindestens: float
    kontrast_text: float
    tippflaeche_mindestens_px: int
    fortschritt_grob_stufen: int = Field(ge=2)
    schriftgroessen: dict[Schriftwahl, float]       # Anteil an der Größe der Stufe


class Stufenbuch(BaseModel):
    fassung: int
    faehigkeiten: dict[str, str]                    # Schlüssel -> was sie erlaubt
    rollen: dict[Rollenname, Rolle]
    stufen: list[Stufe]
    lesestand: Lesestandregel
    lesezeit: LesezeitVorgaben
    zugang: Zugang
    katze: KatzeVorgaben
    gestaltung: Gestaltung

    @model_validator(mode="after")
    def _stimmig(self) -> Stufenbuch:
        genannt = {f for r in self.rollen.values() for f in r.faehigkeiten} | {f for s in self.stufen for f in s.faehigkeiten}
        if fremd := genannt - self.faehigkeiten.keys():
            raise ValueError(f"Fähigkeiten ohne Beschreibung: {', '.join(sorted(fremd))}")
        if verboten := {f for s in self.stufen for f in s.faehigkeiten} & NIE_FUER_KINDER:
            raise ValueError(f"Für Kinder nie: {', '.join(sorted(verboten))}")
        if self.rollen["kind"].faehigkeiten:
            raise ValueError("Ein Kind darf, was seine Stufe erlaubt; die Rolle selbst nennt nichts")
        schluessel = [s.schluessel for s in self.stufen]
        if len(set(schluessel)) != len(schluessel):
            raise ValueError("Jede Stufe nur einmal")
        if [s.ab_alter for s in self.stufen] != sorted(s.ab_alter for s in self.stufen):
            raise ValueError("Die Stufen steigen nach Alter auf")
        if set(self.gestaltung.schriftgroessen) != {"klein", "mittel", "gross"}:
            raise ValueError("Schriftgrößen: klein, mittel und gross")
        return self

    def stufe(self, schluessel: str) -> Stufe:
        for s in self.stufen:
            if s.schluessel == schluessel:
                return s
        raise KeyError(schluessel)

    def hat_stufe(self, schluessel: str) -> bool:
        return any(s.schluessel == schluessel for s in self.stufen)

    def alter_bis(self, stufe: Stufe) -> int | None:
        """Bis zu welchem Alter die Stufe vorgeschlagen wird; die letzte nach oben offen."""
        folgende = [s.ab_alter for s in self.stufen if s.ab_alter > stufe.ab_alter]
        return min(folgende) - 1 if folgende else None

    def vorschlag(self, alter: int) -> Stufe:
        """Die Stufe, die zu diesem Alter passt: die höchste, deren `ab_alter` erreicht ist."""
        passend = [s for s in self.stufen if s.ab_alter <= alter]
        return passend[-1] if passend else self.stufen[0]

    def lesezeit_fuer(self, alter: int) -> LesezeitNachAlter:
        for v in self.lesezeit.nach_alter:
            if v.alter_von <= alter and (v.alter_bis is None or alter <= v.alter_bis):
                return v
        return self.lesezeit.nach_alter[-1]


@lru_cache(maxsize=1)
def stufenbuch() -> Stufenbuch:
    return Stufenbuch.model_validate(json.loads(DATEI.read_text(encoding="utf-8")))
