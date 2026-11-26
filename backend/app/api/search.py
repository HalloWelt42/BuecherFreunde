"""API-Endpunkte für die Volltextsuche; gefunden wird nur, was das Profil sieht (BF-78)."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.app.core.auth import braucht
from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht
from backend.app.material import suche as material_suche
from backend.app.models.grenzen import VERSATZ
from backend.app.services import deckblattangaben
from backend.app.services.search import (
    SearchResult,
    optimize_index,
    rebuild_index,
    search_books,
    search_count,
    suggest,
)

router = APIRouter(prefix="/api/search", tags=["Suche"])
SUCHE = braucht("suche")


class SearchResponse(BaseModel):
    """Suchergebnis mit Pagination."""

    treffer: list[dict]
    gesamt: int
    anfrage: str
    limit: int
    offset: int
    aktive_filter: dict = {}
    material: list[dict] = []          # Treffer im Begleitmaterial (BF-81), nur auf der ersten Seite: je mit Buch und Datei


class SuggestResponse(BaseModel):
    """Vorschläge für Autovervollständigung."""

    vorschlaege: list[dict]
    anfrage: str


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Suchbegriff"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=VERSATZ),
    p: Profil = Depends(SUCHE),
):
    """Volltextsuche in allen Buechern mit Kontext-Snippets.

    Unterstuetzt erweiterte Syntax:
    - "exakter Satz" fuer Phrasensuche
    - autor:Name / author:Name
    - format:epub / format:pdf
    - datum:2020-2024 / datum:>2020 / datum:<2024 / datum:2023
    """
    results, parsed = await search_books(q, limit, offset, sicht=Sicht.von(p))
    total = await search_count(q, sicht=Sicht.von(p))
    im_material = await material_suche.suchen(q, Sicht.von(p), limit) if offset == 0 else []
    angaben = await deckblattangaben.fuer(list({*(r.book_id for r in results), *(m.buch_id for m in im_material)}))

    treffer = [
        {
            "book_id": r.book_id,
            "titel": r.title,
            "autor": r.author,
            "snippet": r.snippet,
            "relevanz": r.relevance,
            "deckblatt": angaben[r.book_id].model_dump() if r.book_id in angaben else None,
        }
        for r in results
    ]

    return SearchResponse(
        treffer=treffer,
        gesamt=total,
        anfrage=q,
        limit=limit,
        offset=offset,
        aktive_filter=parsed.aktive_filter,
        material=[m.model_dump() | {"deckblatt": angaben[m.buch_id].model_dump() if m.buch_id in angaben else None} for m in im_material],
    )


@router.get("/vorschlaege", response_model=SuggestResponse)
async def search_suggest(
    q: str = Query(..., min_length=2, description="Suchbegriff"),
    limit: int = Query(5, ge=1, le=20),
    p: Profil = Depends(SUCHE),
):
    """Autovervollständigung für die Suchleiste."""
    suggestions = await suggest(q, limit, sicht=Sicht.von(p))
    return SuggestResponse(vorschlaege=suggestions, anfrage=q)


@router.post("/index-neu-aufbauen")
async def rebuild(
    _p: Profil = Depends(braucht("einstellungen")),
):
    """Baut den FTS-Index komplett neu auf."""
    count = await rebuild_index()
    return {"indexiert": count, "status": "fertig"}


@router.post("/index-optimieren")
async def optimize(
    _p: Profil = Depends(braucht("einstellungen")),
):
    """Optimiert den FTS-Index."""
    await optimize_index()
    return {"status": "optimiert"}
