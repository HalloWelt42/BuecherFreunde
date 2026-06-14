"""API-Endpunkt für die Anmeldung mit Benutzername und Passwort."""

import hmac

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["Anmeldung"])


class LoginRequest(BaseModel):
    """Anmeldedaten aus dem Login-Fenster."""

    benutzername: str
    passwort: str


class LoginResponse(BaseModel):
    """Antwort mit dem API-Token für nachfolgende Anfragen."""

    token: str


@router.post("/login", response_model=LoginResponse)
async def login(daten: LoginRequest) -> LoginResponse:
    """Prüft Benutzername und Passwort und gibt bei Erfolg den API-Token zurück.

    Die Anmeldedaten stehen in der .env-Datei (AUTH_USERNAME/AUTH_PASSWORD),
    Standard ist admin/admin. Der zurückgegebene Token wird vom Frontend
    gespeichert und als Bearer-Token an alle weiteren Endpunkte gesendet.
    """
    name_ok = hmac.compare_digest(
        daten.benutzername.encode("utf-8"), settings.auth_username.encode("utf-8")
    )
    pass_ok = hmac.compare_digest(
        daten.passwort.encode("utf-8"), settings.auth_password.encode("utf-8")
    )
    if not (name_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzername oder Passwort ist falsch",
        )
    return LoginResponse(token=settings.api_token)
