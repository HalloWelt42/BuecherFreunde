"""Anmeldung: mit dem Konto der Kellerwolke (Baustein des Appkern) oder, ohne sie, mit einem eigenen Konto der App. Dazu die
Angaben, die das Anmeldefenster zeigt."""

from appkern.anmeldung import AnmeldungsFehler, Konto
from appkern.anmeldung.api import anmeldungs_router
from fastapi import Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.anmeldung import anmeldung, eigener_zugang
from backend.app.core.anschluesse import anschluesse
from backend.app.core.auth import braucht, verify_token
from backend.app.core.config import settings
from backend.app.core.eigene_anmeldung import EigeneAnmeldung

# das Inhalts-Cookie wie bisher: Name `app_inhalt` (Vorgabe des Appkerns), gilt unter /api
router = anmeldungs_router(anmeldung, prefix="/api/anmeldung", inhalt_pfade=("/api",))


class AppAngaben(BaseModel):
    name: str
    art: str                           # "kellerwolke" oder "eigen"
    kellerwolke: str
    besitzer: str | None = None
    eingerichtet: bool                 # kellerwolke: der App-Zugang ist da; eigen: es gibt ein Konto


class NeuesKonto(BaseModel):
    kennung: str
    passwort: str


class NeuesKennwort(BaseModel):
    alt: str
    neu: str


class Angemeldet(BaseModel):
    token: str
    konto: Konto


def _eigene() -> EigeneAnmeldung:
    if anmeldung.eigene is None:
        raise HTTPException(409, "Konten verwaltet hier die Kellerwolke")
    return anmeldung.eigene


def _http(f: AnmeldungsFehler) -> HTTPException:
    return HTTPException(f.status, f.meldung)


@router.get("/app", response_model=AppAngaben)
async def app_angaben() -> AppAngaben:
    if anmeldung.eigene is not None:
        return AppAngaben(name="BücherFreunde", art="eigen", kellerwolke="", eingerichtet=await anmeldung.eigene.eingerichtet())
    name = await eigener_zugang.erfragen()
    return AppAngaben(name=name or "BücherFreunde", art=anschluesse().anmeldung, kellerwolke=settings.kellerwolke_url, besitzer=eigener_zugang.besitzer,
                      eingerichtet=bool(name))


@router.post("/einrichten", response_model=Angemeldet, status_code=201)
async def einrichten(n: NeuesKonto) -> Angemeldet:
    """Das erste und einzige Konto anlegen, nur solange es keins gibt."""
    try:
        token, konto = await _eigene().einrichten(n.kennung, n.passwort)
    except AnmeldungsFehler as f:
        raise _http(f) from f
    return Angemeldet(token=token, konto=konto)


@router.post("/kennwort", status_code=204, dependencies=[Depends(braucht("einstellungen"))])
async def kennwort(n: NeuesKennwort, konto: Konto = Depends(verify_token)) -> None:
    try:
        await _eigene().kennwort_aendern(konto, n.alt, n.neu)
    except AnmeldungsFehler as f:
        raise _http(f) from f
