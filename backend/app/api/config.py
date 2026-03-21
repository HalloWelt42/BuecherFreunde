"""API-Endpunkte fuer Konfiguration und Systemstatus."""

from fastapi import APIRouter, Depends

from backend.app.core.auth import verify_token
from backend.app.core.config import settings
from backend.app.core.database import db

router = APIRouter(prefix="/api/config", tags=["Konfiguration"])


@router.get("")
async def get_config(_token: str = Depends(verify_token)) -> dict:
    """Gibt die oeffentliche Konfiguration zurueck (ohne sensible Daten)."""
    return settings.public_config()


@router.get("/version")
async def get_version() -> dict:
    """Gibt die aktuelle Version zurueck (ohne Authentifizierung)."""
    return {"version": settings.version}


@router.get("/paths")
async def get_paths(_token: str = Depends(verify_token)) -> dict:
    """Gibt die konfigurierten Verzeichnispfade zurueck."""
    return {
        "datenbank": str(settings.database_path.resolve()),
        "speicher": str(settings.storage_dir.resolve()),
        "import": str(settings.import_dir.resolve()),
        "extern": str(settings.external_dir.resolve()) if settings.external_dir else "",
    }


@router.get("/stats")
async def get_stats(_token: str = Depends(verify_token)) -> dict:
    """Gibt Zaehler fuer Sidebar und Dashboard zurueck."""
    total = await db.fetch_one("SELECT COUNT(*) as n FROM books")
    favs = await db.fetch_one(
        "SELECT COUNT(*) as n FROM user_book_data WHERE is_favorite = 1"
    )
    to_read = await db.fetch_one(
        "SELECT COUNT(*) as n FROM user_book_data WHERE is_to_read = 1"
    )
    gelesen = await db.fetch_one(
        "SELECT COUNT(*) as n FROM user_book_data WHERE last_read_at IS NOT NULL"
    )
    mit_isbn = await db.fetch_one(
        "SELECT COUNT(*) as n FROM books WHERE isbn IS NOT NULL AND isbn != ''"
    )
    ohne_isbn = await db.fetch_one(
        "SELECT COUNT(*) as n FROM books WHERE isbn IS NULL OR isbn = ''"
    )
    weiterlesen = await db.fetch_one(
        """SELECT COUNT(*) as n FROM user_book_data
           WHERE reading_position IS NOT NULL AND reading_position != ''
           AND last_read_at IS NOT NULL"""
    )
    total_n = total["n"] if total else 0
    gelesen_n = gelesen["n"] if gelesen else 0
    return {
        "buecher_gesamt": total_n,
        "favoriten": favs["n"] if favs else 0,
        "leseliste": to_read["n"] if to_read else 0,
        "gelesen": gelesen_n,
        "ungelesen": total_n - gelesen_n,
        "buecher_mit_isbn": mit_isbn["n"] if mit_isbn else 0,
        "dokumente": ohne_isbn["n"] if ohne_isbn else 0,
        "weiterlesen": weiterlesen["n"] if weiterlesen else 0,
    }
