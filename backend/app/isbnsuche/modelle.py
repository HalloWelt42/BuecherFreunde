"""Was die ISBN-Suche liefert: Fundstellen, Kandidaten mit Stufe, Prüfungen, ISBN zur Wahl."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from backend.app.quellen.abgleich import Stufe


class Fundort(StrEnum):
    """Wo im Buch eine ISBN steht; die Reihenfolge ist die Rangfolge (Impressum vor Rückseite vor Text)."""

    IMPRESSUM = "impressum"
    RUECKSEITE = "rueckseite"
    TITELEI = "titelei"
    TEXT = "text"
    ANMERKUNGEN = "anmerkungen"
    VERLAGSANZEIGE = "verlagsanzeige"
    LITERATURLISTE = "literaturliste"


FUNDORTE: tuple[Fundort, ...] = tuple(Fundort)
#: an diesen Orten stehen ISBN anderer Bücher; eine Nummer ohne den Titel des Buchs daneben ist dort fremd
FREMDE_ORTE = frozenset({Fundort.VERLAGSANZEIGE, Fundort.LITERATURLISTE})


class Ausgabe(StrEnum):
    """Was der Text neben der Nummer über die Ausgabe sagt; die Reihenfolge ist die Rangfolge (Druck vor E-Book, BF-111)."""

    DRUCK = "druck"
    OFFEN = ""
    EBOOK = "ebook"


AUSGABEN: tuple[Ausgabe, ...] = (Ausgabe.DRUCK, Ausgabe.OFFEN, Ausgabe.EBOOK)


class Fundstelle(BaseModel):
    seite: int                                  # Dateiseite ab 1, wie im Leser (?page=)
    prozent: float                              # Lage im Buch, für Formate ohne Seiten
    fundort: Fundort
    ausschnitt: str                             # der Text um die Nummer, maskiert, die Nummer in <mark> (wie in der Suche im Buch)
    funde: int = 1                              # so oft steht die Nummer in diesem Ausschnitt


class Einstufung(BaseModel):
    """Die Stufe eines Kandidaten und worauf sie beruht."""

    stufe: Stufe
    quelle: str = ""                            # Kennung der Quelle; leer: aus dem Text um die Fundstellen
    basis: str = "im Text"                      # wie die Oberfläche die Grundlage nennt ("im Text", "Verzeichnis 3")
    was: str = ""                               # was dort steht, maskiert, abweichende Teile in <mark>
    warum: str = ""                             # kurz, warum nicht passt (leer: passt)


class Kandidat(BaseModel):
    """Eine ISBN des Buchs mit allen Fundstellen, gleich in welcher Schreibweise sie dort steht."""

    isbn: str                                   # ISBN-13 mit Strichen
    isbn13: str                                 # nur Ziffern
    formen: list[str] = Field(default_factory=list)     # wie sie sonst im Buch steht (andere Striche, als ISBN-10)
    ausgabe: Ausgabe = Ausgabe.OFFEN
    funde: int
    fundort: Fundort                            # der beste ihrer Fundorte
    stellen: list[Fundstelle]
    text: Einstufung                            # Stufe aus dem Text um die Fundstellen
    quelle: Einstufung | None = None            # Stufe aus einer Quelle, wenn geprüft

    @property
    def einstufung(self) -> Einstufung:
        return self.quelle or self.text


class Isbnsuche(BaseModel):
    """POST /api/books/{id}/isbn-scan: die Kandidaten in der Rangfolge."""

    kandidaten: list[Kandidat]
    funde: int                                  # alle Fundstellen zusammen
    aktuell: str                                # die gespeicherte ISBN des Buchs
    seiten: int                                 # Seiten des durchsuchten Texts; 0: das Buch hat keinen Text


class Isbnpruefung(BaseModel):
    """POST /api/books/{id}/isbn-pruefen: was die Quellen zu einer ISBN sagen."""

    isbn: str
    einstufung: Einstufung | None = None        # None: keine gefragte Quelle kennt sie
    hinweise: list[str] = Field(default_factory=list)   # Quellen, die gerade nicht antworten, mit Grund
    ruht: bool = False                          # keine gefragte Quelle antwortet gerade


class Pruefen(BaseModel):
    isbn: str = Field(min_length=10, max_length=20)


class Wahl(BaseModel):
    """Ein Buch mit ISBN zur Wahl: der beste Kandidat und wie viele es sonst noch gibt."""

    buch_id: int
    kandidat: Kandidat
    weitere: int


class Wahlbuecher(BaseModel):
    buecher: list[int] = Field(min_length=1, max_length=500)


class Wahlergebnis(BaseModel):
    betroffen: int
