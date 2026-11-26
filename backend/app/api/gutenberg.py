"""Gemeinfreie Bücher (Project Gutenberg über die Gutendex-API): Stand der Quelle, Suche und Aufnahme. Aufgenommen wird über
die Annahme (annahme/gemeinfrei.py); Stand und Fortschritt stehen in der einen Liste unter /api/annahme."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.annahme.dienst import annahme
from backend.app.core.auth import verify_token
from backend.app.quellen import stand
from backend.app.quellen.fehler import QuelleFehler
from backend.app.quellen.gutenberg import Fundliste, suche
from backend.app.quellen.regeln import GUTENBERG

router = APIRouter(prefix="/api/gutenberg", tags=["Gutenberg"])


@router.get("/status")
async def gutenberg_status(_token: str = Depends(verify_token)) -> dict:
    """Der gemerkte Stand der Gutendex-API; gefragt wird sie dabei nicht."""
    s = await stand.einer(GUTENBERG.kennung)
    return {"erreichbar": s.erreichbar, "url": s.adresse, "info": s.grund or s.wort}


@router.get("/suche")
async def gutenberg_suche(
    q: str = Query("", description="Suchbegriff (Titel, Autor)"),
    sprache: str = Query("", description="Sprachfilter (z.B. 'de', 'en', 'de,en')"),
    topic: str = Query("", description="Thema/Kategorie"),
    seite: int = Query(1, ge=1, description="Seitennummer"),
    _token: str = Depends(verify_token),
) -> Fundliste:
    """Sucht Bücher auf Project Gutenberg."""
    try:
        return await suche(query=q, sprache=sprache, topic=topic, seite=seite)
    except QuelleFehler as f:
        raise HTTPException(status_code=502, detail=f.grund) from f


class GutenbergImportRequest(BaseModel):
    """Bücher aus der Suche: je Buch {gutenberg_id, titel, autor, download_url, download_format, cover_url}."""
    buecher: list[dict]


@router.post("/import")
async def gutenberg_import(request: GutenbergImportRequest, _token: str = Depends(verify_token)):
    """Ausgewählte gemeinfreie Bücher aufnehmen, über dieselbe Annahme wie jede Datei (Liste unter /api/annahme): geholt,
    gelesen, ins Regal "Gutenberg". `anzahl`: neu in der Liste; was es schon gibt, steht dort als vorhanden."""
    if not request.buecher:
        raise HTTPException(status_code=400, detail="Keine Bücher ausgewählt")
    neu = await annahme.aus_gemeinfrei(request.buecher)
    return {"gestartet": neu > 0, "anzahl": neu}
