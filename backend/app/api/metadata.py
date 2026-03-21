"""API-Endpunkte fuer Metadatenanreicherung."""

import logging
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from backend.app.core.auth import verify_token
from backend.app.core.database import db
from backend.app.services import googlebooks, openlibrary
from backend.app.services.storage import save_cover

logger = logging.getLogger("buecherfreunde.api.metadata")

router = APIRouter(prefix="/api/metadata", tags=["Metadaten"])


def _slugify(text: str) -> str:
    """Erzeugt einen URL-freundlichen Slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


async def _ensure_categories(names: list[str]) -> list[int]:
    """Stellt sicher, dass Kategorien existieren und gibt deren IDs zurueck.

    Erstellt fehlende Kategorien automatisch.
    """
    cat_ids = []
    for name in names:
        name = name.strip()
        if not name or len(name) < 2:
            continue

        slug = _slugify(name)
        if not slug:
            continue

        existing = await db.fetch_one(
            "SELECT id FROM categories WHERE slug = ?", (slug,)
        )
        if existing:
            cat_ids.append(existing["id"])
        else:
            try:
                cursor = await db.execute(
                    """INSERT INTO categories (name, slug, description, color, icon, sort_order)
                       VALUES (?, ?, '', '#6b7280', '', 0)""",
                    (name, slug),
                )
                cat_ids.append(cursor.lastrowid)
            except Exception:
                # Slug-Kollision bei gleichzeitigem Zugriff
                existing = await db.fetch_one(
                    "SELECT id FROM categories WHERE slug = ?", (slug,)
                )
                if existing:
                    cat_ids.append(existing["id"])

    return cat_ids


async def _assign_categories(book_id: int, cat_ids: list[int]) -> None:
    """Ordnet Kategorien einem Buch zu (addiert, ersetzt nicht)."""
    for cat_id in cat_ids:
        await db.execute(
            "INSERT OR IGNORE INTO book_categories (book_id, category_id) VALUES (?, ?)",
            (book_id, cat_id),
        )


@router.post("/buch/{book_id}/anreichern")
async def enrich_book(
    book_id: int,
    quelle: str | None = Query(None, description="google_books oder open_library"),
    _token: str = Depends(verify_token),
):
    """Reichert ein Buch mit Metadaten an.

    Ohne Quellangabe: Google Books zuerst, dann Open Library.
    Mit quelle=google_books oder quelle=open_library: nur diese Quelle.
    """
    book = await db.fetch_one(
        "SELECT id, hash, isbn, title, author, publisher, year, language, "
        "description, page_count, cover_path FROM books WHERE id = ?",
        (book_id,),
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    # Bestehende Kategorien laden
    cats = await db.fetch_all(
        """SELECT c.name FROM categories c
           JOIN book_categories bc ON bc.category_id = c.id
           WHERE bc.book_id = ?""",
        (book_id,),
    )
    aktuelle_kategorien = [c["name"] for c in cats]

    result = None
    quelle_name = ""

    suche_google = quelle in (None, "google_books")
    suche_ol = quelle in (None, "open_library")

    # 1. Google Books
    if suche_google:
        if book["isbn"]:
            result = await googlebooks.lookup_isbn(book["isbn"])
        if not result and book["title"]:
            query = f"{book['title']} {book['author']}".strip()
            results = await googlebooks.search_books(query, limit=1)
            if results:
                result = results[0]
        if result:
            quelle_name = "google_books"

    # 2. Open Library
    if not result and suche_ol:
        if book["isbn"]:
            result = await openlibrary.lookup_isbn(book["isbn"])
        if not result and book["title"]:
            query = f"{book['title']} {book['author']}".strip()
            results = await openlibrary.search_books(query, limit=1)
            if results:
                result = results[0]
        if result:
            quelle_name = "open_library"

    if not result:
        quelle_text = {"google_books": "Google Books", "open_library": "Open Library"}.get(quelle, "allen Quellen")
        return {"angereichert": False, "grund": f"Keine Metadaten in {quelle_text} gefunden"}

    return {
        "angereichert": True,
        "quelle": quelle_name,
        "vorschlag": result,
        "aktuell": {
            "titel": book["title"],
            "autor": book["author"],
            "isbn": book["isbn"],
            "verlag": book["publisher"],
            "jahr": book["year"],
            "sprache": book["language"],
            "beschreibung": book["description"],
            "seiten": book["page_count"],
            "hat_cover": bool(book["cover_path"]),
            "kategorien": aktuelle_kategorien,
        },
    }


@router.post("/buch/{book_id}/uebernehmen")
async def apply_metadata(
    book_id: int, felder: dict, _token: str = Depends(verify_token)
):
    """Uebernimmt vorgeschlagene Metadaten fuer ein Buch.

    Aktualisiert Buchfelder, erstellt/verknuepft Kategorien,
    laedt Cover-Bild herunter und persistiert es.
    """
    book = await db.fetch_one(
        "SELECT id, hash, cover_path FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    # Buch-Felder aktualisieren
    allowed = {"title", "author", "isbn", "publisher", "year", "language", "description", "page_count"}
    field_map = {
        "titel": "title",
        "autor": "author",
        "isbn": "isbn",
        "verlag": "publisher",
        "jahr": "year",
        "sprache": "language",
        "beschreibung": "description",
        "seiten": "page_count",
    }

    updates = {}
    for key, value in felder.items():
        if key in ("kategorien", "cover_url", "raw", "identifiers", "excerpts", "links"):
            continue
        db_key = field_map.get(key, key)
        if db_key in allowed and value:
            updates[db_key] = value

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [book_id]
        await db.execute(
            f"UPDATE books SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            tuple(values),
        )

    # Kategorien erstellen und zuordnen
    kategorien = felder.get("kategorien", [])
    if kategorien:
        cat_ids = await _ensure_categories(kategorien)
        await _assign_categories(book_id, cat_ids)

    # Cover herunterladen und persistieren
    cover_url = felder.get("cover_url", "")
    cover_gespeichert = False
    if cover_url:
        quelle = felder.get("quelle", "")
        if "google" in cover_url or quelle == "google_books":
            cover_data = await googlebooks.download_cover(cover_url)
        else:
            cover_data = await openlibrary.download_cover(cover_url)
        if cover_data:
            save_cover(book["hash"], cover_data)
            await db.execute(
                "UPDATE books SET cover_path = 'cover.jpg', updated_at = datetime('now') WHERE id = ?",
                (book_id,),
            )
            cover_gespeichert = True

    await db.commit()

    return {
        "uebernommen": True,
        "felder": list(updates.keys()),
        "kategorien_erstellt": len(kategorien),
        "cover_gespeichert": cover_gespeichert,
    }


@router.post("/bulk-anreichern")
async def enrich_all(
    background_tasks: BackgroundTasks,
    _token: str = Depends(verify_token),
):
    """Reichert alle Buecher ohne vollstaendige Metadaten an."""
    books = await db.fetch_all(
        """SELECT id, hash, isbn, title, author FROM books
           WHERE (isbn = '' OR isbn IS NULL)
              OR (author = '' OR author IS NULL)
              OR (publisher = '' OR publisher IS NULL)
           LIMIT 100"""
    )

    if not books:
        return {"zu_bearbeiten": 0}

    async def _enrich_batch():
        for b in books:
            try:
                result = await _lookup_all(b["isbn"], b["title"], b["author"])
                if not result:
                    continue

                # Felder aktualisieren
                field_map = {
                    "titel": "title", "autor": "author", "isbn": "isbn",
                    "verlag": "publisher", "jahr": "year",
                    "sprache": "language", "beschreibung": "description",
                    "seiten": "page_count",
                }
                updates = {}
                for key, value in result.items():
                    db_key = field_map.get(key)
                    if db_key and value:
                        updates[db_key] = value
                if updates:
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    values = list(updates.values()) + [b["id"]]
                    await db.execute(
                        f"UPDATE books SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                        tuple(values),
                    )

                # Kategorien
                kategorien = result.get("kategorien", [])
                if kategorien:
                    cat_ids = await _ensure_categories(kategorien)
                    await _assign_categories(b["id"], cat_ids)

                # Cover
                cover_url = result.get("cover_url", "")
                if cover_url:
                    if "google" in cover_url:
                        cover_data = await googlebooks.download_cover(cover_url)
                    else:
                        cover_data = await openlibrary.download_cover(cover_url)
                    if cover_data:
                        save_cover(b["hash"], cover_data)
                        await db.execute(
                            "UPDATE books SET cover_path = 'cover.jpg', updated_at = datetime('now') WHERE id = ?",
                            (b["id"],),
                        )

                await db.commit()

            except Exception as e:
                logger.warning("Anreicherung fehlgeschlagen fuer Buch %d: %s", b["id"], e)

    background_tasks.add_task(_enrich_batch)
    return {"zu_bearbeiten": len(books), "status": "gestartet"}


async def _lookup_all(isbn: str, title: str, author: str) -> dict | None:
    """Sucht in allen Quellen: Google Books zuerst, dann Open Library."""
    result = None

    # Google Books
    if isbn:
        result = await googlebooks.lookup_isbn(isbn)
    if not result and title:
        query = f"{title} {author}".strip()
        results = await googlebooks.search_books(query, limit=1)
        if results:
            result = results[0]

    # Open Library Fallback
    if not result:
        if isbn:
            result = await openlibrary.lookup_isbn(isbn)
        if not result and title:
            query = f"{title} {author}".strip()
            results = await openlibrary.search_books(query, limit=1)
            if results:
                result = results[0]

    return result


@router.get("/verbindungsstatus")
async def connection_status(_token: str = Depends(verify_token)):
    """Prueft die Verbindung zu den Metadaten-Diensten."""
    gb = await googlebooks.check_connection()
    ol = await openlibrary.check_connection()
    return {
        "google_books": gb,
        "open_library": ol,
    }
