"""Vorlesen: Stimmen zur Wahl und der Ton als Strom."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.core.auth import KOPF, verify_token
from backend.app.services import vorlesen

router = APIRouter(prefix="/api/vorlesen", tags=["Vorlesen"])


class Vorlesetext(BaseModel):
    text: str = Field(min_length=1, max_length=20_000_000)
    stimme: str = Field("", max_length=200)


@router.get("/stimmen")
async def stimmen(_=Depends(verify_token)):
    return await vorlesen.stimmen()


@router.post("", response_class=StreamingResponse)
async def vorlesen_strom(v: Vorlesetext, request: Request, _=Depends(verify_token)):
    zeilen = vorlesen.strom(v.text, v.stimme, request.headers.get(KOPF, ""))
    try:
        erste = await anext(zeilen)                       # was vor dem ersten Satz scheitert, ist eine Antwort mit Grund
    except vorlesen.VorlesenFehler as f:
        raise HTTPException(f.status, f.meldung) from f

    async def alles():
        yield erste
        async for z in zeilen:
            yield z

    return StreamingResponse(alles(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
