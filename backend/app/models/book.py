"""Pydantic-Modelle für Bücher."""

from pydantic import BaseModel, Field, computed_field

from backend.app.services.storage import umschlag_stand


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
    """Felder die bei einem Buch aktualisiert werden können."""

    title: str | None = None
    author: str | None = None
    isbn: str | None = None
    publisher: str | None = None
    year: int | None = None
    language: str | None = None
    description: str | None = None
    page_count: int | None = None
    typ: str | None = None
    sammlung_id: int | None = None
    band_nummer: str | None = None


class BookListResponse(BaseModel):
    """Paginierte Buchliste."""

    buecher: list[BookListItem]
    gesamt: int
    seite: int
    pro_seite: int
    seiten_gesamt: int
    # Nur mit Schnellfilter: wie viele die Liste ohne ihn hätte
    gesamt_ohne_suche: int | None = None
