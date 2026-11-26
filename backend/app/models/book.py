"""Pydantic-Modelle für Bücher."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, computed_field

from backend.app.models.grenzen import Autor, Band, Beschreibung, Isbn, Jahr, Nr, Seiten, Sprache, Titel, Verlag
from backend.app.services.storage import umschlag_stand

# Feste Typen eines Buchs (nicht löschbar, nicht änderbar); leer: ein Buch
TYPEN = [
    {"id": "dokument", "name": "Dokument", "beschreibung": "Handbuch, Arbeit, Skript oder Beleg"},
    {"id": "heft", "name": "Heft", "beschreibung": "Zeitschrift, Magazin oder Heft"},
    {"id": "katalog", "name": "Katalog", "beschreibung": "Produktkatalog oder Verzeichnis"},
    {"id": "broschuere", "name": "Broschüre", "beschreibung": "Informationsbroschüre oder Flyer"},
]

# Feste Gattungen eines Buchs (BF-59), in dieser Reihenfolge angeboten; leer: keine. Nach ihr zeichnet die Oberfläche das
# gestaltete Deckblatt; bei Dokumenten, Heften, Katalogen und Broschüren bleibt sie leer.
GATTUNGEN = [
    {"id": "krimi", "name": "Krimi"},
    {"id": "thriller", "name": "Thriller"},
    {"id": "historisch", "name": "Historischer Roman"},
    {"id": "fantasy", "name": "Fantasy"},
    {"id": "liebesroman", "name": "Liebesroman"},
    {"id": "roman", "name": "Roman"},
    {"id": "klassiker", "name": "Klassiker"},
    {"id": "sachbuch", "name": "Sachbuch"},
    {"id": "ratgeber", "name": "Ratgeber"},
    {"id": "informatik", "name": "Informatik"},
    {"id": "mathematik", "name": "Mathematik"},
    {"id": "fachbuch", "name": "Fachbuch"},
    {"id": "wirtschaft", "name": "Wirtschaft und Recht"},
]


def _erlaubt(wert: str, liste: list[dict[str, str]]) -> str:
    if wert and wert not in {e["id"] for e in liste}:
        raise ValueError("erlaubt ist leer oder " + ", ".join(e["id"] for e in liste))
    return wert


def typ_pruefen(wert: str) -> str:
    return _erlaubt(wert, TYPEN)


def gattung_pruefen(wert: str) -> str:
    return _erlaubt(wert, GATTUNGEN)


Typ = Annotated[str, AfterValidator(typ_pruefen)]
Gattung = Annotated[str, AfterValidator(gattung_pruefen)]

# Umschlag (BF-59): was die Oberfläche zeigt, das gestaltete Deckblatt oder die gespeicherte Titelseite. `umschlag_wahl`
# ist die Wahl des Nutzers je Buch (leer: automatisch), `umschlag_schlicht` der Befund der Umschlagprüfung
# (services/umschlagpruefung.py; noch nicht geprüft zählt als nicht schlicht).
Umschlag = Literal["gestaltet", "titelseite"]
UmschlagWahl = Literal["", "gestaltet", "titelseite"]
Schlicht = Annotated[bool, BeforeValidator(bool)]
# Wer Art und Gattung bestimmt hat: leer offen, "ki" die lokale KI (services/einordnung.py), "hand" der Nutzer; dann
# fasst die KI das Buch nie wieder an
Einordnung = Literal["", "ki", "hand"]
VON_HAND: Einordnung = "hand"
FELDER_DER_EINORDNUNG = frozenset({"typ", "gattung"})     # wer eins davon setzt, hat von Hand eingeordnet
DARSTELLUNG = frozenset({"umschlag_wahl"})                # Wahl der Darstellung: keine Bearbeitung der Angaben


def umschlag_zeigen(wahl: UmschlagWahl, schlicht: bool) -> Umschlag:
    """Die Wahl des Nutzers, sonst nach dem Befund: ein schlichter Umschlag wird gestaltet."""
    if wahl == "":
        return "gestaltet" if schlicht else "titelseite"
    return wahl


class Umschlagangaben(BaseModel):
    """Was Liste und Buch für das Deckblatt tragen: Gattung, Wahl, Befund und daraus der Umschlag, der gezeigt wird."""

    gattung: str = ""
    umschlag_wahl: UmschlagWahl = ""
    umschlag_schlicht: Schlicht = False

    @computed_field
    @property
    def umschlag(self) -> Umschlag:
        return umschlag_zeigen(self.umschlag_wahl, self.umschlag_schlicht)


class Deckblatt(Umschlagangaben):
    """Was ein Treffer oder ein Werk braucht, um sein Deckblatt zu zeigen (Suche, Autorenseite; services/deckblattangaben.py)."""

    typ: str = ""
    cover_path: str = ""
    file_format: str = ""
    year: int | None = None


class BookListItem(Umschlagangaben):
    """Buch in der Listendarstellung (kompakt)."""

    id: int
    hash: str
    title: str
    author: str
    publisher: str = ""
    file_format: str
    file_size: int
    cover_path: str = ""
    page_count: int = 0
    year: int | None = None
    isbn: str = ""
    typ: str = ""
    sammlung_id: int | None = None
    band_nummer: str = ""
    is_favorite: bool = False
    is_to_read: bool = False
    rating: int = 0
    reading_position: str = ""
    last_read_at: str | None = None
    categories: list[dict] = Field(default_factory=list)
    sammlung: dict | None = None
    created_at: str = ""
    updated_at: str = ""

    @computed_field
    @property
    def cover_stand(self) -> int:
        return umschlag_stand(self.hash)


class BookResponse(Umschlagangaben):
    """Vollständige Buchdetails."""

    id: int
    hash: str
    title: str
    author: str
    isbn: str = ""
    publisher: str = ""
    year: int | None = None
    language: str = ""
    description: str = ""
    file_format: str
    file_name: str = ""
    file_size: int
    cover_path: str = ""
    page_count: int = 0
    typ: str = ""
    sammlung_id: int | None = None
    band_nummer: str = ""
    is_favorite: bool = False
    is_to_read: bool = False
    rating: int = 0
    reading_position: str = ""
    last_read_at: str | None = None
    categories: list[dict] = Field(default_factory=list)
    sammlung: dict | None = None
    authors: list[dict] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    @computed_field
    @property
    def cover_stand(self) -> int:
        return umschlag_stand(self.hash)


class BookUpdate(BaseModel):
    """Felder die bei einem Buch aktualisiert werden können. Das Jahr lässt sich mit null leeren, die übrigen Felder
    bleiben bei null, wie sie sind (die Sammlung löst DELETE /api/collections/{id}/buch/{buch}). Typ oder Gattung setzen
    heißt von Hand eingeordnet (`FELDER_DER_EINORDNUNG`); die Wahl des Umschlags ist keine Bearbeitung (`DARSTELLUNG`)."""

    title: Titel | None = None
    author: Autor | None = None
    isbn: Isbn | None = None
    publisher: Verlag | None = None
    year: Jahr | None = None
    language: Sprache | None = None
    description: Beschreibung | None = None
    page_count: Seiten | None = None
    typ: Typ | None = None
    gattung: Gattung | None = None
    umschlag_wahl: UmschlagWahl | None = None
    sammlung_id: Nr | None = None
    band_nummer: Band | None = None


class BookListResponse(BaseModel):
    """Paginierte Buchliste."""

    buecher: list[BookListItem]
    gesamt: int
    seite: int
    pro_seite: int
    seiten_gesamt: int
    # Nur mit Schnellfilter: wie viele die Liste ohne ihn hätte
    gesamt_ohne_suche: int | None = None
