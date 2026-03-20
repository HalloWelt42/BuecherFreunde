"""API-Endpunkte fuer Backup und Wiederherstellung."""

import logging
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.core.auth import verify_token
from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde")
router = APIRouter(prefix="/api/backup", tags=["Backup"])


def _backup_dir() -> Path:
    """Gibt das Backup-Verzeichnis zurueck."""
    d = settings.backup_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/create")
async def erstelle_backup(_: str = Depends(verify_token)):
    """Erstellt ein vollstaendiges Backup als ZIP."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"buecherfreunde_backup_{timestamp}.zip"
    zip_path = _backup_dir() / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Datenbank
        db_path = settings.database_path
        if db_path.exists():
            zf.write(db_path, "database/buecherfreunde.db")

        # VERSION
        version_path = Path(__file__).resolve().parents[3] / "VERSION"
        if version_path.exists():
            zf.write(version_path, "VERSION")

        # Metadaten aus Storage (metadata.json pro Buch)
        storage = settings.storage_dir
        if storage.exists():
            for meta_file in storage.rglob("metadata.json"):
                rel = meta_file.relative_to(storage)
                zf.write(meta_file, f"metadata/{rel}")

    size = zip_path.stat().st_size
    logger.info("Backup erstellt: %s (%d Bytes)", zip_name, size)
    return {
        "message": "Backup erstellt",
        "filename": zip_name,
        "size": size,
    }


@router.get("/list")
async def liste_backups(_: str = Depends(verify_token)):
    """Alle vorhandenen Backups auflisten."""
    backups = []
    for f in sorted(_backup_dir().glob("*.zip"), reverse=True):
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
    filename: str = "", _: str = Depends(verify_token)
):
    """Backup-Datei herunterladen."""
    if not filename:
        # Neuestes Backup
        backups = sorted(_backup_dir().glob("*.zip"), reverse=True)
        if not backups:
            raise HTTPException(status_code=404, detail="Kein Backup vorhanden")
        path = backups[0]
    else:
        path = _backup_dir() / filename
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
        with open(tmp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        with zipfile.ZipFile(tmp_path, "r") as zf:
            # Datenbank wiederherstellen
            if "database/buecherfreunde.db" in zf.namelist():
                db_data = zf.read("database/buecherfreunde.db")
                settings.database_path.parent.mkdir(
                    parents=True, exist_ok=True
                )
                with open(settings.database_path, "wb") as db_file:
                    db_file.write(db_data)

            # Metadaten wiederherstellen
            for name in zf.namelist():
                if name.startswith("metadata/"):
                    rel = name[len("metadata/"):]
                    if rel:
                        target = settings.storage_dir / rel
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with open(target, "wb") as mf:
                            mf.write(zf.read(name))

    logger.info("Backup wiederhergestellt: %s", file.filename)
    return {"message": "Backup wiederhergestellt"}


@router.get("/storage-info")
async def storage_info(_: str = Depends(verify_token)):
    """Informationen ueber das Buchmaterial-Verzeichnis."""
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
