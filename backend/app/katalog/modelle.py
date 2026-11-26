"""Die Formen des Katalogs (BF-69, docs/neubau/KATALOG.md): die Datei (Standard, Sichern, Teilen) und der Entwurf, der
gültige Katalog, wie die Schnittstelle ihn zeigt, die Eingaben, Vorschläge, alte Regale und Läufe.

Ein Katalog hat zwei Ebenen: Bereiche und darunter Kategorien. Ein Bereich gilt für bestimmte Arten von Werken
(`arten`, die Werte von `books.typ`, leer heißt Buch); vorgeschlagen werden einem Werk nur Kategorien aus Bereichen seiner
Art. Eine Kategorie hat ein eigenes Zeichen und erbt die Farbe ihres Bereichs, solange sie keine eigene hat: gespeichert
wird dann eine leere Farbe, gezeigt die des Bereichs."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, field_validator, model_validator

from backend.app.models.book import Typ
from backend.app.models.grenzen import (
    AUSWAHL_HOECHSTENS, BEREICHE_HOECHSTENS, KATALOG_SCHLUESSEL, KATEGORIEN_JE_BEREICH, REGELWERTE, SYMBOL, TEILE_HOECHSTENS,
    Bereichsbeschreibung, Farbe, FarbeOderLeer, KiBeschreibung, KiJeAnfrage, Katalogname, Nr, Regelwert, Sicherheit,
    Stapelgroesse, TeilenAb,
)

Art = Literal["bereich", "kategorie", "regal"]
Herkunft = Literal["standard", "geteilt", "neu", "eigen"]
Regelart = Literal["sachgruppen", "schlagworte", "titelwoerter", "verlage"]
REGELARTEN: tuple[Regelart, ...] = ("sachgruppen", "schlagworte", "titelwoerter", "verlage")
Vorschlagsquelle = Literal["regel", "ki", "beide"]
Laufart = Literal["einordnen", "bestand"]
Laufzustand = Literal["laeuft", "pause", "fertig", "fehler"]
VORGABE_FARBE = "#6b7280"
BUCH = ""                                              # die Art eines Werks, das ein Buch ist (books.typ leer)


def _ohne_vorsilbe(wert: object) -> object:
    """Zeichen heißen wie in Font Awesome (solid), ohne "fa-"; die Symbolwahl der Oberfläche liefert sie mit."""
    return wert.strip().removeprefix("fa-") if isinstance(wert, str) else wert


def eigene_farbe(farbe: str, bereichsfarbe: str) -> str:
    """Was an einer Kategorie gespeichert wird: leer, wenn sie die Farbe ihres Bereichs hat; sie erbt dann auch jede neue."""
    return "" if not farbe or farbe.casefold() == (bereichsfarbe or "").casefold() else farbe


def _leer_wie_keine(wert: object) -> object:
    return wert or None


def _einmal(werte: list[str]) -> list[str]:
    """Jeder Wert einmal (Groß und klein gleich), in der Reihenfolge, wie er kam."""
    gesehen: set[str] = set()
    aus = []
    for w in werte:
        if w.casefold() not in gesehen:
            gesehen.add(w.casefold())
            aus.append(w)
    return aus


Zeichen = Annotated[str, BeforeValidator(_ohne_vorsilbe), StringConstraints(max_length=SYMBOL, pattern=r"^[a-z0-9-]*$")]
_TEIL = r"[a-z0-9]+(?:-[a-z0-9]+)*"
Bereichsschluessel = Annotated[str, StringConstraints(strip_whitespace=True, max_length=KATALOG_SCHLUESSEL, pattern=rf"^{_TEIL}$")]
Kategorieschluessel = Annotated[str, StringConstraints(strip_whitespace=True, max_length=KATALOG_SCHLUESSEL,
                                                       pattern=rf"^{_TEIL}/{_TEIL}$")]
Regelwerte = Annotated[list[Regelwert], Field(max_length=REGELWERTE)]
HerkunftOderLeer = Annotated[Herkunft | None, BeforeValidator(_leer_wie_keine)]
Arten = Annotated[list[Typ], Field(min_length=1, max_length=10)]


class Regeln(BaseModel):
    """Feste Regeln einer Kategorie, je Art eine Liste von Texten (katalog/regeln.py)."""

    model_config = ConfigDict(extra="forbid")

    sachgruppen: Regelwerte = Field(default_factory=list)     # Nummern der Bibliotheken, als Anfang: "62" trifft "621.3"
    schlagworte: Regelwerte = Field(default_factory=list)     # ganze Wörter in den Schlagworten und alten Regalen
    titelwoerter: Regelwerte = Field(default_factory=list)    # Wortanfang im Titel
    verlage: Regelwerte = Field(default_factory=list)         # im Verlag enthalten

    @field_validator(*REGELARTEN)
    @classmethod
    def _jeder_einmal(cls, werte: list[str]) -> list[str]:
        return _einmal(werte)

    def werte(self, art: Regelart) -> list[str]:
        return getattr(self, art)

    @property
    def leer(self) -> bool:
        return not any(self.werte(a) for a in REGELARTEN)


# -- Datei und Entwurf ------------------------------------------------------------------------------------------------------

class Teil(BaseModel):
    """Eine der Kategorien, in die eine große Kategorie im Entwurf zerfällt."""

    schluessel: Kategorieschluessel
    name: Katalogname
    zeichen: Zeichen = ""
    ki_beschreibung: KiBeschreibung = ""
    regeln: Regeln = Field(default_factory=Regeln)


class Katalogkategorie(Teil):
    farbe: FarbeOderLeer = ""                  # gespeichert: leer erbt die Farbe des Bereichs; gezeigt: die, die gilt
    verborgen: bool = False
    herkunft: HerkunftOderLeer = None          # in einer Datei frei; im Entwurf immer gesetzt
    anzahl: int | None = None                  # im Entwurf: Treffer der Regeln im Bestand
    teile: Annotated[list[Teil], Field(max_length=TEILE_HOECHSTENS)] = Field(default_factory=list)


class Katalogbereich(BaseModel):
    schluessel: Bereichsschluessel
    name: Katalogname
    zeichen: Zeichen = ""
    farbe: Farbe = VORGABE_FARBE
    beschreibung: Bereichsbeschreibung = ""
    arten: Arten = Field(default_factory=lambda: [BUCH])     # für welche Arten von Werken der Bereich gilt
    verborgen: bool = False
    herkunft: HerkunftOderLeer = None
    anzahl: int | None = None
    kategorien: Annotated[list[Katalogkategorie], Field(max_length=KATEGORIEN_JE_BEREICH)] = Field(default_factory=list)

    @field_validator("arten")
    @classmethod
    def _art_einmal(cls, arten: list[str]) -> list[str]:
        return list(dict.fromkeys(arten))


class Katalog(BaseModel):
    """Ein Katalog als Daten: der Standard (katalog/standard.json), eine Datei zum Sichern und Teilen, ein Entwurf."""

    fassung: Literal[1] = 1
    bereiche: Annotated[list[Katalogbereich], Field(max_length=BEREICHE_HOECHSTENS)] = Field(default_factory=list)

    @model_validator(mode="after")
    def _eindeutig(self) -> Katalog:
        gesehen: set[str] = set()
        for s in self.schluessel():
            if s in gesehen:
                raise ValueError(f"Der Schlüssel {s} steht mehr als einmal im Katalog")
            gesehen.add(s)
        bereichsnamen: set[str] = set()
        for b in self.bereiche:
            if b.name.casefold() in bereichsnamen:
                raise ValueError(f"Den Bereich {b.name} gibt es mehr als einmal")
            bereichsnamen.add(b.name.casefold())
            namen: set[str] = set()
            for k in b.kategorien:
                if k.name.casefold() in namen:
                    raise ValueError(f"Die Kategorie {k.name} steht im Bereich {b.name} mehr als einmal")
                namen.add(k.name.casefold())
        return self

    def schluessel(self) -> Iterator[str]:
        for b in self.bereiche:
            yield b.schluessel
            for k in b.kategorien:
                yield k.schluessel
                yield from (t.schluessel for t in k.teile)

    def kategorien(self) -> Iterator[tuple[Katalogbereich, Katalogkategorie]]:
        for b in self.bereiche:
            for k in b.kategorien:
                yield b, k


# -- der gültige Katalog ----------------------------------------------------------------------------------------------------

class Kategorie(BaseModel):
    id: int
    schluessel: str
    name: str
    zeichen: str
    farbe: str                                 # die eigene, sonst die des Bereichs
    ki_beschreibung: str
    regeln: Regeln
    verborgen: bool
    herkunft: str
    anzahl: int                                # Bücher in der Kategorie


class Bereich(BaseModel):
    id: int
    schluessel: str
    name: str
    zeichen: str
    farbe: str
    beschreibung: str
    arten: list[str]
    verborgen: bool
    anzahl: int                                # Bücher in seinen Kategorien, jedes einmal
    kategorien: list[Kategorie]


class Regal(BaseModel):
    id: int
    name: str
    zeichen: str
    farbe: str
    anzahl: int
    spezial: bool


class KatalogAntwort(BaseModel):
    bereiche: list[Bereich]
    regale: list[Regal]
    ohne_kategorie: int                        # Bücher in keiner Kategorie des Katalogs
    hat_katalog: bool


class Einordnungskategorie(BaseModel):
    """Was Regeln und KI beim Einordnen von einer Kategorie brauchen."""

    id: int
    schluessel: str
    name: str
    ki_beschreibung: str
    regeln: Regeln
    arten: list[str]                           # die Arten ihres Bereichs


class BereichEingabe(BaseModel):
    name: Katalogname
    zeichen: Zeichen = ""
    farbe: Farbe = VORGABE_FARBE
    beschreibung: Bereichsbeschreibung = ""
    arten: Arten = Field(default_factory=lambda: [BUCH])
    verborgen: bool = False


class BereichAenderung(BaseModel):
    name: Katalogname | None = None
    zeichen: Zeichen | None = None
    farbe: Farbe | None = None
    beschreibung: Bereichsbeschreibung | None = None
    arten: Arten | None = None
    verborgen: bool | None = None


class KategorieEingabe(BaseModel):
    bereich_id: Nr
    name: Katalogname
    zeichen: Zeichen = ""
    farbe: FarbeOderLeer = ""                  # leer oder die des Bereichs: erbt
    ki_beschreibung: KiBeschreibung = ""
    regeln: Regeln = Field(default_factory=Regeln)
    verborgen: bool = False


class KategorieAenderung(BaseModel):
    bereich_id: Nr | None = None
    name: Katalogname | None = None
    zeichen: Zeichen | None = None
    farbe: FarbeOderLeer | None = None
    ki_beschreibung: KiBeschreibung | None = None
    regeln: Regeln | None = None
    verborgen: bool | None = None


class Loeschfolgen(BaseModel):
    """Was beim Löschen verloren geht: die Bücher verlieren die Zuordnung (sie selbst bleiben), Vorschläge fallen weg."""

    name: str
    buecher: int
    vorschlaege: int                           # offene
    kategorien: int                            # bei einem Bereich: seine Kategorien
    titel: list[str]                           # die ersten betroffenen Bücher


class Regelzahl(BaseModel):
    art: Regelart
    werte: list[str]
    treffer: int                               # Bücher, die eine Regel dieser Art trifft


class Treffer(BaseModel):
    regeln: list[Regelzahl]
    zusammen: int                              # Bücher, die irgendeine Regel trifft
    ki_vorschlaege: int                        # offene Vorschläge, an denen die KI beteiligt ist


# -- Entwurf, Läufe, Einstellungen ------------------------------------------------------------------------------------------

class Laufstand(BaseModel):
    laeuft: bool = False
    pause: bool = False
    stand: Laufzustand | Literal[""] = ""      # leer: es gab noch keinen Lauf
    stapel: int = 0                            # fertige Stapel
    stapel_gesamt: int = 0
    stapel_groesse: int = 0
    regeln: int = 0                            # Vorschläge mit einer Regel
    ki: int = 0                                # Vorschläge der KI (beim Entwurf: neue Kategorien)
    ohne_vorschlag: int = 0                    # Bücher ohne Vorschlag
    schritt: str = ""
    grund: str = ""                            # warum pausiert, ohne KI oder mit einem Fehler zu Ende


class EntwurfWeg(BaseModel):
    weg: Literal["standard", "bestand", "leer"]


class EntwurfStand(BaseModel):
    entwurf: Katalog | None = None
    lauf: Laufstand | None = None


class Katalogeinstellungen(BaseModel):
    stapel: Stapelgroesse                      # Titel je Stapel
    ki_je_anfrage: KiJeAnfrage                 # Bücher je Anfrage an die KI
    sicher_ab: Sicherheit                      # so sichere Vorschläge sind vorab angehakt
    teilen_ab: TeilenAb                        # über so vielen Treffern zerfällt eine Kategorie im Entwurf in ihre Teile


class EinordnenStart(BaseModel):
    stapel: Stapelgroesse | None = None        # ohne: die Einstellung


# -- Vorschläge -------------------------------------------------------------------------------------------------------------

class Fund(BaseModel):
    """Ein Buch in einer Kategorie, gefunden von Regel, KI oder beiden, vor dem Merken."""

    buch_id: int
    kategorie_id: int
    quelle: Vorschlagsquelle
    gruende: list[str]
    sicherheit: int


class Auch(BaseModel):
    """Ein anderer offener Vorschlag für dasselbe Buch; mit `id` lässt er sich gleich mit annehmen."""

    id: int
    kategorie_id: int
    name: str
    sicherheit: int


class OffenerVorschlag(BaseModel):
    id: int
    buch_id: int
    kategorie_id: int
    quelle: Vorschlagsquelle
    gruende: list[str]
    sicherheit: int
    vorab: bool                                # sicher genug, um vorab angehakt zu sein
    auch: list[Auch]                           # die übrigen offenen Vorschläge für dasselbe Buch


class OffeneJeKategorie(BaseModel):
    kategorie_id: int
    anzahl: int


Auswahlnummern = Annotated[list[Nr], Field(min_length=1, max_length=AUSWAHL_HOECHSTENS)]


class Annehmen(BaseModel):
    ids: Auswahlnummern | None = None
    kategorie: Nr | None = None                # alle offenen dieser Kategorie

    @model_validator(mode="after")
    def _eins_von_beiden(self) -> Annehmen:
        if (self.ids is None) == (self.kategorie is None):
            raise ValueError("Entweder ids oder kategorie angeben")
        return self


class Ablehnen(BaseModel):
    ids: Auswahlnummern


class Angenommen(BaseModel):
    angenommen: int


class Abgelehnt(BaseModel):
    abgelehnt: int


# -- alte Regale ------------------------------------------------------------------------------------------------------------

class AltVorschlag(BaseModel):
    art: Literal["kategorie", "schlagwort"]    # in eine Kategorie, oder der Name wird ein Etikett an den Büchern
    kategorie_id: int | None = None
    grund: str


class AltesRegal(BaseModel):
    id: int
    name: str
    anzahl: int
    vorschlag: AltVorschlag


class Uebernahmeziel(BaseModel):
    kategorie_id: Nr | None = None
    schlagwort: bool = False

    @model_validator(mode="after")
    def _eins_von_beiden(self) -> Uebernahmeziel:
        if (self.kategorie_id is not None) == self.schlagwort:
            raise ValueError("Entweder kategorie_id oder schlagwort angeben")
        return self


class Uebernahme(BaseModel):
    ids: Auswahlnummern
    ziel: Uebernahmeziel


class Uebernommen(BaseModel):
    buecher: int


class AltLoeschfolgen(BaseModel):
    id: int
    name: str
    buecher: int                               # Bücher im Regal; sie selbst bleiben
    ohne_kategorie: int                        # davon in keiner Kategorie des Katalogs
    titel: list[str]
