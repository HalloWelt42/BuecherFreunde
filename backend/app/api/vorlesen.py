"""Vorlesen über den Sprechdienst der Leitstelle: Stimmen zur Wahl, der Ton als Strom, Satz für Satz, und kurze Ansagen für
Hinweise und Tasten im Kinderbereich (BF-78). Vorlesen ist keine KI im Sinne von FAMILIE.md: jede Stufe darf es."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.core.auth import braucht, profil, verify_token
from backend.app.familie import ich
from backend.app.familie.modelle import Profil
from backend.app.services import ansage, vorlesen

router = APIRouter(prefix="/api/vorlesen", tags=["Vorlesen"], dependencies=[Depends(braucht("vorlesen"))])


class Vorlesetext(BaseModel):
    text: str = Field(min_length=1, max_length=20_000_000)
    stimme: str = Field("", max_length=200)


class Ansagetext(BaseModel):
    text: str = Field(min_length=1, max_length=ansage.TEXT_HOECHSTENS)
    stimme: str = Field("", max_length=200)


@router.get("/stimmen")
async def stimmen(_=Depends(verify_token)):
    return await vorlesen.stimmen()


@router.post("", response_class=StreamingResponse)
async def vorlesen_strom(v: Vorlesetext, _=Depends(verify_token)):
    zeilen = vorlesen.strom(v.text, v.stimme)
    try:
        erste = await anext(zeilen)                       # was vor dem ersten Satz scheitert, ist eine Antwort mit Grund
    except vorlesen.VorlesenFehler as f:
        raise HTTPException(f.status, f.meldung) from f

    async def alles():
        yield erste
        async for z in zeilen:
            yield z

    return StreamingResponse(alles(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/ansage", response_class=Response, responses={200: {"content": {"audio/wav": {}}}})
async def ansage_sprechen(a: Ansagetext, p: Profil = Depends(profil)) -> Response:
    """Ein Satz als WAV, gemerkt im Zwischenspeicher; die Vorlesestimme des Profils geht vor, sonst `stimme`, sonst die Vorgabe.
    Ohne Sprechdienst 503 mit Grund (dann spricht die Oberfläche mit der Stimme des Geräts)."""
    saetze = vorlesen.saetze(a.text)
    if len(saetze) != 1:
        raise HTTPException(422, "Text: eine Ansage ist genau ein Satz")
    hilfen = ich.lesehilfen(p)
    try:
        gesprochen = await ansage.sprechen(saetze[0], (hilfen.stimme if hilfen and hilfen.stimme else "") or a.stimme)
    except vorlesen.VorlesenFehler as f:
        raise HTTPException(f.status, f.meldung) from f
    return Response(gesprochen.ton, media_type="audio/wav",
                    headers={"Cache-Control": "private, max-age=86400", "X-Ansage": "gemerkt" if gesprochen.gemerkt else "neu"})
