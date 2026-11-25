"""Import-Service für Bücher.

Verarbeitet einzelne Dateien und Verzeichnisse, erkennt Duplikate,
speichert im Hash-System und indexiert für die Volltextsuche.
"""

import asyncio
import logging
import re
import shutil
from pathlib import Path

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.ablage.namen import sauber
from backend.app.ablage.wolke import wolke
from backend.app.annahme import angaben, auswertung
from backend.app.annahme.eintragen import ablegen, eintragen
from backend.app.services.storage import SUPPORTED_FORMATS, compute_hash, get_storage_path, sanitize_filename

logger = logging.getLogger("buecherfreunde.import")
_eine = asyncio.Semaphore(1)


async def update_task_status(
    task_id: int,
    status: str,
    progress: int = 0,
    step: str = "",
    error: str = "",
    book_id: int | None = None,
) -> None:
    """Aktualisiert den Status einer Import-Aufgabe."""
    try:
        await db.execute(
            """UPDATE import_tasks
               SET status = ?, progress_percent = ?, current_step = ?,
                   error = ?, book_id = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (status, progress, step, error, book_id, task_id),
        )
        await db.commit()
    except Exception as e:
        logger.error("Task-Status-Update fehlgeschlagen fuer %d: %s", task_id, e)


async def import_single_file(file_path: Path, task_id: int | None = None, enrich: bool = True) -> dict:
    """Importiert eine einzelne Datei.

    Workflow: Hash -> Duplikat? -> Speichern -> Verarbeiten -> DB -> FTS

    Returns:
        Dict mit Ergebnis: {"status": "ok"|"duplikat"|"fehler", ...}
    """
    # Upload-Prefix entfernen: "upload_1234_dateiname.pdf" -> "dateiname.pdf"
    raw_name = file_path.name
    raw_name = re.sub(r"^upload_\d+_", "", raw_name)
    original_name = sanitize_filename(raw_name)
    result = {"status": "fehler", "datei": original_name}

    try:
        async with _eine:                                   # immer nur ein Buch zugleich (wenig Arbeitsspeicher)
            return await _do_import(file_path, task_id, enrich, original_name, result)
    except BaseException as e:
        error = f"{type(e).__name__}: {e}"
        logger.error("Import-Fehler fuer '%s': %s", original_name, error, exc_info=True)
        if task_id:
            try:
                await update_task_status(task_id, "fehler", 0, "", error)
            except BaseException:
                pass
        result["fehler"] = error
        return result


async def _do_import(
    file_path: Path,
    task_id: int | None,
    enrich: bool,
    original_name: str,
    result: dict,
) -> dict:
    """Eine Datei vom Gerät (Ordner, gemeinfreies Buch) aufnehmen: derselbe Weg wie beim Hochladen (annahme/), das Original
    geht in die Kellerwolke, ohne sie bleibt es im Speicher des Geräts."""
    async def melde(status: str, anteil: int, schritt: str, fehler: str = "", buch: int | None = None) -> None:
        if task_id:
            await update_task_status(task_id, status, anteil, schritt, fehler, buch)

    if not file_path.exists():
        result["fehler"] = f"Datei nicht gefunden: {file_path}"
        await melde("fehler", 0, "", result["fehler"])
        return result
    if task_id and await is_task_cancelled(task_id):
        result["status"] = "abgebrochen"
        return result

    await melde("verarbeite", 10, "Prüfsumme wird gebildet")
    file_hash = await asyncio.to_thread(compute_hash, file_path)
    da = await db.fetch_one("SELECT id, title FROM books WHERE hash = ?", (file_hash,))
    if da:
        await melde("duplikat", 100, "Gibt es schon", "", da["id"])
        return result | {"status": "duplikat", "book_id": da["id"], "titel": da["title"], "hash": file_hash}

    await melde("verarbeite", 30, "Text und Umschlag werden gelesen")
    e = await auswertung.auswerten(file_path)
    if not e.lesbar:
        result["fehler"] = e.grund
        await melde("fehler", 0, "", e.grund)
        return result
    if enrich:
        await melde("verarbeite", 60, "Angaben werden ergänzt")
        await angaben.ergaenzen(e, file_path.stem)
    if task_id and await is_task_cancelled(task_id):
        result["status"] = "abgebrochen"
        return result

    await melde("verarbeite", 75, "Wird abgelegt")
    groesse = file_path.stat().st_size
    knoten = None
    if wolke.bereit:
        await wolke.ordner(f"{settings.ablage_ordner}/Eingang")
        knoten = (await wolke.datei_schreiben(f"{settings.ablage_ordner}/Eingang/{file_hash[:12]} {sauber(original_name, 180)}", file_path))["id"]
    else:
        ziel = get_storage_path(file_hash) / original_name
        ziel.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, file_path, ziel)
    await melde("verarbeite", 85, "Kommt ins Regal")
    buch = await eintragen(file_hash, original_name, groesse, e)
    if knoten:
        await ablegen(buch, knoten)
    await melde("fertig", 100, "In der Bibliothek", "", buch)
    logger.info("Aufgenommen: '%s' (Nummer %d)", e.title, buch)
    return result | {"status": "ok", "book_id": buch, "titel": e.title, "hash": file_hash}


async def scan_directory(directory: Path) -> list[dict]:
    """Scannt ein Verzeichnis nach importierbaren Dateien.

    Gibt eine Liste von Datei-Infos zurück (ohne Import).
    """
    files = []
    if not directory.exists():
        return files

    for f in sorted(directory.rglob("*")):
        if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS:
            try:
                file_hash = compute_hash(f)
                existing = await db.fetch_one(
                    "SELECT id, title FROM books WHERE hash = ?", (file_hash,)
                )
                files.append({
                    "pfad": str(f),
                    "name": f.name,
                    "groesse": f.stat().st_size,
                    "format": f.suffix.lower(),
                    "hash": file_hash,
                    "ist_duplikat": existing is not None,
                    "bestehendes_buch": existing["title"] if existing else None,
                })
            except Exception as e:
                logger.warning("Datei '%s' uebersprungen: %s", f.name, e)

    return files


def list_importable_files(directory: Path) -> list[dict]:
    """Listet importierbare Dateien schnell auf (ohne Hash, ohne DB-Check).

    Nur Dateiname, Pfad, Groesse und Format -- kehrt sofort zurueck.
    """
    files = []
    if not directory.exists():
        return files

    for f in sorted(directory.rglob("*")):
        if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS:
            files.append({
                "pfad": str(f),
                "name": f.name,
                "groesse": f.stat().st_size,
                "format": f.suffix.lower(),
            })

    return files


async def create_import_task(filename: str, file_path: str = "") -> int:
    """Erstellt eine neue Import-Aufgabe und gibt die ID zurück."""
    cursor = await db.execute(
        "INSERT INTO import_tasks (filename, file_path, status) VALUES (?, ?, 'wartend')",
        (filename, file_path),
    )
    await db.commit()
    return cursor.lastrowid


async def get_import_status() -> dict:
    """Gibt den Status aller Import-Aufgaben zurück.

    Liefert Gesamtzahlen und nur die aktiven + letzten fertigen Tasks.
    """
    counts = await db.fetch_one(
        """SELECT
             COUNT(*) as gesamt,
             SUM(CASE WHEN status = 'wartend' THEN 1 ELSE 0 END) as wartend,
             SUM(CASE WHEN status = 'verarbeite' THEN 1 ELSE 0 END) as verarbeite,
             SUM(CASE WHEN status = 'fertig' THEN 1 ELSE 0 END) as fertig,
             SUM(CASE WHEN status = 'fehler' THEN 1 ELSE 0 END) as fehler,
             SUM(CASE WHEN status = 'duplikat' THEN 1 ELSE 0 END) as duplikat
           FROM import_tasks"""
    )

    # Aktive Tasks (verarbeite + wartend, max 50) + letzte fertige (max 20)
    aktive = await db.fetch_all(
        """SELECT id, filename, status, progress_percent, current_step,
                  error, book_id, created_at, updated_at
           FROM import_tasks
           WHERE status IN ('verarbeite', 'wartend')
           ORDER BY created_at ASC
           LIMIT 50"""
    )

    letzte = await db.fetch_all(
        """SELECT id, filename, status, progress_percent, current_step,
                  error, book_id, created_at, updated_at
           FROM import_tasks
           WHERE status IN ('fertig', 'fehler', 'duplikat')
           ORDER BY updated_at DESC
           LIMIT 20"""
    )

    return {
        "zaehler": dict(counts) if counts else {},
        "aufgaben": aktive + letzte,
    }


async def clear_finished_tasks() -> int:
    """Löscht alle fertigen, fehlerhaften und duplikat Tasks aus der DB."""
    result = await db.execute(
        "DELETE FROM import_tasks WHERE status IN ('fertig', 'fehler', 'duplikat')"
    )
    await db.commit()
    return result


async def cancel_pending_tasks() -> int:
    """Bricht alle wartenden und aktiven Tasks ab."""
    await db.execute(
        "DELETE FROM import_tasks WHERE status = 'wartend'"
    )
    await db.execute(
        """UPDATE import_tasks SET status = 'fehler', error = 'Abgebrochen',
           current_step = 'Abgebrochen', updated_at = datetime('now')
           WHERE status = 'verarbeite'"""
    )
    await db.commit()


async def is_task_cancelled(task_id: int) -> bool:
    """Prüft ob ein Task abgebrochen wurde."""
    row = await db.fetch_one(
        "SELECT status FROM import_tasks WHERE id = ?", (task_id,)
    )
    if not row:
        return True  # Task gelöscht = abgebrochen
    return row["status"] not in ("wartend", "verarbeite")
