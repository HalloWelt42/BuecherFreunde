"""Wege der Annahme (Hochladen), Vertrag in docs/neubau/SCHNITTSTELLE.md."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.app.ablage.wolke import WolkeFehler
from backend.app.annahme.dienst import TEIL, Versatz, annahme
from backend.app.core.auth import verify_token, verify_token_query

router = APIRouter(prefix="/api/annahme", tags=["Annahme"])


class Neu(BaseModel):
    name: str = Field(min_length=1, max_length=400)
    groesse: int = Field(ge=0)
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


@router.post("/ausblenden")
async def ausblenden(_=Depends(verify_token)):
    await annahme.ausblenden()
    return await annahme.alle()


@router.get("/ereignisse")
async def ereignisse(_=Depends(verify_token_query)):
    async def strom():
        async for d in annahme.ereignisse():
            yield f"data: {json.dumps(d, ensure_ascii=False)}\n\n"
    return StreamingResponse(strom(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{nr}")
async def einer(nr: int, _=Depends(verify_token)):
    return await _da(nr)


@router.patch("/{nr}")
async def teil(nr: int, request: Request, _=Depends(verify_token)):
    await _da(nr)
    try:
        versatz, laenge = int(request.headers.get("upload-offset", "")), int(request.headers.get("content-length", ""))
    except ValueError:
        raise HTTPException(400, "Es fehlen Upload-Offset oder Content-Length") from None
    if laenge > TEIL:
        raise HTTPException(413, "Das Teil ist größer als vereinbart")
    try:
        return await annahme.teil(nr, versatz, request.stream(), laenge)
    except Versatz as f:
        return JSONResponse({"detail": str(f), "empfangen": f.empfangen}, status_code=409)
    except WolkeFehler as f:
        raise HTTPException(503, f.meldung) from f


@router.post("/{nr}/erneut")
async def erneut(nr: int, _=Depends(verify_token)):
    await _da(nr)
    return await annahme.erneut(nr)


@router.delete("/{nr}")
async def entfernen(nr: int, _=Depends(verify_token)):
    await _da(nr)
    await annahme.entfernen(nr)
    return {"entfernt": nr}
