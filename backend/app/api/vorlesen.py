"""Vorlesen über die Vertonung (BF-14): die Stimmen zur Wahl mit ihren Bereichen, die Beschreibung der Einstellungen und der Ton als
Strom, Satz für Satz, mit den Werten des aktiven Profils, und die Stimmprobe als abgelegter Ton (BF-114). Vorlesen ist keine KI im Sinne von FAMILIE.md: jede Stufe darf es. Feste
Ansagen für den Kinderbereich: api/familie.py (BF-78). Die Arbeit tut das Paket backend/app/vorlesen."""

from __future__ import annotations

from appkern.vorlesen import NDJSON, VorlesenFehler
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.app.core.auth import braucht, profil
from backend.app.familie.modelle import Profil
from backend.app.vorlesen import beschreibung, proben, sprechen, stimmen, strom, tonablage
from backend.app.vorlesen.modelle import Beschreibung, Leserstimme, Stimmenliste, vertont

router = APIRouter(prefix="/api/vorlesen", tags=["Vorlesen"], dependencies=[Depends(braucht("vorlesen"))])
# Töne lädt das Tonelement des Browsers ohne Kopfdaten: angemeldet über das Cookie für Inhalte
ton_router = APIRouter(prefix="/api/vorlesen", tags=["Vorlesen"], dependencies=[Depends(braucht("vorlesen", inhalt=True))])
TON_GILT_S = 365 * 24 * 60 * 60                    # der Name trägt die Prüfsumme von Text und Werten: ein Ton ändert sich nie


class Probenwahl(BaseModel):
    stimme: Leserstimme = ""                      # wie im Leser gewählt; leer: die Stimme ab Werk der Vertonung


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
async def vorlesen_strom(v: Vorlesetext, request: Request, p: Profil = Depends(profil)) -> Response:
    if v.stimme and not vertont(v.stimme):
        raise HTTPException(400, "Diese Stimme spricht die Vertonung nicht; bitte eine aus der Liste wählen")
    zeilen = sprechen.zeilen(v.text, v.stimme, p.einstellungen.vorlesen.werte)
    try:
        # was vor dem ersten Satz scheitert, ist eine Antwort mit Grund; geht der Leser vorher, endet auch die Anfrage an die Vertonung
        erste = await strom.erste_zeile(zeilen, request.is_disconnected)
    except strom.Gegangen:
        return Response(status_code=strom.GEGANGEN)
    except VorlesenFehler as f:
        raise HTTPException(f.status, f.meldung) from f

    async def alles():
        yield erste
        async for z in zeilen:
            yield z

    return StreamingResponse(alles(), media_type=NDJSON, headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/probe", response_model=proben.Stimmprobe)
async def probe_holen(w: Probenwahl, p: Profil = Depends(profil)) -> proben.Stimmprobe:
    """Die Probe dieser Stimme mit den Werten des Profils: fertig abgelegt, sonst jetzt gesprochen und abgelegt. Mit einer
    Stimme des Geräts nur der Text."""
    try:
        return await proben.holen(w.stimme, "leser", p.einstellungen.vorlesen.werte)
    except VorlesenFehler as f:
        raise HTTPException(f.status, f.meldung) from f


@ton_router.get("/probe/ton/{ordner}/{datei}", response_class=FileResponse, responses={200: {"content": {"audio/wav": {}}}})
async def probe_ton(request: Request, ordner: str = Path(pattern=tonablage.ORDNERFORM),
                    datei: str = Path(pattern=tonablage.DATEIFORM)) -> Response:
    """Ein abgelegter Ton einer Stimmprobe, mit langer Zeit im Speicher des Browsers."""
    kopf = {"ETag": f'"{datei}"', "Cache-Control": f"private, max-age={TON_GILT_S}, immutable"}
    if request.headers.get("if-none-match") == kopf["ETag"]:
        return Response(status_code=304, headers=kopf)
    pfad = proben.pfad_im_ordner(ordner, datei)
    if not pfad.is_file():
        raise HTTPException(404, "Diese Stimmprobe gibt es nicht")
    return FileResponse(pfad, media_type="audio/wav", headers=kopf)
