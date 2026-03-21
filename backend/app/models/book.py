"""Pydantic-Modelle fuer Buecher."""

from pydantic import BaseModel, Field


class BookListItem(BaseModel):
    """Buch in der Listendarstellung (kompakt)."""

    id: int
    hash: str
    title: str
    author: str
    file_format: str
    file_size: int
    cover_path: str = ""
    page_count: int = 0
    year: int | None = None
    isbn: str = ""
    is_favorite: bool = False
    is_to_read: bool = False
    rating: int = 0
    reading_position: str = ""
    last_read_at: str | None = None
    categories: list[dict] = Field(default_factory=list)
    tags: list[dict] = Field(default_factory=list)
    created_at: str = ""


class BookResponse(BaseModel):
    """Vollstaendige Buchdetails."""

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
    is_favorite: bool = False
    is_to_read: bool = False
    rating: int = 0
    reading_position: str = ""
    last_read_at: str | None = None
    categories: list[dict] = Field(default_factory=list)
    tags: list[dict] = Field(default_factory=list)
    collections: list[dict] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class BookUpdate(BaseModel):
    """Felder die bei einem Buch aktualisiert werden koennen."""

    title: str | None = None
    author: str | None = None
    isbn: str | None = None
    publisher: str | None = None
    year: int | None = None
    language: str | None = None
    description: str | None = None


class BookListResponse(BaseModel):
    """Paginierte Buchliste."""

    buecher: list[BookListItem]
    gesamt: int
    seite: int
    pro_seite: int
    seiten_gesamt: int
