"""Formen der Annahme mit Vorschau (BF-80): was eine Aufnahme vor dem Übernehmen weiß (`Gelesen`), wie sie zugeordnet wird
(`Zuordnung`, je Feld mit Herkunft) und wie die Schnittstelle die Vorschau zeigt."""

from __future__ import annotations

from typing import Annotated, Generic, Literal, TypeVar

from pydantic import AfterValidator, BaseModel, Field

from backend.app.annahme.auswertung import Ergebnis
from backend.app.models.book import BESONDERES
from backend.app.models.grenzen import AUSWAHL_HOECHSTENS, DATEINAME, ETIKETTEN_JE_DATEI, KATEGORIEN_JE_DATEI, Band, Etikett, Nr, Sprache

T = TypeVar("T")

# Woher ein Wert der Vorschau kommt: feste Regel, KI, Ordnername in der ZIP, Name oder Inhalt der Datei, Lücke einer Sammlung
# (BF-75), das vorhandene Buch im Bestand, der Nutzer. Was der Nutzer setzt, überschreibt nichts mehr (auch nicht die KI).
Herkunft = Literal["regel", "ki", "ordner", "datei", "luecke", "bestand", "nutzer"]
NUTZER: Herkunft = "nutzer"
BUCH, MATERIAL = "buch", "material"
ARTEN = (BUCH, *BESONDERES, MATERIAL)            # Art in der Vorschau; "buch" ist books.typ leer, leer heißt noch offen
Doppelart = Literal["neu", "gleich", "format"]  # gleich: dieselbe Datei; format: dasselbe Buch in einem anderen Format
Doppelwahl = Literal["neu", "weglassen", "format", "eigenes"]
Rolle = Literal["buch", "material", "zip", "rest", "doppel"]
Kistand = Literal["", "offen", "fertig"]


def _art(wert: str) -> str:
    if wert and wert not in ARTEN:
        raise ValueError("erlaubt ist " + ", ".join(ARTEN))
    return wert


Art = Annotated[str, AfterValidator(_art)]


class Wert(BaseModel, Generic[T]):
    """Ein Feld der Vorschau: der Wert, woher er kommt (leer: noch kein Vorschlag) und, bei Regel und KI, warum."""

    wert: T
    herkunft: Herkunft | None = None
    grund: str = ""


class Ziel(BaseModel):
    """Zu welchem Buch eine Datei gehört (weiteres Format, Begleitmaterial): eins im Bestand oder eine andere Aufnahme derselben
    Vorschau, die als Buch übernommen wird."""

    buch_id: int | None = None
    aufnahme: int | None = None
    titel: str = ""


class Doppel(BaseModel):
    art: Doppelart = "neu"
    wahl: Doppelwahl = "neu"
    herkunft: Herkunft | None = None
    grund: str = ""                              # etwa "gleiche Datei im Bestand" oder "zu Sturmflut, EPUB"


class Zuordnung(BaseModel):
    """Was beim Übernehmen mit der Datei geschieht, je Feld mit Herkunft. Gespeichert als JSON in `aufnahme.zuordnung`."""

    art: Wert[str] = Field(default_factory=lambda: Wert[str](wert=""))
    gattung: str | None = None                   # nur von der KI, wo das gezeichnete Deckblatt sie braucht (BF-59)
    kategorien: Wert[list[int]] = Field(default_factory=lambda: Wert[list[int]](wert=[]))
    etiketten: Wert[list[str]] = Field(default_factory=lambda: Wert[list[str]](wert=[]))
    sammlung: Wert[int | None] = Field(default_factory=lambda: Wert[int | None](wert=None))
    band: Wert[str] = Field(default_factory=lambda: Wert[str](wert=""))
    sprache: Wert[str] = Field(default_factory=lambda: Wert[str](wert=""))
    doppel: Doppel = Field(default_factory=Doppel)
    ziel: Ziel | None = None
    nicht: str = ""                              # warum nicht übernommen (kein Buchformat und zu keinem Buch gehörig)
    hinweise: list[str] = Field(default_factory=list)
    bestaetigt: bool = False                     # übernommen: ab hier zählt die Zuordnung, wie sie ist
    von_profil: str | None = None                # wer übernommen hat (Etiketten sind persönlich, BF-78)


class Gelesen(BaseModel):
    """Die Angaben aus der Datei, gemerkt bis zum Übernehmen; Volltext und Umschlag liegen schon bei der Prüfsumme im
    Speicher (services/storage.py), ins Regal kommt erst etwas beim Übernehmen."""

    titel: str = ""
    autor: str = ""
    isbn: str = ""
    verlag: str = ""
    jahr: int | None = None
    sprache: str = ""
    beschreibung: str = ""
    seiten: int = 0
    umschlag: bool = False
    umschlag_schlicht: bool | None = None
    alter_von: int | None = None
    alter_bis: int | None = None
    alter_quelle: str = ""

    @classmethod
    def von(cls, e: Ergebnis, schlicht: bool | None) -> Gelesen:
        return cls(titel=e.title, autor=e.author, isbn=e.isbn or "", verlag=e.publisher or "", jahr=e.year, sprache=e.language or "",
                   beschreibung=e.description or "", seiten=e.page_count or 0, umschlag=bool(e.cover_data), umschlag_schlicht=schlicht,
                   alter_von=e.alter_von, alter_bis=e.alter_bis, alter_quelle=e.alter_quelle)

    def ergebnis(self, volltext: str, umschlag: bytes | None) -> Ergebnis:
        return Ergebnis(title=self.titel, author=self.autor, isbn=self.isbn, publisher=self.verlag, year=self.jahr, language=self.sprache,
                        description=self.beschreibung, page_count=self.seiten, fulltext=volltext, cover_data=umschlag,
                        alter_von=self.alter_von, alter_bis=self.alter_bis, alter_quelle=self.alter_quelle)


# -- Eingaben ---------------------------------------------------------------------------------------------------------------

class Vorgabe(BaseModel):
    """Was für alle Dateien einer Vorschau gesetzt ist, etwa beim Hochladen in eine Lücke einer Sammlung (BF-75)."""

    sammlung_id: Nr | None = None
    band: Band = ""                              # nur bei einer einzelnen Datei in eine Lücke
    sprache: Sprache = ""


class VorschauNeu(BaseModel):
    name: str = Field("", max_length=DATEINAME)
    vorgabe: Vorgabe = Field(default_factory=Vorgabe)


class ZielEingabe(BaseModel):
    buch_id: Nr | None = None
    aufnahme: Nr | None = None


class Felder(BaseModel):
    """Was der Nutzer setzt; ein genanntes Feld gilt für alle genannten Aufnahmen und heißt danach "nutzer". `sammlung` und
    `ziel` leert null."""

    art: Art | None = None
    kategorien: list[Nr] | None = Field(None, max_length=KATEGORIEN_JE_DATEI)
    etiketten: list[Etikett] | None = Field(None, max_length=ETIKETTEN_JE_DATEI)
    sammlung: Nr | None = None
    band: Band | None = None
    sprache: Sprache | None = None
    doppel: Doppelwahl | None = None
    ziel: ZielEingabe | None = None


class Aenderung(BaseModel):
    ids: list[Nr] = Field(min_length=1, max_length=AUSWAHL_HOECHSTENS)
    felder: Felder


class Auswahl(BaseModel):
    """Welche Aufnahmen einer Vorschau; ohne `ids` alle."""

    ids: list[Nr] | None = Field(None, max_length=AUSWAHL_HOECHSTENS)


# -- Ansichten --------------------------------------------------------------------------------------------------------------

class Ablageziel(BaseModel):
    ort: Literal["kellerwolke", "geraet", "bleibt"]   # bleibt: im Eingang oder im Ordner, wo sie liegt
    ordner: str
    name: str = ""


class Zeile(BaseModel):
    id: int
    name: str
    groesse: int
    ordner: str                                  # Ordner in der ZIP, nur als Hinweis
    stand: str
    text: str
    rolle: Rolle
    buch_id: int | None
    gelesen: Gelesen | None
    umschlag: bool                               # GET /api/annahme/{id}/umschlag zeigt ihn
    felder: Zuordnung | None
    ablage: Ablageziel | None
    ki: Kistand
    material: int = 0                            # so viele Dateien dieser Vorschau kommen als Begleitmaterial zu ihr


class Vorschauzaehler(BaseModel):
    gesamt: int = 0
    uebernehmen: int = 0                         # kommt beim Übernehmen ins Regal, als Format oder als Material
    buecher: int = 0
    besonderes: int = 0
    material: int = 0
    formate: int = 0
    weglassen: int = 0
    nicht: int = 0                               # nicht übernommen, mit Grund
    offen: int = 0                               # Art noch offen
    laeuft: int = 0                              # wird noch gelesen oder ausgepackt
    ki: int = 0                                  # die KI prüft noch


class Vorschaukurz(BaseModel):
    id: str
    name: str
    quelle: str
    stand: str
    dateien: int
    warten: int                                  # warten auf die Bestätigung
    laeuft: int
    ki: int
    groesse: int
    hinweis: str
    angelegt_am: str
    geaendert_am: str


class Vorschauansicht(Vorschaukurz):
    vorgabe: Vorgabe
    zaehler: Vorschauzaehler
    zeilen: list[Zeile]


class Verwerffolge(BaseModel):
    id: int
    name: str
    ordner: str                                  # in der ZIP, als Hinweis
    groesse: int
    wirkung: Literal["papierkorb", "endgueltig", "bleibt", "nichts"]   # nichts: es gibt keine Datei (schon da, nicht ausgepackt)
    pfad: str                                    # wo sie liegt


class Verwerffolgen(BaseModel):
    vorschau: str
    name: str
    dateien: list[Verwerffolge]
    papierkorb: int
    endgueltig: int
    bleibt: int
    stand: str
