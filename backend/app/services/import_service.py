"""Import-Service fuer Buecher.

Verarbeitet einzelne Dateien und Verzeichnisse, erkennt Duplikate,
speichert im Hash-System und indexiert fuer die Volltextsuche.
"""

import asyncio
import logging
from pathlib import Path

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services.processor import process_book
from backend.app.services.storage import (
    SUPPORTED_FORMATS,
    check_duplicate,
    compute_hash,
    get_storage_path,
    save_cover,
    save_fulltext,
    save_metadata,
    store_file,
)

logger = logging.getLogger("buecherfreunde.import")


async def update_task_status(
    task_id: int,
    status: str,
    progress: int = 0,
    step: str = "",
    error: str = "",
    book_id: int | None = None,
) -> None:
    """Aktualisiert den Status einer Import-Aufgabe."""
    await db.execute(
        """UPDATE import_tasks
           SET status = ?, progress_percent = ?, current_step = ?,
               error = ?, book_id = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (status, progress, step, error, book_id, task_id),
    )
    await db.commit()


async def import_single_file(file_path: Path, task_id: int | None = None) -> dict:
    """Importiert eine einzelne Datei.

    Workflow: Hash -> Duplikat? -> Speichern -> Verarbeiten -> DB -> FTS

    Returns:
        Dict mit Ergebnis: {"status": "ok"|"duplikat"|"fehler", ...}
    """
    result = {"status": "fehler", "datei": file_path.name}

    # 1. Hash berechnen
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

    # 2. Duplikat pruefen
    if task_id:
        await update_task_status(task_id, "verarbeite", 20, "Duplikat wird geprueft")

    dup = check_duplicate(file_hash)
    if dup:
        # Auch in DB pruefen
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

    # 3. Im Hash-Speicher ablegen
    if task_id:
        await update_task_status(task_id, "verarbeite", 30, "Datei wird gespeichert")

    try:
        file_hash, storage_path = store_file(file_path, file_hash)
    except FileExistsError:
        if task_id:
            await update_task_status(task_id, "duplikat", 100, "Datei existiert bereits")
        result["status"] = "duplikat"
        return result
    except Exception as e:
        error = f"Speichern fehlgeschlagen: {e}"
        if task_id:
            await update_task_status(task_id, "fehler", 30, "", error)
        result["fehler"] = error
        return result

    # 4. Buch verarbeiten (Text, Metadaten, Cover extrahieren)
    if task_id:
        await update_task_status(task_id, "verarbeite", 50, "Inhalt wird extrahiert")

    from backend.app.services.storage import get_original_file

    original = get_original_file(file_hash)
    if not original:
        original = file_path  # Fallback

    proc_result = process_book(original)

    # 5. Open Library Anreicherung (wenn ISBN vorhanden)
    if task_id:
        await update_task_status(task_id, "verarbeite", 60, "ISBN wird gesucht")

    if proc_result.isbn and settings.openlibrary_enabled:
        if task_id:
            await update_task_status(task_id, "verarbeite", 65, "Metadaten werden angereichert (Open Library)")
        try:
            from backend.app.services.openlibrary import lookup_isbn
            ol_data = await lookup_isbn(proc_result.isbn)
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
                # Titel nur uebernehmen wenn bisher nur Dateiname
                if ol_data.get("titel") and proc_result.title == file_path.stem.replace("_", " ").replace("-", " "):
                    proc_result.title = ol_data["titel"]
                logger.info("Metadaten angereichert via Open Library fuer ISBN %s", proc_result.isbn)
        except Exception as e:
            logger.warning("Open Library Anreicherung fehlgeschlagen: %s", e)
    elif not proc_result.isbn and proc_result.title and settings.openlibrary_enabled:
        # Fallback: Titel/Autor-Suche wenn keine ISBN
        if task_id:
            await update_task_status(task_id, "verarbeite", 65, "Suche nach Metadaten (Titel/Autor)")
        try:
            from backend.app.services.openlibrary import search_books
            query = f"{proc_result.title} {proc_result.author}".strip()
            results = await search_books(query, limit=1)
            if results:
                ol_data = results[0]
                if ol_data.get("isbn"):
                    proc_result.isbn = ol_data["isbn"]
                if not proc_result.author and ol_data.get("autor"):
                    proc_result.author = ol_data["autor"]
                if not proc_result.year and ol_data.get("jahr"):
                    proc_result.year = ol_data["jahr"]
                logger.info("Metadaten via Titelsuche gefunden: %s", proc_result.title)
        except Exception as e:
            logger.warning("Open Library Titelsuche fehlgeschlagen: %s", e)

    # 6. Sidecar-Dateien speichern
    if task_id:
        await update_task_status(task_id, "verarbeite", 75, "Metadaten werden gespeichert")

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

    # 7. In Datenbank eintragen
    if task_id:
        await update_task_status(task_id, "verarbeite", 85, "Datenbankeintrag wird erstellt")

    file_size = file_path.stat().st_size
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
            file_path.name,
            str(storage_path),
            "cover.jpg" if proc_result.cover_data else "",
            proc_result.page_count,
            proc_result.fts_content,
        ),
    )
    await db.commit()
    book_id = cursor.lastrowid

    # Buecher ohne ISBN -> Kategorie "Ungeordnet"
    if not proc_result.isbn:
        ungeordnet = await db.fetch_one(
            "SELECT id FROM categories WHERE name = ?", ("Ungeordnet",)
        )
        if not ungeordnet:
            cur = await db.execute(
                "INSERT INTO categories (name, description) VALUES (?, ?)",
                ("Ungeordnet", "Bücher ohne ISBN oder Zuordnung"),
            )
            await db.commit()
            kat_id = cur.lastrowid
        else:
            kat_id = ungeordnet["id"]
        await db.execute(
            "INSERT OR IGNORE INTO book_categories (book_id, category_id) VALUES (?, ?)",
            (book_id, kat_id),
        )
        await db.commit()

    # 8. Fertig
    if task_id:
        await update_task_status(task_id, "fertig", 100, "Import abgeschlossen", "", book_id)

    result["status"] = "ok"
    result["book_id"] = book_id
    result["titel"] = proc_result.title
    result["hash"] = file_hash
    return result


async def scan_directory(directory: Path) -> list[dict]:
    """Scannt ein Verzeichnis nach importierbaren Dateien.

    Gibt eine Liste von Datei-Infos zurueck (ohne Import).
    """
    files = []
    if not directory.exists():
        return files

    for f in sorted(directory.rglob("*")):
        if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS:
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

    return files


async def create_import_task(filename: str, file_path: str = "") -> int:
    """Erstellt eine neue Import-Aufgabe und gibt die ID zurueck."""
    cursor = await db.execute(
        "INSERT INTO import_tasks (filename, file_path, status) VALUES (?, ?, 'wartend')",
        (filename, file_path),
    )
    await db.commit()
    return cursor.lastrowid


async def get_import_status() -> list[dict]:
    """Gibt den Status aller Import-Aufgaben zurueck."""
    return await db.fetch_all(
        """SELECT id, filename, status, progress_percent, current_step,
                  error, book_id, created_at, updated_at
           FROM import_tasks
           ORDER BY created_at DESC
           LIMIT 100"""
    )
