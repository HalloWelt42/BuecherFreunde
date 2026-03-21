"""API-Endpunkte für die Volltextsuche."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.app.core.auth import verify_token
from backend.app.services.search import (
    SearchResult,
    optimize_index,
    rebuild_index,
    search_books,
    search_count,
    suggest,
)

router = APIRouter(prefix="/api/search", tags=["Suche"])


class SearchResponse(BaseModel):
    """Suchergebnis mit Pagination."""

    treffer: list[dict]
    gesamt: int
    anfrage: str
    limit: int
    offset: int


class SuggestResponse(BaseModel):
    """Vorschläge für Autovervollständigung."""

    vorschlaege: list[dict]
    anfrage: str


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Suchbegriff"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _token: str = Depends(verify_token),
):
    """Volltextsuche in allen Büchern mit Kontext-Snippets."""
    results = await search_books(q, limit, offset)
    total = await search_count(q)

    treffer = [
        {
            "book_id": r.book_id,
            "titel": r.title,
            "autor": r.author,
            "snippet": r.snippet,
            "relevanz": r.relevance,
        }
        for r in results
    ]

    return SearchResponse(
        treffer=treffer,
        gesamt=total,
        anfrage=q,
        limit=limit,
        offset=offset,
    )


@router.get("/vorschlaege", response_model=SuggestResponse)
async def search_suggest(
    q: str = Query(..., min_length=2, description="Suchbegriff"),
    limit: int = Query(5, ge=1, le=20),
    _token: str = Depends(verify_token),
):
    """Autovervollständigung für die Suchleiste."""
    suggestions = await suggest(q, limit)
    return SuggestResponse(vorschlaege=suggestions, anfrage=q)


@router.post("/index-neu-aufbauen")
async def rebuild(
    _token: str = Depends(verify_token),
):
    """Baut den FTS-Index komplett neu auf."""
    count = await rebuild_index()
    return {"indexiert": count, "status": "fertig"}


@router.post("/index-optimieren")
async def optimize(
    _token: str = Depends(verify_token),
):
    """Optimiert den FTS-Index."""
    await optimize_index()
    return {"status": "optimiert"}
