"""Grenzen der Eingaben (BF-50): eine Stelle für alle Modelle der Schnittstelle.

Die Längen sind am Bestand gemessen und lassen reichlich Luft; was darüber liegt, ist ein Fehler der Eingabe, kein Buch.
Pflichttexte werden an den Rändern von Leerzeichen befreit und dürfen danach nicht leer sein. Zahlen bleiben in dem
Bereich, den SQLite als ganze Zahl speichern kann; eine Nummer außerhalb gibt es nicht (im Pfad: 404, siehe
core/fehlerantworten.py)."""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated

from annotated_types import Ge, Le
from pydantic import AfterValidator, StringConstraints

GROESSTE_ZAHL = 2**63 - 1                # SQLite INTEGER

# Längen in Zeichen
TITEL = 500
AUTOR = 1000
VERLAG = 500
SPRACHE = 35
BESCHREIBUNG = 50_000
BAND = 50
NOTIZ = 20_000
SEITENANGABE = 50
STELLE = 2_000                           # EPUB-Stelle (CFI) oder Bereich
TEXTAUSZUG = 5_000
ETIKETT = 50
ETIKETT_NOTIZ = 5_000
REGAL = 100
REGAL_BESCHREIBUNG = 1_000
SYMBOL = 50
SAMMLUNG = 100
SAMMLUNG_BESCHREIBUNG = 1_000
LESEPOSITION = 2_000
AUTORNAME = 300
BIOGRAFIE = 200_000
HERKUNFT = 100
ADRESSE = 2_000
PROMPT_NAME = 100
PROMPT_BESCHREIBUNG = 1_000
PROMPT = 20_000
BEGRIFF = 200                            # ein Eintrag der Begriffsliste beim Übersetzen (BF-71)
BEGRIFF_GRUND = 300
BLOCKTEXT = 50_000                       # eine Übersetzung von Hand für einen Block

# Bereiche
SEITEN_HOECHSTENS = 100_000
ALTER_BIS = 99                           # Lese- oder Interessenalter eines Buchs (BF-78)
JAHR_AB = 1000                           # Erscheinungsjahr eines Buchs
LEBENSJAHR_AB = -3000                    # Geburts- und Sterbejahr eines Autors
JAHR_BIS = 9999                          # Obergrenze eines Filters nach Jahren
SORTIERUNG = 1_000_000
LISTENSEITE = 1_000_000                  # Seiten einer Liste (Blättern)
VERSATZ = 100_000_000                    # Einträge überspringen
AUSWAHL_HOECHSTENS = 10_000              # so viele Nummern in einer Anfrage (Sammelaktionen, Zuordnungen)
SAMMLUNG_ALS_EINTRAG_AB = 2              # ab so vielen Büchern darf eine Sammlung in der Liste ein Eintrag sein (BF-66)
SAMMLUNG_ALS_EINTRAG_BIS = 1000          # die größte Grenze, die man dafür einstellen kann
# Katalog (BF-69)
KATALOG_NAME = 100                       # Name eines Bereichs oder einer Kategorie
KATALOG_BESCHREIBUNG = 1_000             # Beschreibung eines Bereichs
KI_BESCHREIBUNG = 2_000                  # was in eine Kategorie gehört, für die KI
KATALOG_SCHLUESSEL = 100
REGELWERT = 100                          # ein Wert einer Regel, etwa ein Schlagwort
REGELWERTE = 300                         # so viele Werte je Art einer Regel
BEREICHE_HOECHSTENS = 50
KATEGORIEN_JE_BEREICH = 300
TEILE_HOECHSTENS = 50
KATALOG_STAPEL_BIS = 20_000              # Titel je Stapel eines Laufs
KI_JE_ANFRAGE_BIS = 200                  # Bücher je Anfrage an die KI
KATALOG_TEILEN_BIS = 1_000_000


def _bis_naechstes_jahr(jahr: int) -> int:
    if jahr > date.today().year + 1:
        raise ValueError(f"höchstens {date.today().year + 1}")
    return jahr


def _farbe(wert: str) -> str:
    if not re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", wert):
        raise ValueError("keine Farbe wie #3366ff")
    return wert


def _farbe_oder_leer(wert: str) -> str:
    return _farbe(wert) if wert else wert


def _pflicht(hoechstens: int) -> StringConstraints:
    """Nicht leer und nicht nur Leerzeichen."""
    return StringConstraints(strip_whitespace=True, min_length=1, max_length=hoechstens)


def _frei(hoechstens: int) -> StringConstraints:
    """Darf leer sein; Leerzeichen an den Rändern gehen."""
    return StringConstraints(strip_whitespace=True, max_length=hoechstens)


# Zahlen
Nr = Annotated[int, Ge(1), Le(GROESSTE_ZAHL)]
Index = Annotated[int, Ge(0), Le(GROESSTE_ZAHL)]           # zählt ab 0
Jahr = Annotated[int, Ge(JAHR_AB), AfterValidator(_bis_naechstes_jahr)]
Lebensjahr = Annotated[int, Ge(LEBENSJAHR_AB), AfterValidator(_bis_naechstes_jahr)]
Seiten = Annotated[int, Ge(0), Le(SEITEN_HOECHSTENS)]
Lesealter = Annotated[int, Ge(0), Le(ALTER_BIS)]
Prozent = Annotated[float, Ge(0), Le(100)]
Sicherheit = Annotated[int, Ge(0), Le(100)]
Stapelgroesse = Annotated[int, Ge(1), Le(KATALOG_STAPEL_BIS)]
KiJeAnfrage = Annotated[int, Ge(1), Le(KI_JE_ANFRAGE_BIS)]
TeilenAb = Annotated[int, Ge(1), Le(KATALOG_TEILEN_BIS)]
Sortierung = Annotated[int, Ge(-SORTIERUNG), Le(SORTIERUNG)]
AlsEintragAb = Annotated[int, Ge(SAMMLUNG_ALS_EINTRAG_AB), Le(SAMMLUNG_ALS_EINTRAG_BIS)]

# Formen
Farbe = Annotated[str, AfterValidator(_farbe)]
FarbeOderLeer = Annotated[str, StringConstraints(strip_whitespace=True), AfterValidator(_farbe_oder_leer)]
Isbn = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9Xx -]{0,20}$")]
Symbol = Annotated[str, StringConstraints(strip_whitespace=True, max_length=SYMBOL, pattern=r"^[a-z0-9-]*$")]

# Texte, die nicht leer sein dürfen
Titel = Annotated[str, _pflicht(TITEL)]
Autor = Annotated[str, _pflicht(AUTOR)]
Notiz = Annotated[str, _pflicht(NOTIZ)]
Regalname = Annotated[str, _pflicht(REGAL)]
Sammlungsname = Annotated[str, _pflicht(SAMMLUNG)]
Autorname = Annotated[str, _pflicht(AUTORNAME)]
Leseposition = Annotated[str, _pflicht(LESEPOSITION)]
Stelle = Annotated[str, _pflicht(STELLE)]
Promptname = Annotated[str, _pflicht(PROMPT_NAME)]
Katalogname = Annotated[str, _pflicht(KATALOG_NAME)]
Regelwert = Annotated[str, _pflicht(REGELWERT)]
Prompt = Annotated[str, _pflicht(PROMPT)]

# Texte, die leer sein dürfen
Verlag = Annotated[str, _frei(VERLAG)]
Sprache = Annotated[str, _frei(SPRACHE)]
Beschreibung = Annotated[str, _frei(BESCHREIBUNG)]
Band = Annotated[str, _frei(BAND)]
Seitenangabe = Annotated[str, _frei(SEITENANGABE)]
StelleOderLeer = Annotated[str, _frei(STELLE)]
Textauszug = Annotated[str, _frei(TEXTAUSZUG)]
Etikett = Annotated[str, _frei(ETIKETT)]
EtikettNotiz = Annotated[str, _frei(ETIKETT_NOTIZ)]
Regalbeschreibung = Annotated[str, _frei(REGAL_BESCHREIBUNG)]
Sammlungsbeschreibung = Annotated[str, _frei(SAMMLUNG_BESCHREIBUNG)]
Biografie = Annotated[str, _frei(BIOGRAFIE)]
Herkunft = Annotated[str, _frei(HERKUNFT)]
Adresse = Annotated[str, _frei(ADRESSE)]
Promptbeschreibung = Annotated[str, _frei(PROMPT_BESCHREIBUNG)]
Bereichsbeschreibung = Annotated[str, _frei(KATALOG_BESCHREIBUNG)]
KiBeschreibung = Annotated[str, _frei(KI_BESCHREIBUNG)]
