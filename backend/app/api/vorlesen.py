"""Vorlesen über die Vertonung (BF-14): die Stimmen zur Wahl mit ihren Bereichen, die Beschreibung der Einstellungen und der Ton als
Strom, Satz für Satz, mit den Werten des aktiven Profils. Vorlesen ist keine KI im Sinne von FAMILIE.md: jede Stufe darf es. Feste
Ansagen für den Kinderbereich: api/familie.py (BF-78). Die Arbeit tut das Paket backend/app/vorlesen."""

from __future__ import annotations

from appkern.vorlesen import NDJSON, VorlesenFehler
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.core.auth import braucht, profil
from backend.app.familie.modelle import Profil
from backend.app.vorlesen import beschreibung, sprechen, stimmen
from backend.app.vorlesen.modelle import Beschreibung, Stimmenliste, vertont

router = APIRouter(prefix="/api/vorlesen", tags=["Vorlesen"], dependencies=[Depends(braucht("vorlesen"))])


class Vorlesetext(BaseModel):
    text: str = Field(min_length=1, max_length=20_000_000)
    stimme: str = Field("", max_length=200)        # wie die Vertonung sie schreibt; leer: ihre Stimme ab Werk


@router.get("/stimmen", response_model=Stimmenliste)
async def stimmen_lesen() -> Stimmenliste:
    return await stimmen.liste()


@router.get("/beschreibung", response_model=Beschreibung)
async def beschreibung_lesen() -> Beschreibung:
    """Was die Vertonung zum Sprechen anbietet (Name, Art, Grenzen, Vorgabe); gespeichert wird je Profil (`einstellungen.vorlesen`)."""
    return await beschreibung.lesen()


@router.post("", response_class=StreamingResponse)
async def vorlesen_strom(v: Vorlesetext, p: Profil = Depends(profil)) -> StreamingResponse:
    if v.stimme and not vertont(v.stimme):
        raise HTTPException(400, "Diese Stimme spricht die Vertonung nicht; bitte eine aus der Liste wählen")
    zeilen = sprechen.zeilen(v.text, v.stimme, p.einstellungen.vorlesen.werte)
    try:
        erste = await anext(zeilen)                    # was vor dem ersten Satz scheitert, ist eine Antwort mit Grund
    except StopAsyncIteration:
        erste = b""
    except VorlesenFehler as f:
        raise HTTPException(f.status, f.meldung) from f

    async def alles():
        yield erste
        async for z in zeilen:
            yield z

    return StreamingResponse(alles(), media_type=NDJSON, headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
