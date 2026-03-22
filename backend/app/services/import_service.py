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
from backend.app.services.processor import process_book
from backend.app.services.storage import (
    SUPPORTED_FORMATS,
    check_duplicate,
    compute_hash,
    get_original_file,
    get_storage_path,
    sanitize_filename,
    save_cover,
    save_fulltext,
    save_metadata,
    store_file,
)

logger = logging.getLogger("buecherfreunde.import")


def _repair_orphaned_storage(source_file: Path, storage_path: Path) -> None:
    """Repariert verwaisten Storage: kopiert Quelldatei rein falls keine Originaldatei vorhanden."""
    storage_path.mkdir(parents=True, exist_ok=True)

    # Prüfen ob bereits eine Originaldatei im Storage liegt
    sidecar_names = {"metadata.json", "fulltext.txt", "cover.jpg"}
    has_original = any(
        f.name not in sidecar_names and f.is_file()
        for f in storage_path.iterdir()
    )

    if has_original:
        logger.info("Verwaister Storage hat bereits Originaldatei, überspringe Kopie")
        return

    # Quelldatei in Storage kopieren (mit bereinigtem Namen)
    raw_name = re.sub(r"^upload_\d+_", "", source_file.name)
    safe_name = sanitize_filename(raw_name)
    target = storage_path / safe_name
    shutil.copy2(source_file, target)
    logger.info("Quelldatei in verwaisten Storage kopiert: %s -> %s", source_file.name, target.name)


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
        logger.info("import_single_file gestartet: '%s' (task %s)", original_name, task_id)
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
    """Eigentliche Import-Logik, wird von import_single_file aufgerufen."""

    # 0. Prüfen ob Datei existiert
    if not file_path.exists():
        error = f"Datei nicht gefunden: {file_path}"
        logger.error(error)
        if task_id:
            await update_task_status(task_id, "fehler", 0, "", error)
        result["fehler"] = error
        return result

    # 1. Prüfen ob Task noch existiert (könnte abgebrochen worden sein)
    if task_id:
        task_row = await db.fetch_one(
            "SELECT status FROM import_tasks WHERE id = ?", (task_id,)
        )
        if not task_row or task_row["status"] not in ("wartend", "verarbeite"):
            result["status"] = "abgebrochen"
            return result

    # 2. Hash berechnen
    if task_id:
        await update_task_status(task_id, "verarbeite", 10, "Hash wird berechnet")

    try:
        file_hash = compute_hash(file_path)
    except Exception as e:
        error = f"Hash-Berechnung fehlgeschlagen: {e}"
        if task_id:
            await update_task_status(task_id, "fehler", 0, "", error)
        result["fehler"] = error
        return result

    # 3. Duplikat prüfen
    if task_id:
        await update_task_status(task_id, "verarbeite", 20, "Duplikat wird geprüft")

    dup = check_duplicate(file_hash)
    existing = None
    if dup:
        existing = await db.fetch_one(
            "SELECT id, title FROM books WHERE hash = ?", (file_hash,)
        )
        if existing:
            if task_id:
                await update_task_status(
                    task_id, "duplikat", 100, "Duplikat erkannt", "", existing["id"]
                )
            result["status"] = "duplikat"
            result["book_id"] = existing["id"]
            result["titel"] = existing["title"]
            return result
        # Storage existiert aber kein DB-Eintrag -> verwaist, weitermachen
        logger.warning(
            "Verwaiste Datei im Storage gefunden (Hash %s...), erstelle DB-Eintrag",
            file_hash[:16],
        )

    # 4. Im Hash-Speicher ablegen (oder vorhandenen verwenden)
    if task_id:
        await update_task_status(task_id, "verarbeite", 30, "Datei wird gespeichert")

    if dup and not existing:
        # Verwaiste Datei - Storage-Pfad wiederverwenden, Quelldatei reinkopieren
        storage_path = get_storage_path(file_hash)
        _repair_orphaned_storage(file_path, storage_path)
        logger.info("Verwende vorhandenen Storage-Pfad: %s", storage_path)
    else:
        try:
            file_hash, storage_path = store_file(file_path, file_hash)
        except FileExistsError:
            # Noch ein Sicherheitscheck: vielleicht wurde zwischen Duplikat-Check
            # und store_file ein DB-Eintrag erstellt (Race Condition)
            race_check = await db.fetch_one(
                "SELECT id, title FROM books WHERE hash = ?", (file_hash,)
            )
            if race_check:
                if task_id:
                    await update_task_status(
                        task_id, "duplikat", 100, "Duplikat erkannt", "", race_check["id"]
                    )
                result["status"] = "duplikat"
                result["book_id"] = race_check["id"]
                result["titel"] = race_check["title"]
                return result
            # Verwaist - Storage wiederverwenden, Quelldatei reinkopieren
            storage_path = get_storage_path(file_hash)
            _repair_orphaned_storage(file_path, storage_path)
            logger.warning("FileExistsError aber kein DB-Eintrag, verwende Storage: %s", storage_path)
        except Exception as e:
            error = f"Speichern fehlgeschlagen: {e}"
            if task_id:
                await update_task_status(task_id, "fehler", 30, "", error)
            result["fehler"] = error
            return result

    # 5. Buch verarbeiten (Text, Metadaten, Cover extrahieren)
    if task_id:
        await update_task_status(task_id, "verarbeite", 50, "Inhalt wird extrahiert")

    original = get_original_file(file_hash)
    if not original:
        original = file_path  # Fallback

    try:
        proc_result = process_book(original)
    except Exception as e:
        logger.error("Prozessor-Fehler fuer '%s': %s", original_name, e)
        proc_result = None

    if proc_result is None or proc_result.error:
        # Trotz Fehler weitermachen -- Datei ist gespeichert, nur Metadaten fehlen
        logger.warning(
            "Verarbeitung fehlerhaft fuer '%s': %s",
            original_name,
            proc_result.error if proc_result else "Prozessor gab None zurueck",
        )
        if proc_result is None:
            from backend.app.services.processors.base import BookProcessingResult
            proc_result = BookProcessingResult()
            proc_result.title = file_path.stem.replace("_", " ").replace("-", " ")

    # 6. Open Library Anreicherung
    if task_id:
        await update_task_status(task_id, "verarbeite", 60, "Metadaten werden angereichert")

    if enrich and settings.openlibrary_enabled:
        try:
            await _enrich_from_openlibrary(proc_result, file_path, task_id)
        except Exception as e:
            logger.warning("Open Library Anreicherung fehlgeschlagen: %s", e)

    # 7. Sidecar-Dateien speichern
    if task_id:
        await update_task_status(task_id, "verarbeite", 75, "Metadaten werden gespeichert")

    try:
        metadata = {
            "titel": proc_result.title,
            "autor": proc_result.author,
            "isbn": proc_result.isbn,
            "verlag": proc_result.publisher,
            "jahr": proc_result.year,
            "sprache": proc_result.language,
            "beschreibung": proc_result.description,
            "seiten": proc_result.page_count,
        }
        save_metadata(file_hash, metadata)

        if proc_result.fulltext:
            save_fulltext(file_hash, proc_result.fulltext)

        if proc_result.cover_data:
            save_cover(file_hash, proc_result.cover_data)
    except Exception as e:
        logger.warning("Sidecar-Speicherung fehlgeschlagen: %s", e)

    # 8. In Datenbank eintragen
    if task_id:
        await update_task_status(task_id, "verarbeite", 85, "Datenbankeintrag wird erstellt")

    try:
        # Dateigroesse aus Storage lesen (nicht aus temp_path die geloescht wird)
        stored_file = get_original_file(file_hash)
        file_size = stored_file.stat().st_size if stored_file else 0
    except Exception:
        file_size = 0

    file_format = file_path.suffix.lower().lstrip(".")

    cursor = await db.execute(
        """INSERT INTO books
           (hash, title, author, isbn, publisher, year, language, description,
            file_format, file_size, file_name, storage_path, cover_path,
            page_count, fts_content)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            file_hash,
            proc_result.title,
            proc_result.author,
            proc_result.isbn,
            proc_result.publisher,
            proc_result.year,
            proc_result.language,
            proc_result.description,
            file_format,
            file_size,
            original_name,
            str(storage_path),
            "cover.jpg" if proc_result.cover_data else "",
            proc_result.page_count,
            proc_result.fts_content,
        ),
    )
    await db.commit()
    book_id = cursor.lastrowid

    # Bücher ohne ISBN -> Kategorie "Ungeordnet"
    if not proc_result.isbn:
        try:
            await _assign_ungeordnet(book_id)
        except Exception as e:
            logger.warning("Kategorie-Zuordnung fehlgeschlagen: %s", e)

    # 9. Fertig
    if task_id:
        await update_task_status(task_id, "fertig", 100, "Import abgeschlossen", "", book_id)

    result["status"] = "ok"
    result["book_id"] = book_id
    result["titel"] = proc_result.title
    result["hash"] = file_hash
    logger.info("Import erfolgreich: '%s' (ID %d)", proc_result.title, book_id)
    return result


async def _enrich_from_openlibrary(proc_result, file_path, task_id):
    """Reichert Metadaten via Open Library an."""
    if proc_result.isbn:
        if task_id and await is_task_cancelled(task_id):
            return
        if task_id:
            await update_task_status(task_id, "verarbeite", 65, "Open Library (ISBN)")
        from backend.app.services.openlibrary import lookup_isbn
        ol_data = await asyncio.wait_for(lookup_isbn(proc_result.isbn), timeout=15.0)
        if ol_data:
            if not proc_result.author and ol_data.get("autor"):
                proc_result.author = ol_data["autor"]
            if not proc_result.publisher and ol_data.get("verlag"):
                proc_result.publisher = ol_data["verlag"]
            if not proc_result.year and ol_data.get("jahr"):
                proc_result.year = ol_data["jahr"]
            if not proc_result.language and ol_data.get("sprache"):
                proc_result.language = ol_data["sprache"]
            if not proc_result.description and ol_data.get("beschreibung"):
                proc_result.description = ol_data["beschreibung"]
            if ol_data.get("titel") and proc_result.title == file_path.stem.replace("_", " ").replace("-", " "):
                proc_result.title = ol_data["titel"]
            logger.info("Metadaten angereichert via ISBN %s", proc_result.isbn)
    elif proc_result.title:
        if task_id and await is_task_cancelled(task_id):
            return
        if task_id:
            await update_task_status(task_id, "verarbeite", 65, "Open Library (Titelsuche)")
        from backend.app.services.openlibrary import search_books
        query = f"{proc_result.title} {proc_result.author}".strip()
        results = await asyncio.wait_for(search_books(query, limit=1), timeout=15.0)
        if results:
            ol_data = results[0]
            if ol_data.get("isbn"):
                proc_result.isbn = ol_data["isbn"]
            if not proc_result.author and ol_data.get("autor"):
                proc_result.author = ol_data["autor"]
            if not proc_result.year and ol_data.get("jahr"):
                proc_result.year = ol_data["jahr"]
            logger.info("Metadaten via Titelsuche: %s", proc_result.title)


async def _assign_ungeordnet(book_id: int):
    """Ordnet ein Buch der Kategorie 'Ungeordnet' zu."""
    ungeordnet = await db.fetch_one(
        "SELECT id FROM categories WHERE slug = ?", ("ungeordnet",)
    )
    if not ungeordnet:
        cur = await db.execute(
            "INSERT OR IGNORE INTO categories (name, slug, description) VALUES (?, ?, ?)",
            ("Ungeordnet", "ungeordnet", "Bücher ohne ISBN oder Zuordnung"),
        )
        await db.commit()
        if cur.lastrowid:
            kat_id = cur.lastrowid
        else:
            row = await db.fetch_one(
                "SELECT id FROM categories WHERE slug = ?", ("ungeordnet",)
            )
            kat_id = row["id"]
    else:
        kat_id = ungeordnet["id"]
    await db.execute(
        "INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'import')",
        (book_id, kat_id),
    )
    await db.commit()


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
                dup = check_duplicate(file_hash)
                existing = await db.fetch_one(
                    "SELECT id, title FROM books WHERE hash = ?", (file_hash,)
                )
                files.append({
                    "pfad": str(f),
                    "name": f.name,
                    "groesse": f.stat().st_size,
                    "format": f.suffix.lower(),
                    "hash": file_hash,
                    "ist_duplikat": dup is not None or existing is not None,
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
