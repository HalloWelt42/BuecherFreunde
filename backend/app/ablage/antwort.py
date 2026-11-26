"""Das Original eines Buchs als Antwort an den Browser, mit Bereichen (Leser holen nur, was sie zeigen): vom Gerät, aus dem
Zwischenspeicher oder durchgereicht aus der Kellerwolke, ohne es hier abzulegen. Zum Ansehen im Browser kommt es inline,
zum Herunterladen als Anhang; der Weg ist derselbe."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from backend.app.ablage import originale
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core.config import settings
from backend.app.services.storage import get_storage_path, ist_original

FEHLT = "Dieses Buch liegt noch nicht in der Kellerwolke"


def auf_dem_geraet(file_hash: str) -> Path | None:
    """Das Original, wenn es auf dem Gerät liegt (Ablage ohne Kellerwolke oder noch im Zwischenlager)."""
    ordner = get_storage_path(file_hash)
    kandidaten = [f for f in ordner.iterdir() if ist_original(f)] if ordner.exists() else []
    zwischen = settings.zwischen_dir / "original" / file_hash
    kandidaten += [f for f in zwischen.iterdir() if f.suffix != ".halb"] if zwischen.exists() else []
    return kandidaten[0] if kandidaten else None


async def original_antwort(request: Request, file_hash: str, art: str, name: str, herunterladen: bool = False) -> Response:
    weise = "attachment" if herunterladen else "inline"
    da = auf_dem_geraet(file_hash)
    if da is not None:
        return FileResponse(da, media_type=art, filename=name, headers={"Accept-Ranges": "bytes"}, content_disposition_type=weise)
    ablage = originale.eintrag(file_hash)
    if ablage is None or not wolke.bereit:
        raise HTTPException(status_code=404, detail=FEHLT)
    return await wolke_antwort(request, ablage["knoten"], art, name or ablage["name"], herunterladen)


async def wolke_antwort(request: Request, knoten: str, art: str, name: str, herunterladen: bool = False) -> Response:
    """Eine Datei der Kellerwolke, durchgereicht mit Bereichen (auch für Fassungen eines Buchs, BF-71)."""
    weise = "attachment" if herunterladen else "inline"
    try:
        r = await wolke.strom(knoten, request.headers.get("range"))
    except WolkeFehler as f:
        raise HTTPException(status_code=503, detail=f.meldung) from f
    if r.status_code >= 400 and r.status_code != 416:
        await r.aclose()
        raise HTTPException(status_code=503, detail=f"Die Kellerwolke meldet {r.status_code}")
    kopf = {k: r.headers[k] for k in ("content-length", "content-range", "etag") if k in r.headers}
    kopf["Accept-Ranges"] = "bytes"
    kopf["Content-Disposition"] = f"{weise}; filename*=UTF-8''{quote(name)}"

    async def strom():
        try:
            async for stueck in r.aiter_raw(1 << 16):
                yield stueck
        finally:
            await r.aclose()

    return StreamingResponse(strom(), status_code=r.status_code, media_type=art, headers=kopf)
