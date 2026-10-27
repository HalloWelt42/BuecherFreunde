"""API-Endpunkte für Backup und Wiederherstellung."""

import asyncio
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.core.auth import verify_token, verify_token_query
from backend.app.core.config import settings
from backend.app.services import sicherung

logger = logging.getLogger("buecherfreunde")
router = APIRouter(prefix="/api/backup", tags=["Backup"])


def _backup_dir() -> Path:
    """Gibt das Backup-Verzeichnis zurück."""
    d = settings.backup_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/create")
async def erstelle_backup(_: str = Depends(verify_token)):
    """Sichert von Hand nach der Sicherungsregel: sofort, aber nie ohne Änderung seit der jüngsten Sicherung."""
    lauf = await asyncio.to_thread(sicherung.sichern, sicherung.Anlass.HAND)
    return {
        "message": "Backup erstellt" if lauf.neu else f"Keine neue Sicherung nötig: {lauf.grund}",
        "filename": lauf.datei.name,
        "size": lauf.datei.stat().st_size,
        "neu": lauf.neu,
    }


@router.get("/list")
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


@router.get("/download")
async def download_backup(
    filename: str = "", _: str = Depends(verify_token_query)
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


@router.post("/restore")
async def restore_backup(
    file: UploadFile, _: str = Depends(verify_token)
):
    """Backup wiederherstellen."""
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "backup.zip"
        content = await file.read()

        # Größenlimit prüfen (1 GB)
        if len(content) > 1024 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Backup-Datei zu groß (max 1 GB)")

        with open(tmp_path, "wb") as f:
            f.write(content)

        if not zipfile.is_zipfile(tmp_path):
            raise HTTPException(status_code=400, detail="Keine gültige ZIP-Datei")

        with zipfile.ZipFile(tmp_path, "r") as zf:
            # Zip-Bomb-Schutz: entpackte Größe prüfen
            total_size = sum(info.file_size for info in zf.infolist())
            if total_size > 2 * 1024 * 1024 * 1024:  # 2 GB Limit
                raise HTTPException(status_code=400, detail="ZIP-Inhalt zu groß (max 2 GB)")

            # Datenbank wiederherstellen
            if "database/buecherfreunde.db" in zf.namelist():
                db_data = zf.read("database/buecherfreunde.db")
                settings.database_path.parent.mkdir(
                    parents=True, exist_ok=True
                )
                with open(settings.database_path, "wb") as db_file:
                    db_file.write(db_data)

            # Metadaten wiederherstellen (mit Zip Slip Schutz)
            storage_resolved = settings.storage_dir.resolve()
            for name in zf.namelist():
                if name.startswith("metadata/"):
                    rel = name[len("metadata/"):]
                    if rel:
                        target = (settings.storage_dir / rel).resolve()
                        # Zip Slip: Pfad muss innerhalb des Storage bleiben
                        if not target.is_relative_to(storage_resolved):
                            logger.warning("Zip Slip Versuch blockiert: %s", name)
                            continue
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with open(target, "wb") as mf:
                            mf.write(zf.read(name))

    logger.info("Backup wiederhergestellt: %s", file.filename)
    return {"message": "Backup wiederhergestellt"}


@router.get("/storage-info")
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
