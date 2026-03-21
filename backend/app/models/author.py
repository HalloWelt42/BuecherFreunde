"""Pydantic-Modelle für Autoren."""

from pydantic import BaseModel, Field


class AuthorListItem(BaseModel):
    """Autor in der Listendarstellung (kompakt)."""

    id: int
    name: str
    slug: str
    photo_path: str = ""
    birth_year: int | None = None
    death_year: int | None = None
    nationality: str = ""
    book_count: int = 0
    created_at: str = ""


class AuthorResponse(BaseModel):
    """Vollständige Autorendetails."""

    id: int
    name: str
    slug: str
    biography: str = ""
    beschreibung: str = ""
    birth_year: int | None = None
    death_year: int | None = None
    photo_path: str = ""
    wikidata_id: str = ""
    wikipedia_url: str = ""
    website: str = ""
    nationality: str = ""
    quelle: str = ""
    konfidenz: str = ""
    score: int = 0
    books: list[dict] = Field(default_factory=list)
    werke: list[dict] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class AuthorUpdate(BaseModel):
    """Felder die bei einem Autor aktualisiert werden können."""

    name: str | None = None
    biography: str | None = None
    birth_year: int | None = None
    death_year: int | None = None
    nationality: str | None = None
    website: str | None = None
    wikidata_id: str | None = None
    wikipedia_url: str | None = None


class AuthorListResponse(BaseModel):
    """Paginierte Autorenliste."""

    autoren: list[AuthorListItem]
    gesamt: int
    seite: int
    pro_seite: int
    seiten_gesamt: int
