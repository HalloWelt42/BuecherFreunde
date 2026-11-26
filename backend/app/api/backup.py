"""API-Endpunkte für Backup und Wiederherstellung."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.app.ablage import sicherungen
from backend.app.core.auth import braucht, verify_token, verify_token_inhalt
from backend.app.core.config import settings
from backend.app.einrichtung import wiederherstellen
from backend.app.einrichtung.modelle import Auftragsstand, Wiederherstellen, Wiederherstellfolgen
from backend.app.einrichtung.zustand import Einrichtungsfehler
from backend.app.services import sicherung

logger = logging.getLogger("buecherfreunde")
router = APIRouter(prefix="/api/backup", tags=["Backup"])


def _backup_dir() -> Path:
    """Gibt das Backup-Verzeichnis zurück."""
    d = settings.backup_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/create", dependencies=[Depends(braucht("einstellungen"))])
async def erstelle_backup(_: str = Depends(verify_token)):
    """Sichert von Hand nach der Sicherungsregel: sofort, aber nie ohne Änderung seit der jüngsten Sicherung."""
    lauf = await asyncio.to_thread(sicherung.sichern, sicherung.Anlass.HAND)
    if lauf.neu:
        await sicherungen.ablegen(lauf.datei)          # auch in die Kellerwolke, wenn eingeschaltet (BF-82)
    return {
        "message": "Backup erstellt" if lauf.neu else f"Keine neue Sicherung nötig: {lauf.grund}",
        "filename": lauf.datei.name,
        "size": lauf.datei.stat().st_size,
        "neu": lauf.neu,
    }


@router.get("/list", dependencies=[Depends(braucht("einstellungen"))])
async def liste_backups(_: str = Depends(verify_token)):
    """Alle vorhandenen Backups auflisten, jüngstes zuerst."""
    backups = []
    for f in sicherung.staende():
        backups.append({
            "filename": f.name,
            "size": f.stat().st_size,
            "created_at": datetime.fromtimestamp(
                f.stat().st_mtime
            ).isoformat(),
        })
    return backups


@router.get("/download", dependencies=[Depends(braucht("einstellungen", inhalt=True))])
async def download_backup(
    filename: str = "", _: str = Depends(verify_token_inhalt)
):
    """Backup-Datei herunterladen."""
    if not filename:
        # Neuestes Backup
        backups = sicherung.staende()
        if not backups:
            raise HTTPException(status_code=404, detail="Kein Backup vorhanden")
        path = backups[0]
    else:
        # Path Traversal verhindern: nur den Dateinamen verwenden
        safe_name = Path(filename).name
        path = _backup_dir() / safe_name
        if not path.resolve().is_relative_to(_backup_dir().resolve()):
            raise HTTPException(status_code=400, detail="Ungültiger Dateiname")
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Backup nicht gefunden")

    return FileResponse(
        path,
        media_type="application/zip",
        filename=path.name,
    )


@router.get("/restore/folgen", response_model=Wiederherstellfolgen, dependencies=[Depends(braucht("einstellungen"))])
async def restore_folgen(quelle: Literal["datei", "geraet", "kellerwolke"], kennung: str) -> Wiederherstellfolgen:
    """Vor dem Zurückspielen (BF-82): was die Sicherung enthält und was sie ersetzt (Bestand, Konto), mit `stand`. Eine Datei
    kommt vorher in Teilen über `POST /api/einrichtung/sicherungen/hochladen`."""
    try:
        return await wiederherstellen.folgen(quelle, kennung, ersetzen=True)
    except Einrichtungsfehler as f:
        raise HTTPException(f.status, f.meldung) from f


@router.post("/restore", response_model=Auftragsstand, dependencies=[Depends(braucht("einstellungen"))])
async def restore_backup(w: Wiederherstellen) -> Auftragsstand:
    """Zurückspielen nur mit dem `stand` der Folgen, als Auftrag "Sicherung einspielen" wie in der Ersteinrichtung; vorher entsteht
    eine Sicherung des jetzigen Stands, gelöscht wird nichts."""
    try:
        return await wiederherstellen.beginnen(w.quelle, w.kennung, w.stand, ersetzen=True)
    except Einrichtungsfehler as f:
        raise HTTPException(f.status, f.meldung) from f


@router.get("/storage-info", dependencies=[Depends(braucht("einstellungen"))])
async def storage_info(_: str = Depends(verify_token)):
    """Informationen über das Buchmaterial-Verzeichnis."""
    storage = settings.storage_dir
    total_size = 0
    file_count = 0

    if storage.exists():
        for f in storage.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size
                file_count += 1

    return {
        "path": str(storage),
        "size": total_size,
        "file_count": file_count,
        "rsync_hint": f"rsync -av {storage}/ ziel:/pfad/zum/backup/",
    }
