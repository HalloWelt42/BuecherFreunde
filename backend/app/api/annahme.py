"""Wege der Annahme (Hochladen), Vertrag in docs/neubau/SCHNITTSTELLE.md."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.app.ablage.wolke import WolkeFehler
from backend.app.annahme import eingangsordner
from backend.app.annahme.dienst import QUELLEN, STAENDE, TEIL, Versatz, ZuViel, annahme
from backend.app.core.auth import verify_token, verify_token_inhalt
from backend.app.models.grenzen import GROESSTE_ZAHL, Nr

Quelle = Literal[QUELLEN]                         # type: ignore[valid-type]
Stand = Literal[STAENDE]                          # type: ignore[valid-type]

router = APIRouter(prefix="/api/annahme", tags=["Annahme"])


class Neu(BaseModel):
    name: str = Field(min_length=1, max_length=400)
    groesse: int = Field(ge=0, le=GROESSTE_ZAHL)
    sha256: str = Field("", pattern=r"^([0-9a-f]{64})?$")
    anreichern: bool = False


async def _da(nr: int) -> dict:
    z = await annahme.einer(nr)
    if z is None:
        raise HTTPException(404, "Diese Aufnahme gibt es nicht")
    return z


@router.get("")
async def alle(_=Depends(verify_token)):
    return await annahme.alle()


@router.post("")
async def anlegen(n: Neu, _=Depends(verify_token)):
    return await annahme.anlegen(n.name, n.groesse, n.sha256, n.anreichern)


@router.delete("")
async def aufraeumen(quelle: Quelle | None = None, stand: list[Stand] | None = Query(None), _=Depends(verify_token)):
    """Viele auf einmal entfernen, wie einzeln mit DELETE /{nr}: nach Quelle, nach Stand (mehrfach) oder beidem."""
    if quelle is None and not stand:
        raise HTTPException(422, "Quelle oder Stand: fehlt, ohne beides wäre es die ganze Liste")
    return {"entfernt": await annahme.aufraeumen(quelle, stand), **await annahme.alle()}


@router.post("/ausblenden")
async def ausblenden(_=Depends(verify_token)):
    await annahme.ausblenden()
    return await annahme.alle()


@router.get("/eingangsordner")
async def eingang(_=Depends(verify_token)):
    try:
        return await eingangsordner.inhalt()
    except WolkeFehler as f:
        raise HTTPException(503, f.meldung) from f


@router.post("/eingangsordner")
async def eingang_aufnehmen(_=Depends(verify_token)):
    try:
        return {"neu": await eingangsordner.aufnehmen()}
    except WolkeFehler as f:
        raise HTTPException(503, f.meldung) from f


@router.get("/ereignisse")
async def ereignisse(_=Depends(verify_token_inhalt)):
    async def strom():
        async for d in annahme.ereignisse():
            yield f"data: {json.dumps(d, ensure_ascii=False)}\n\n"
    return StreamingResponse(strom(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{nr}")
async def einer(nr: Nr, _=Depends(verify_token)):
    return await _da(nr)


@router.patch("/{nr}")
async def teil(nr: Nr, request: Request, _=Depends(verify_token)):
    await _da(nr)
    try:
        versatz, laenge = int(request.headers.get("upload-offset", "")), int(request.headers.get("content-length", ""))
    except ValueError:
        raise HTTPException(400, "Es fehlen Upload-Offset oder Content-Length") from None
    if laenge > TEIL:
        raise HTTPException(413, "Das Teil ist größer als vereinbart")
    try:
        return await annahme.teil(nr, versatz, request.stream(), laenge)
    except ZuViel as f:
        raise HTTPException(413, "Mehr Daten als die angesagte Größe der Datei") from f
    except Versatz as f:
        return JSONResponse({"detail": str(f), "empfangen": f.empfangen}, status_code=409)
    except WolkeFehler as f:
        raise HTTPException(503, f.meldung) from f


@router.post("/{nr}/erneut")
async def erneut(nr: Nr, _=Depends(verify_token)):
    await _da(nr)
    return await annahme.erneut(nr)


@router.delete("/{nr}")
async def entfernen(nr: Nr, _=Depends(verify_token)):
    await _da(nr)
    await annahme.entfernen(nr)
    return {"entfernt": nr}
