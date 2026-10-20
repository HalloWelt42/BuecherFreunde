"""Schutz der Wege: Menschen mit einer Anmeldung der Kellerwolke (Sitzung oder gekoppeltes Gerät), andere Apps mit
ihrem App-Schlüssel nur für `fundus/*`. Geprüft wird über den Baustein des Appkern (`core/anmeldung.py`)."""

from fastapi import HTTPException, Query, Request, status
from appkern.anmeldung import AnmeldungsFehler, Konto

from backend.app.core.anmeldung import anmeldung, eigener_zugang, erlaubte_apps

KOPF = "x-kellerwolke-sitzung"


def _aus_kopf(request: Request) -> str:
    art, _, wert = request.headers.get("authorization", "").partition(" ")
    return request.headers.get(KOPF) or (wert.strip() if art.lower() == "bearer" else "")


async def _konto(token: str) -> Konto:
    try:
        konto = await anmeldung.pruefen(token)
    except AnmeldungsFehler as f:
        raise HTTPException(status_code=f.status, detail=f.meldung) from f
    if konto is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Anmeldung erforderlich", headers={"WWW-Authenticate": "Bearer"})
    return konto


async def verify_token(request: Request) -> Konto:
    """Ein Mensch mit gültiger Anmeldung der Kellerwolke."""
    konto = await _konto(_aus_kopf(request))
    if not konto.mensch:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Andere Apps nutzen die Wege fundus/*")
    return konto


async def verify_token_query(
    token: str = Query(..., description="Anmeldung als Parameter (für Bilder, Downloads und Ereignisströme)"),
) -> Konto:
    """Wie `verify_token`, für Adressen ohne Kopf (img, a, EventSource)."""
    konto = await _konto(token)
    if not konto.mensch:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Andere Apps nutzen die Wege fundus/*")
    return konto


async def app_pruefen(request: Request) -> Konto:
    """Eine andere App mit ihrem App-Schlüssel der Kellerwolke, die laut `FUNDUS_APPS` den Bestand lesen darf."""
    await eigener_zugang.erfragen()              # das Konto, dem BücherFreunde gehört, muss bekannt sein
    token = _aus_kopf(request)
    if not token.startswith("kw_app_"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "App-Schlüssel der Kellerwolke erwartet",
                            headers={"WWW-Authenticate": "Bearer"})
    konto = await _konto(token)
    if (konto.app or "").lower() not in erlaubte_apps():
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Die App {konto.app or 'ohne Namen'} darf den Bestand nicht lesen")
    return konto


__all__ = ["app_pruefen", "verify_token", "verify_token_query"]
