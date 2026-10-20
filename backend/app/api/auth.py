"""Anmeldung mit dem Konto der Kellerwolke (Baustein des Appkern): Stand, Anmelden mit Passwort, Gerät mit Code
koppeln, Abmelden. Dazu die Angaben, die das Anmeldefenster zeigt (Name der App, Kellerwolke, Besitzer)."""

from appkern.anmeldung.api import anmeldungs_router
from pydantic import BaseModel

from backend.app.core.anmeldung import anmeldung, eigener_zugang
from backend.app.core.config import settings

router = anmeldungs_router(anmeldung, prefix="/api/anmeldung", inhalt_pfad="/api")


class AppAngaben(BaseModel):
    name: str
    kellerwolke: str
    besitzer: str | None = None
    eingerichtet: bool


@router.get("/app", response_model=AppAngaben)
async def app_angaben() -> AppAngaben:
    name = await eigener_zugang.erfragen()
    return AppAngaben(name=name or "BücherFreunde", kellerwolke=settings.kellerwolke_url, besitzer=eigener_zugang.besitzer,
                      eingerichtet=bool(name))
