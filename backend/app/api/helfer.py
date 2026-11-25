"""Helfer beim Lesen: Nachschlagen und das Gespräch mit dem Assistenten, beide als kleines Fenster in der App."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from fastapi.responses import StreamingResponse

from backend.app.core.auth import KOPF, verify_token, verify_token_inhalt
from backend.app.services import gespraech, nachschlagen
from backend.app.services.hausdienst import DienstFehler

router = APIRouter(prefix="/api", tags=["Helfer"])
Kennung = Annotated[str, Path(pattern=gespraech.KENNUNG)]


def _http(f: DienstFehler) -> HTTPException:
    return HTTPException(f.status, f.meldung)


def _sitzung(request: Request) -> str:
    return request.headers.get(KOPF, "")


def _basis(request: Request) -> str:
    """Unter welcher Adresse der Mensch die App gerade benutzt."""
    return f"{request.headers.get('x-forwarded-proto', request.url.scheme)}://{request.headers.get('host', request.url.netloc)}"


@router.get("/nachschlag/suche", response_model=list[nachschlagen.Nachschlagtreffer])
async def nachschlag_suche(request: Request, q: str = Query(min_length=1, max_length=400), _=Depends(verify_token)):
    try:
        return await nachschlagen.suche(q, sitzung=_sitzung(request))
    except DienstFehler as f:
        raise _http(f) from f


@router.get("/nachschlag/artikel", response_model=nachschlagen.Nachschlagartikel)
async def nachschlag_artikel(request: Request, buch: str = Query(max_length=200), pfad: str = Query(max_length=600), q: str = Query("", max_length=400),
                             anker: str = Query("", max_length=300), _=Depends(verify_token)):
    try:
        return await nachschlagen.artikel(buch, pfad, q, anker, _sitzung(request))
    except DienstFehler as f:
        raise _http(f) from f


@router.get("/nachschlag/bild/{buch}/{pfad:path}")
async def nachschlag_bild(buch: str, pfad: str, _=Depends(verify_token_inhalt)):
    try:
        inhalt, art = await nachschlagen.bild(buch, pfad)
    except DienstFehler as f:
        raise _http(f) from f
    return Response(inhalt, media_type=art, headers={"Cache-Control": "private, max-age=604800", "X-Content-Type-Options": "nosniff"})


@router.post("/gespraech", response_model=gespraech.Gestellt, status_code=201)
async def fragen(f: gespraech.Frage, request: Request, _=Depends(verify_token)):
    try:
        return await gespraech.fragen(f, _sitzung(request), _basis(request))
    except DienstFehler as e:
        raise _http(e) from e


@router.get("/gespraech/{chat}/{zug}", response_class=StreamingResponse)
async def antwort(request: Request, chat: Kennung, zug: Kennung, _=Depends(verify_token)):
    return StreamingResponse(gespraech.antwort(chat, zug, _sitzung(request)), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/gespraech/zuege/{zug}/abbrechen", status_code=204)
async def abbrechen(request: Request, zug: Kennung, _=Depends(verify_token)):
    try:
        await gespraech.abbrechen(zug, _sitzung(request))
    except DienstFehler as e:
        raise _http(e) from e
