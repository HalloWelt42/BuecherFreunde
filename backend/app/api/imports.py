"""Ordner auf dem Gerät einlesen: der Einlese-Ordner und die externe Sammlung. Aufgenommen wird über dieselbe Annahme wie
beim Hochladen; Stand und Fortschritt stehen in der einen Liste unter /api/annahme."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.annahme import ordner
from backend.app.annahme.dienst import annahme
from backend.app.core.auth import braucht
from backend.app.core.config import settings

router = APIRouter(prefix="/api/import", tags=["Import"], dependencies=[Depends(braucht("hinzufuegen"))])


async def _einlesen(verzeichnis, quelle: str, anreichern: bool) -> dict:
    dateien = await asyncio.to_thread(ordner.dateien, verzeichnis)
    return {"gefunden": len(dateien), "neu": await annahme.aus_ordner(dateien, quelle, anreichern)}


@router.post("/scan")
async def scan_import_dir(anreichern: bool = Query(False, description="Angaben aus den Quellen ergänzen")):
    """Den Einlese-Ordner aufnehmen: `{gefunden, neu}`; was schon aufgenommen oder in Arbeit ist, kommt nicht noch einmal."""
    return await _einlesen(settings.import_dir, "ordner", anreichern)


@router.post("/externes-verzeichnis")
async def scan_external_dir(anreichern: bool = Query(False, description="Angaben aus den Quellen ergänzen")):
    """Die externe Sammlung aufnehmen; die Dateien bleiben dort, wo sie sind."""
    if not settings.external_dir.exists():
        raise HTTPException(status_code=404, detail="Externes Verzeichnis nicht gefunden")
    return await _einlesen(settings.external_dir, "extern", anreichern)


@router.get("/vorschau")
async def preview_import_dir(verzeichnis: str = Query("import", description="'import' oder 'extern'")):
    """Was im Ordner liegt, ohne aufzunehmen; mit Prüfsumme, ob es den Inhalt schon gibt."""
    directory = settings.external_dir if verzeichnis == "extern" else settings.import_dir
    dateien = await ordner.vorschau(directory)
    return {"dateien": dateien, "verzeichnis": str(directory), "gesamt": len(dateien),
            "neu": sum(1 for f in dateien if not f["ist_duplikat"]), "duplikate": sum(1 for f in dateien if f["ist_duplikat"])}
