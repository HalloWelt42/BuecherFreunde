"""API-Endpunkte für den Buch-Import."""

import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from backend.app.core.auth import verify_token, verify_token_query
from backend.app.core.config import settings
from backend.app.services.import_service import (
    cancel_pending_tasks,
    clear_finished_tasks,
    create_import_task,
    get_import_status,
    import_single_file,
    list_importable_files,
    scan_directory,
    update_task_status,
)
from backend.app.services.storage import SUPPORTED_FORMATS

logger = logging.getLogger("buecherfreunde.api.import")

router = APIRouter(prefix="/api/import", tags=["Import"])


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    _token: str = Depends(verify_token),
):
    """Lädt eine einzelne Datei hoch und importiert sie."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Kein Dateiname")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Format '{suffix}' nicht unterstützt. Erlaubt: {', '.join(sorted(SUPPORTED_FORMATS))}",
        )

    # Import-Aufgabe erstellen
    task_id = await create_import_task(file.filename)

    # Datei temporär speichern (nur Dateiname ohne Pfad gegen Path Traversal)
    safe_name = Path(file.filename).name
    import_dir = settings.import_dir
    import_dir.mkdir(parents=True, exist_ok=True)
    temp_path = import_dir / f"upload_{task_id}_{safe_name}"

    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        await update_task_status(task_id, "fehler", 0, "", str(e))
        raise HTTPException(status_code=500, detail=f"Upload fehlgeschlagen: {e}")

    # Import im Hintergrund starten
    async def _import():
        try:
            await import_single_file(temp_path, task_id)
        finally:
            temp_path.unlink(missing_ok=True)

    background_tasks.add_task(_import)

    return {"task_id": task_id, "datei": file.filename, "status": "wartend"}


@router.post("/upload-mehrere")
async def upload_multiple(
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
    _token: str = Depends(verify_token),
):
    """Lädt mehrere Dateien hoch und importiert sie."""
    tasks = []

    for file in files:
        if not file.filename:
            continue
        suffix = Path(file.filename).suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            continue

        task_id = await create_import_task(file.filename)

        safe_name = Path(file.filename).name
        import_dir = settings.import_dir
        import_dir.mkdir(parents=True, exist_ok=True)
        temp_path = import_dir / f"upload_{task_id}_{safe_name}"

        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        async def _import(path=temp_path, tid=task_id):
            try:
                await import_single_file(path, tid)
            finally:
                path.unlink(missing_ok=True)

        background_tasks.add_task(_import)
        tasks.append({"task_id": task_id, "datei": file.filename})

    return {"aufgaben": tasks, "anzahl": len(tasks)}


@router.post("/scan")
async def scan_import_dir(
    background_tasks: BackgroundTasks,
    anreichern: bool = Query(False, description="Metadaten via Open Library anreichern"),
    _token: str = Depends(verify_token),
):
    """Scannt das Import-Verzeichnis und importiert neue Dateien.

    Listet Dateien schnell auf (ohne Hash), erstellt sofort Tasks
    und verarbeitet alles im Hintergrund. Duplikate werden pro Datei
    beim Import erkannt.
    """
    files = list_importable_files(settings.import_dir)

    if not files:
        return {"gefunden": 0, "neu": 0, "aufgaben": []}

    tasks = []
    for f in files:
        file_path = Path(f["pfad"])
        task_id = await create_import_task(f["name"], f["pfad"])

        async def _import(path=file_path, tid=task_id, enrich=anreichern):
            await import_single_file(path, tid, enrich=enrich)

        background_tasks.add_task(_import)
        tasks.append({"task_id": task_id, "datei": f["name"]})

    return {"gefunden": len(files), "neu": len(tasks), "aufgaben": tasks}


@router.post("/externes-verzeichnis")
async def scan_external_dir(
    background_tasks: BackgroundTasks,
    anreichern: bool = Query(False, description="Metadaten via Open Library anreichern"),
    _token: str = Depends(verify_token),
):
    """Scannt das externe Verzeichnis und importiert neue Dateien.

    Listet Dateien schnell auf (ohne Hash), erstellt sofort Tasks
    und verarbeitet alles im Hintergrund. Duplikate werden pro Datei
    beim Import erkannt.
    """
    if not settings.external_dir.exists():
        raise HTTPException(
            status_code=404, detail="Externes Verzeichnis nicht gefunden"
        )

    files = list_importable_files(settings.external_dir)

    if not files:
        return {"gefunden": 0, "neu": 0, "aufgaben": []}

    tasks = []
    for f in files:
        file_path = Path(f["pfad"])
        task_id = await create_import_task(f["name"], f["pfad"])

        async def _import(path=file_path, tid=task_id, enrich=anreichern):
            await import_single_file(path, tid, enrich=enrich)

        background_tasks.add_task(_import)
        tasks.append({"task_id": task_id, "datei": f["name"]})

    return {"gefunden": len(files), "neu": len(tasks), "aufgaben": tasks}


@router.get("/status")
async def import_status(_token: str = Depends(verify_token)):
    """Gibt den Status aller Import-Aufgaben zurück."""
    result = await get_import_status()
    return result


@router.delete("/bereinigen")
async def clear_finished(_token: str = Depends(verify_token)):
    """Löscht alle abgeschlossenen Import-Aufgaben aus der Datenbank."""
    await clear_finished_tasks()
    result = await get_import_status()
    return result


@router.post("/abbrechen")
async def cancel_import(_token: str = Depends(verify_token)):
    """Bricht alle wartenden Import-Aufgaben ab."""
    await cancel_pending_tasks()
    result = await get_import_status()
    return result


@router.get("/events")
async def import_events(_token: str = Depends(verify_token_query)):
    """SSE-Endpunkt für Echtzeit-Fortschritt der Import-Aufgaben."""

    async def event_generator():
        last_data = None
        while True:
            result = await get_import_status()
            zaehler = result.get("zaehler", {})
            aufgaben = result.get("aufgaben", [])

            aktiv_count = (zaehler.get("wartend", 0) or 0) + (zaehler.get("verarbeite", 0) or 0)

            data = json.dumps(
                {
                    "zaehler": zaehler,
                    "aufgaben": aufgaben,
                    "aktiv": aktiv_count,
                },
                ensure_ascii=False,
                default=str,
            )

            if data != last_data:
                yield f"data: {data}\n\n"
                last_data = data

            if aktiv_count == 0:
                yield f"data: {data}\n\n"
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/vorschau")
async def preview_import_dir(
    verzeichnis: str = Query("import", description="'import' oder 'extern'"),
    _token: str = Depends(verify_token),
):
    """Zeigt eine Vorschau der importierbaren Dateien ohne Import."""
    if verzeichnis == "extern":
        directory = settings.external_dir
    else:
        directory = settings.import_dir

    if not directory.exists():
        return {"dateien": [], "verzeichnis": str(directory)}

    files = await scan_directory(directory)
    return {
        "dateien": files,
        "verzeichnis": str(directory),
        "gesamt": len(files),
        "neu": len([f for f in files if not f["ist_duplikat"]]),
        "duplikate": len([f for f in files if f["ist_duplikat"]]),
    }
