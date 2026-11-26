"""Pydantic-Modelle für Bücher."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, computed_field

from backend.app.models.grenzen import Autor, Band, Beschreibung, Isbn, Jahr, Nr, Seiten, Sprache, Titel, Verlag
from backend.app.services.storage import umschlag_stand

# Feste Typen eines Buchs (nicht löschbar, nicht änderbar); leer: ein Buch
TYPEN = [
    {"id": "heft", "name": "Heft", "beschreibung": "Zeitschrift, Magazin oder Heft"},
    {"id": "katalog", "name": "Katalog", "beschreibung": "Produktkatalog oder Verzeichnis"},
    {"id": "broschuere", "name": "Broschüre", "beschreibung": "Informationsbroschüre oder Flyer"},
]


def typ_pruefen(wert: str) -> str:
    if wert and wert not in {t["id"] for t in TYPEN}:
        raise ValueError("erlaubt ist leer oder " + ", ".join(t["id"] for t in TYPEN))
    return wert


Typ = Annotated[str, AfterValidator(typ_pruefen)]


class BookListItem(BaseModel):
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


class BookResponse(BaseModel):
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
    bleiben bei null, wie sie sind (die Sammlung löst DELETE /api/collections/{id}/buch/{buch})."""

    title: Titel | None = None
    author: Autor | None = None
    isbn: Isbn | None = None
    publisher: Verlag | None = None
    year: Jahr | None = None
    language: Sprache | None = None
    description: Beschreibung | None = None
    page_count: Seiten | None = None
    typ: Typ | None = None
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
