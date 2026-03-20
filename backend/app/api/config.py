"""API-Endpunkte fuer Konfiguration und Systemstatus."""

from fastapi import APIRouter, Depends

from backend.app.core.auth import verify_token
from backend.app.core.config import settings

router = APIRouter(prefix="/api/config", tags=["Konfiguration"])


@router.get("")
async def get_config(_token: str = Depends(verify_token)) -> dict:
    """Gibt die oeffentliche Konfiguration zurueck (ohne sensible Daten)."""
    return settings.public_config()


@router.get("/version")
async def get_version() -> dict:
    """Gibt die aktuelle Version zurueck (ohne Authentifizierung)."""
    return {"version": settings.version}
