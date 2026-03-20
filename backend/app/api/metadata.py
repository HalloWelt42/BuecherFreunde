"""API-Endpunkte fuer Metadatenanreicherung."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from backend.app.core.auth import verify_token
from backend.app.core.database import db
from backend.app.services.openlibrary import check_connection, lookup_isbn, search_books

logger = logging.getLogger("buecherfreunde.api.metadata")

router = APIRouter(prefix="/api/metadata", tags=["Metadaten"])


@router.post("/buch/{book_id}/anreichern")
async def enrich_book(book_id: int, _token: str = Depends(verify_token)):
    """Reichert ein Buch mit Metadaten von Open Library an."""
    book = await db.fetch_one(
        "SELECT id, isbn, title, author FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    result = None

    # Zuerst ISBN-Lookup versuchen
    if book["isbn"]:
        result = await lookup_isbn(book["isbn"])

    # Falls kein ISBN-Treffer, nach Titel/Autor suchen
    if not result and book["title"]:
        query = f"{book['title']} {book['author']}".strip()
        results = await search_books(query, limit=1)
        if results:
            result = results[0]

    if not result:
        return {"angereichert": False, "grund": "Keine Metadaten gefunden"}

    # Vorschau zurueckgeben (nicht automatisch uebernehmen)
    return {
        "angereichert": True,
        "vorschlag": result,
        "aktuell": {
            "titel": book["title"],
            "autor": book["author"],
            "isbn": book["isbn"],
        },
    }


@router.post("/buch/{book_id}/uebernehmen")
async def apply_metadata(
    book_id: int, felder: dict, _token: str = Depends(verify_token)
):
    """Uebernimmt vorgeschlagene Metadaten fuer ein Buch."""
    existing = await db.fetch_one("SELECT id FROM books WHERE id = ?", (book_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    # Nur erlaubte Felder aktualisieren
    allowed = {"title", "author", "isbn", "publisher", "year", "language", "description"}
    # Mapping von deutschen Feldnamen zu DB-Spalten
    field_map = {
        "titel": "title",
        "autor": "author",
        "isbn": "isbn",
        "verlag": "publisher",
        "jahr": "year",
        "sprache": "language",
        "beschreibung": "description",
    }

    updates = {}
    for key, value in felder.items():
        db_key = field_map.get(key, key)
        if db_key in allowed and value:
            updates[db_key] = value

    if not updates:
        raise HTTPException(status_code=400, detail="Keine gueltigen Felder")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [book_id]
    await db.execute(
        f"UPDATE books SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
        tuple(values),
    )
    await db.commit()

    return {"uebernommen": True, "felder": list(updates.keys())}


@router.post("/bulk-anreichern")
async def enrich_all(
    background_tasks: BackgroundTasks,
    _token: str = Depends(verify_token),
):
    """Reichert alle Buecher ohne vollstaendige Metadaten an."""
    # Buecher mit fehlenden Metadaten finden
    books = await db.fetch_all(
        """SELECT id, isbn, title, author FROM books
           WHERE (isbn = '' OR isbn IS NULL)
              OR (author = '' OR author IS NULL)
              OR (publisher = '' OR publisher IS NULL)
           LIMIT 100"""
    )

    if not books:
        return {"zu_bearbeiten": 0}

    async def _enrich_batch():
        for book in books:
            try:
                result = None
                if book["isbn"]:
                    result = await lookup_isbn(book["isbn"])
                if not result and book["title"]:
                    query = f"{book['title']} {book['author']}".strip()
                    results = await search_books(query, limit=1)
                    if results:
                        result = results[0]
                # Automatisch uebernehmen bei Bulk
                if result:
                    updates = {}
                    field_map = {
                        "titel": "title", "autor": "author", "isbn": "isbn",
                        "verlag": "publisher", "jahr": "year",
                        "sprache": "language", "beschreibung": "description",
                    }
                    for key, value in result.items():
                        db_key = field_map.get(key)
                        if db_key and value:
                            updates[db_key] = value
                    if updates:
                        set_clause = ", ".join(f"{k} = ?" for k in updates)
                        values = list(updates.values()) + [book["id"]]
                        await db.execute(
                            f"UPDATE books SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                            tuple(values),
                        )
                        await db.commit()
            except Exception as e:
                logger.warning("Anreicherung fehlgeschlagen fuer Buch %d: %s", book["id"], e)

    background_tasks.add_task(_enrich_batch)
    return {"zu_bearbeiten": len(books), "status": "gestartet"}


@router.get("/verbindungsstatus")
async def connection_status(_token: str = Depends(verify_token)):
    """Prueft die Verbindung zu Open Library."""
    return await check_connection()
