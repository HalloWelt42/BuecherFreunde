"""Formen der Lücken in Sammlungen (BF-75): was gespeichert ist, was die Schnittstelle zeigt und was sie annimmt."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator

from backend.app.luecken.suchadresse import pruefen
from backend.app.models.book import BookListItem
from backend.app.models.grenzen import ADRESSE, Bandzahl, Sprache

Wahl = Literal["quelle", "eigene", "keine"]            # welche Zahl der Bände gilt; keine: nur Lücken zwischen vorhandenen
Herkunft = Literal["quelle", "eigene", "keine", ""]     # woher die geltende Zahl kommt; leer: es gibt keine
Ausblendgrund = Literal["gibt_es_nicht", "brauche_ich_nicht"]
Abfrage = Literal["offen", "fertig", "fehler"]         # gespeichert je Sammlung und Sprache; nur offen wird gefragt
GRUENDE: dict[str, str] = {"gibt_es_nicht": "Gibt es nicht", "brauche_ich_nicht": "Brauche ich nicht"}


# -- Gespeichert ---------------------------------------------------------------------------------------------------------

class Quellband(BaseModel):
    """Was eine Quelle zu einem Band weiß (`reihe_band`)."""

    nummer: int
    titel: str = ""
    autor: str = ""
    isbn: str = ""
    jahr: int | None = None
    quelle: str = ""


class Quellergebnis(BaseModel):
    gesamt: int | None                                  # der höchste Band, den die Quelle kennt
    baende: list[Quellband]


class Reihenstand(BaseModel):
    """Je Sammlung und Sprache (`reihe_sprache`): welche Zahl gilt und was die Quelle sagte."""

    sprache: str
    wahl: Wahl = "quelle"
    eigene: int | None = None
    quelle_gesamt: int | None = None
    quelle: str = ""
    gefragt: str = ""                                   # der Name der Reihe in der Frage
    stand: Abfrage = "offen"
    grund: str = ""
    nachgeschlagen_am: str | None = None

    def gilt(self) -> tuple[int | None, Herkunft]:
        """Die Zahl der Bände und woher sie kommt; die eigene Angabe gewinnt immer."""
        if self.wahl == "eigene" and self.eigene:
            return self.eigene, "eigene"
        if self.wahl == "keine":
            return None, "keine"
        return (self.quelle_gesamt, "quelle") if self.quelle_gesamt else (None, "")


class Buchband(BaseModel):
    """Ein Buch einer Sammlung, so weit die Lücken es brauchen."""

    id: int
    titel: str = ""
    autor: str = ""
    band: str = ""
    sprache: str = ""                                   # wie das Buch sie nennt
    privat: bool = False                                # jemand hat es privat: sein Titel geht nie in eine Frage an eine Quelle


class Ausgeblendet(BaseModel):
    sprache: str
    name: str                                           # der Sprache, zum Anzeigen
    nummer: int
    grund: Ausblendgrund
    grund_text: str                                     # "Gibt es nicht", "Brauche ich nicht"
    titel: str = ""                                     # aus der Quelle, wenn bekannt
    am: str


# -- Ansicht ---------------------------------------------------------------------------------------------------------------

class Nachschlagen(BaseModel):
    """Was die Quellen zu dieser Sprache gefragt wurden; `nicht`: es wird nicht gefragt (Platzhalter aus, kein Band mit Nummer)."""

    stand: Literal["offen", "fertig", "fehler", "nicht"]
    quelle: str = ""                                    # Kennung, etwa dnb
    quelle_name: str = ""                               # wie sie in der Oberfläche heißt, etwa Verzeichnis 3
    reihe: str = ""                                     # nach welchem Namen gefragt wird oder wurde
    grund: str = ""
    am: str | None = None


class Luecke(BaseModel):
    """Ein fehlender Band mit allem, was zum Besorgen nötig ist."""

    sprache: str
    nummer: int
    titel: str = ""                                     # aus der Quelle; leer: unbekannt
    autor: str = ""                                     # aus der Quelle, sonst der häufigste Autor der Sammlung
    isbn: str = ""                                      # aus der Quelle, mit Strichen, wenn es eine gültige ist
    jahr: int | None = None
    quelle: str = ""                                    # Kennung der Quelle der Angaben; leer: nur aus den eigenen Nummern
    kopieren: str                                       # Titel, Autor, Reihe und Band, ISBN als eine Zeile
    suchadresse: str | None = None                      # die fertige Adresse; leer ohne Vorlage in den Einstellungen


class Platz(BaseModel):
    """Ein Eintrag im Regal einer Sprache: ein Buch oder ein fehlender Band, in der Folge der Bände."""

    art: Literal["buch", "luecke"]
    band: str                                           # wie es am Buch steht; bei einer Lücke die Nummer
    nummer: int | None = None                           # der erste Platz der Zählung; leer: ohne Zahl
    zwischen: bool = False                              # ein Zwischenband (3.5, 3a), belegt keinen Platz
    buch_id: int | None = None
    buch: BookListItem | None = None
    luecke: Luecke | None = None


class Reihe(BaseModel):
    """Die Bände einer Sprache, mit eigener Zählung ab 1."""

    sprache: str                                        # Kürzel; leer: kein Buch nennt eine Sprache
    name: str                                           # zum Anzeigen, etwa Deutsch
    reihe: str                                          # Name der Reihe in dieser Sprache: den die Titel nennen, sonst der Sammlung
    gesamt: int | None                                  # die Zahl der Bände, die gilt
    herkunft: Herkunft
    quelle_gesamt: int | None = None                    # was die Quelle sagt, auch wenn eine eigene Angabe gilt
    eigene: int | None = None                           # die eigene Angabe
    nachschlagen: Nachschlagen
    buecher: int                                        # Bücher dieser Sprache, die das Profil sieht
    belegt: int                                         # Plätze der Zählung, die sie belegen
    fehlen: list[int]
    zeile: str                                          # etwa "es fehlen 4, 9, 11 und 12"; leer ohne Lücke
    eintraege: list[Platz]


class Sammlungsluecken(BaseModel):
    sammlung_id: int
    name: str
    autor: str                                          # der häufigste Autor ihrer Bücher
    an: bool                                            # Platzhalter im Regal; aus: keine Lücken, die Bücher stehen trotzdem je Sprache
    reihen: list[Reihe]
    ausgeblendet: list[Ausgeblendet]


# -- Eingaben --------------------------------------------------------------------------------------------------------------

class Gesamtangabe(BaseModel):
    sprache: Sprache = ""
    wahl: Wahl
    zahl: Bandzahl | None = None                        # nur bei eigene

    @model_validator(mode="after")
    def _zahl_bei_eigene(self) -> Gesamtangabe:
        if self.wahl == "eigene" and self.zahl is None:
            raise ValueError("die Zahl fehlt, sie gehört zur eigenen Angabe")
        if self.wahl != "eigene" and self.zahl is not None:
            raise ValueError("eine Zahl gehört nur zur eigenen Angabe")
        return self


class LueckenAendern(BaseModel):
    an: bool | None = None
    gesamt: list[Gesamtangabe] = Field(default_factory=list, max_length=100)


class Ausblenden(BaseModel):
    sprache: Sprache = ""
    nummer: Bandzahl
    grund: Ausblendgrund


class Zurueckholen(BaseModel):
    sprache: Sprache = ""
    nummer: Bandzahl


def _vorlage(wert: str) -> str:
    try:
        return pruefen(wert)
    except ValueError as f:
        raise ValueError(str(f)) from None


Suchvorlage = Annotated[str, StringConstraints(strip_whitespace=True, max_length=ADRESSE), AfterValidator(_vorlage)]


class Suchadresse(BaseModel):
    suchadresse: Suchvorlage = ""


class Platzhalter(BaseModel):
    name: str                                           # ohne Klammern, etwa titel
    bedeutung: str


class Suchadresseinstellungen(BaseModel):
    suchadresse: str                                    # leer: keine Suche, im Feld nur Kopieren
    platzhalter: list[Platzhalter]


class Probe(BaseModel):
    """Die fertige Adresse für einen fehlenden Band, den das Profil sieht; ohne Lücke oder ohne Vorlage leer."""

    adresse: str | None
    sammlung: str = ""
    luecke: Luecke | None = None


class Nachschlagestand(BaseModel):
    """Der Auftrag "Lücken nachschlagen", wie die übrigen Läufe: was, wie weit, seit wann."""

    was: str = "Lücken nachschlagen"
    stand: Literal["wartet", "laeuft", "ruht", "fertig"]
    gesamt: int                                         # Sammlungen und Sprachen in diesem Lauf
    fertig: int                                         # davon gefragt (mit Antwort oder Fehler)
    offen: int                                          # noch nie gefragt, auch über diesen Lauf hinaus
    aktuell: str = ""                                   # etwa "Leuchtfeuerkai, Deutsch"
    grund: str = ""
    begonnen: str | None = None
    geaendert: str | None = None
    fertig_am: str | None = None
