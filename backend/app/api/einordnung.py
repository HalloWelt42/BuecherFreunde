"""Stand des Einordnens (BF-59, BF-77, services/einordnung.py): Art aller Werke nach Regeln und mit der lokalen KI."""

from fastapi import APIRouter, Depends

from backend.app.core.auth import braucht
from backend.app.services.einordnung import EinordnungStand, einordner

router = APIRouter(prefix="/api/einordnung", tags=["Einordnung"], dependencies=[Depends(braucht("bearbeiten"))])


@router.get("/stand", response_model=EinordnungStand)
async def einordnung_stand() -> EinordnungStand:
    return await einordner.stand()


@router.post("/fortsetzen", response_model=EinordnungStand, dependencies=[Depends(braucht("ki"))])
async def einordnung_fortsetzen() -> EinordnungStand:
    """Nach einer Ablehnung durch die Leitstelle wieder einordnen."""
    einordner.fortsetzen()
    return await einordner.stand()
