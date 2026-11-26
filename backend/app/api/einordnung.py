"""Stand des Einordnens mit der lokalen KI (BF-59, services/einordnung.py) für die Einstellungen."""

from fastapi import APIRouter, Depends

from backend.app.core.auth import verify_token
from backend.app.services.einordnung import EinordnungStand, einordner

router = APIRouter(prefix="/api/einordnung", tags=["Einordnung"], dependencies=[Depends(verify_token)])


@router.get("/stand", response_model=EinordnungStand)
async def einordnung_stand() -> EinordnungStand:
    return await einordner.stand()


@router.post("/fortsetzen", response_model=EinordnungStand)
async def einordnung_fortsetzen() -> EinordnungStand:
    """Nach einer Ablehnung durch die Leitstelle wieder einordnen."""
    einordner.fortsetzen()
    return await einordner.stand()
