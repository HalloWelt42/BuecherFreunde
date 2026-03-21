"""API-Endpunkte fuer Buecher."""

import math
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from backend.app.core.auth import verify_token, verify_token_query
from backend.app.core.database import db
from backend.app.models.book import BookListResponse, BookListItem, BookResponse, BookUpdate
from backend.app.services.storage import get_original_file, get_sidecar_path

router = APIRouter(prefix="/api/books", tags=["Buecher"])


async def _get_book_categories(book_id: int) -> list[dict]:
    """Laedt Kategorien eines Buches."""
    rows = await db.fetch_all(
        """SELECT c.id, c.name, c.slug FROM categories c
           JOIN book_categories bc ON bc.category_id = c.id
           WHERE bc.book_id = ?""",
        (book_id,),
    )
    return rows


async def _get_book_tags(book_id: int) -> list[dict]:
    """Laedt Tags eines Buches."""
    rows = await db.fetch_all(
        """SELECT t.id, t.name, t.slug, t.color FROM tags t
           JOIN book_tags bt ON bt.tag_id = t.id
           WHERE bt.book_id = ?""",
        (book_id,),
    )
    return rows


async def _get_book_collections(book_id: int) -> list[dict]:
    """Laedt Sammlungen eines Buches."""
    rows = await db.fetch_all(
        """SELECT c.id, c.name, c.color FROM collections c
           JOIN book_collections bc ON bc.collection_id = c.id
           WHERE bc.book_id = ?""",
        (book_id,),
    )
    return rows


async def _get_user_data(book_id: int) -> dict:
    """Laedt Nutzerdaten eines Buches."""
    row = await db.fetch_one(
        "SELECT * FROM user_book_data WHERE book_id = ?", (book_id,)
    )
    if row:
        return row
    return {
        "is_favorite": False,
        "is_to_read": False,
        "rating": 0,
        "reading_position": "",
        "last_read_at": None,
    }


async def _enrich_book_list_item(book: dict) -> BookListItem:
    """Reichert ein Buch-Dict mit Relationen an."""
    ud = await _get_user_data(book["id"])
    cats = await _get_book_categories(book["id"])
    tags = await _get_book_tags(book["id"])
    return BookListItem(
        **book,
        is_favorite=bool(ud.get("is_favorite")),
        is_to_read=bool(ud.get("is_to_read")),
        rating=ud.get("rating", 0),
        reading_position=ud.get("reading_position", ""),
        last_read_at=ud.get("last_read_at"),
        categories=cats,
        tags=tags,
    )


@router.get("", response_model=BookListResponse)
async def list_books(
    _token: str = Depends(verify_token),
    seite: int = Query(1, ge=1, description="Seitennummer"),
    pro_seite: int = Query(24, ge=1, le=100, description="Eintraege pro Seite"),
    kategorie: str | None = Query(None, description="Kategorie-ID(s), kommagetrennt"),
    tag: str | None = Query(None, description="Tag-ID(s), kommagetrennt"),
    sammlung: int | None = Query(None, description="Sammlungs-ID Filter"),
    favorit: bool | None = Query(None, description="Nur Favoriten"),
    zu_lesen: bool | None = Query(None, description="Nur Zum-Lesen"),
    bewertung_min: int | None = Query(None, ge=0, le=5, description="Mindestbewertung"),
    format: str | None = Query(None, description="Dateiformat (.pdf, .epub, ...)"),
    gelesen: bool | None = Query(None, description="Nur gelesene Buecher"),
    hat_isbn: bool | None = Query(None, description="True=mit ISBN, False=ohne ISBN"),
    weiterlesen: bool | None = Query(None, description="Buecher mit Leseposition"),
    sortierung: str = Query("titel", description="Sortierung: titel, autor, datum, bewertung, groesse"),
    richtung: str = Query("asc", description="Sortierrichtung: asc, desc"),
):
    """Listet Buecher paginiert und filterbar auf."""
    # Basis-Query aufbauen
    conditions = []
    params: list = []

    if kategorie is not None:
        kat_ids = [int(k) for k in kategorie.split(",") if k.strip().isdigit()]
        if len(kat_ids) == 1:
            conditions.append("b.id IN (SELECT book_id FROM book_categories WHERE category_id = ?)")
            params.append(kat_ids[0])
        elif len(kat_ids) > 1:
            ph = ",".join("?" * len(kat_ids))
            conditions.append(f"b.id IN (SELECT book_id FROM book_categories WHERE category_id IN ({ph}))")
            params.extend(kat_ids)

    if tag is not None:
        tag_ids = [int(t) for t in tag.split(",") if t.strip().isdigit()]
        if len(tag_ids) == 1:
            conditions.append("b.id IN (SELECT book_id FROM book_tags WHERE tag_id = ?)")
            params.append(tag_ids[0])
        elif len(tag_ids) > 1:
            ph = ",".join("?" * len(tag_ids))
            conditions.append(f"b.id IN (SELECT book_id FROM book_tags WHERE tag_id IN ({ph}))")
            params.extend(tag_ids)

    if sammlung is not None:
        conditions.append("b.id IN (SELECT book_id FROM book_collections WHERE collection_id = ?)")
        params.append(sammlung)

    if favorit is not None:
        conditions.append("b.id IN (SELECT book_id FROM user_book_data WHERE is_favorite = 1)")

    if zu_lesen is not None:
        conditions.append("b.id IN (SELECT book_id FROM user_book_data WHERE is_to_read = 1)")

    if bewertung_min is not None:
        conditions.append("b.id IN (SELECT book_id FROM user_book_data WHERE rating >= ?)")
        params.append(bewertung_min)

    if gelesen is not None:
        if gelesen:
            conditions.append("b.id IN (SELECT book_id FROM user_book_data WHERE last_read_at IS NOT NULL)")
        else:
            conditions.append("b.id NOT IN (SELECT book_id FROM user_book_data WHERE last_read_at IS NOT NULL)")

    if weiterlesen is not None:
        conditions.append(
            """b.id IN (SELECT book_id FROM user_book_data
               WHERE reading_position IS NOT NULL AND reading_position != ''
               AND last_read_at IS NOT NULL)"""
        )

    if hat_isbn is not None:
        if hat_isbn:
            conditions.append("b.isbn IS NOT NULL AND b.isbn != ''")
        else:
            conditions.append("(b.isbn IS NULL OR b.isbn = '')")

    if format is not None:
        formats = [f.lower().lstrip(".") for f in format.split(",") if f.strip()]
        if len(formats) == 1:
            conditions.append("b.file_format = ?")
            params.append(formats[0])
        elif len(formats) > 1:
            placeholders = ",".join("?" * len(formats))
            conditions.append(f"b.file_format IN ({placeholders})")
            params.extend(formats)

    where = " AND ".join(conditions) if conditions else "1=1"

    # Sortierung
    sort_map = {
        "titel": "b.title",
        "autor": "b.author",
        "datum": "b.created_at",
        "groesse": "b.file_size",
    }
    sort_col = sort_map.get(sortierung, "b.title")
    sort_dir = "DESC" if richtung.lower() == "desc" else "ASC"

    # Gesamt zaehlen
    count_sql = f"SELECT COUNT(*) as total FROM books b WHERE {where}"
    count_row = await db.fetch_one(count_sql, tuple(params))
    gesamt = count_row["total"] if count_row else 0

    # Seite abfragen
    offset = (seite - 1) * pro_seite
    select_sql = f"""
        SELECT b.id, b.hash, b.title, b.author, b.file_format,
               b.file_size, b.cover_path, b.page_count, b.year, b.isbn, b.created_at
        FROM books b
        WHERE {where}
        ORDER BY {sort_col} {sort_dir}
        LIMIT ? OFFSET ?
    """
    rows = await db.fetch_all(select_sql, tuple(params) + (pro_seite, offset))

    buecher = []
    for row in rows:
        item = await _enrich_book_list_item(row)
        buecher.append(item)

    return BookListResponse(
        buecher=buecher,
        gesamt=gesamt,
        seite=seite,
        pro_seite=pro_seite,
        seiten_gesamt=math.ceil(gesamt / pro_seite) if gesamt > 0 else 0,
    )


@router.get("/recently-read", response_model=list[BookListItem])
async def recently_read(
    _token: str = Depends(verify_token),
    limit: int = Query(10, ge=1, le=50),
):
    """Gibt die zuletzt gelesenen Buecher zurueck."""
    sql = """
        SELECT b.id, b.hash, b.title, b.author, b.file_format,
               b.file_size, b.cover_path, b.page_count, b.year, b.isbn, b.created_at
        FROM books b
        JOIN user_book_data ud ON ud.book_id = b.id
        WHERE ud.last_read_at IS NOT NULL
        ORDER BY ud.last_read_at DESC
        LIMIT ?
    """
    rows = await db.fetch_all(sql, (limit,))
    return [await _enrich_book_list_item(row) for row in rows]


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: int, _token: str = Depends(verify_token)):
    """Gibt die vollstaendigen Details eines Buches zurueck."""
    row = await db.fetch_one("SELECT * FROM books WHERE id = ?", (book_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    ud = await _get_user_data(book_id)
    cats = await _get_book_categories(book_id)
    tags = await _get_book_tags(book_id)
    colls = await _get_book_collections(book_id)

    return BookResponse(
        **row,
        is_favorite=bool(ud.get("is_favorite")),
        is_to_read=bool(ud.get("is_to_read")),
        rating=ud.get("rating", 0),
        reading_position=ud.get("reading_position", ""),
        last_read_at=ud.get("last_read_at"),
        categories=cats,
        tags=tags,
        collections=colls,
    )


@router.patch("/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: int, update: BookUpdate, _token: str = Depends(verify_token)
):
    """Aktualisiert Metadaten eines Buches."""
    existing = await db.fetch_one("SELECT id FROM books WHERE id = ?", (book_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    updates = update.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Keine Felder zum Aktualisieren")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [book_id]
    await db.execute(
        f"UPDATE books SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
        tuple(values),
    )

    # FTS aktualisieren falls Titel oder Autor geaendert
    if "title" in updates or "author" in updates:
        book = await db.fetch_one("SELECT * FROM books WHERE id = ?", (book_id,))
        if book:
            await db.execute(
                "INSERT INTO books_fts(books_fts, rowid, title, author, fts_content) VALUES('delete', ?, ?, ?, ?)",
                (book_id, book["title"], book["author"], book["fts_content"]),
            )
            new_title = updates.get("title", book["title"])
            new_author = updates.get("author", book["author"])
            await db.execute(
                "INSERT INTO books_fts(rowid, title, author, fts_content) VALUES(?, ?, ?, ?)",
                (book_id, new_title, new_author, book["fts_content"]),
            )

    await db.commit()
    return await get_book(book_id)


@router.delete("/{book_id}")
async def delete_book(
    book_id: int,
    datei_loeschen: bool = Query(False, description="Auch die Datei im Speicher loeschen"),
    _token: str = Depends(verify_token),
):
    """Loescht ein Buch aus der Datenbank."""
    book = await db.fetch_one("SELECT hash FROM books WHERE id = ?", (book_id,))
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    await db.execute("DELETE FROM books WHERE id = ?", (book_id,))
    await db.commit()

    if datei_loeschen:
        from backend.app.services.storage import delete_stored_file

        delete_stored_file(book["hash"])

    return {"geloescht": True, "id": book_id}


class BulkAction(BaseModel):
    """Massenbearbeitung fuer mehrere Buecher."""
    book_ids: list[int]
    aktion: str  # "loeschen", "kategorie_zuweisen", "tag_zuweisen", "favorit", "zu_lesen"
    wert: str | int | None = None  # z.B. Kategorie-ID, Tag-ID, true/false


@router.post("/bulk")
async def bulk_action(
    action: BulkAction,
    _token: str = Depends(verify_token),
):
    """Fuehrt eine Massenbearbeitung fuer mehrere Buecher durch."""
    if not action.book_ids:
        raise HTTPException(status_code=400, detail="Keine Buecher ausgewaehlt")

    betroffen = 0

    if action.aktion == "loeschen":
        for bid in action.book_ids:
            await db.execute("DELETE FROM books WHERE id = ?", (bid,))
            betroffen += 1
        await db.commit()

    elif action.aktion == "kategorie_zuweisen":
        if action.wert is None:
            raise HTTPException(status_code=400, detail="Kategorie-ID fehlt")
        kat_id = int(action.wert)
        for bid in action.book_ids:
            await db.execute(
                "INSERT OR IGNORE INTO book_categories (book_id, category_id) VALUES (?, ?)",
                (bid, kat_id),
            )
            betroffen += 1
        await db.commit()

    elif action.aktion == "tag_zuweisen":
        if action.wert is None:
            raise HTTPException(status_code=400, detail="Tag-ID fehlt")
        tag_id = int(action.wert)
        for bid in action.book_ids:
            await db.execute(
                "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?, ?)",
                (bid, tag_id),
            )
            betroffen += 1
        await db.commit()

    elif action.aktion == "favorit":
        fav = 1 if action.wert in (True, "true", 1) else 0
        for bid in action.book_ids:
            await db.execute(
                """INSERT INTO user_book_data (book_id, is_favorite)
                   VALUES (?, ?)
                   ON CONFLICT(book_id) DO UPDATE SET is_favorite = ?""",
                (bid, fav, fav),
            )
            betroffen += 1
        await db.commit()

    elif action.aktion == "zu_lesen":
        val = 1 if action.wert in (True, "true", 1) else 0
        for bid in action.book_ids:
            await db.execute(
                """INSERT INTO user_book_data (book_id, is_to_read)
                   VALUES (?, ?)
                   ON CONFLICT(book_id) DO UPDATE SET is_to_read = ?""",
                (bid, val, val),
            )
            betroffen += 1
        await db.commit()

    else:
        raise HTTPException(status_code=400, detail=f"Unbekannte Aktion: {action.aktion}")

    return {"betroffen": betroffen, "aktion": action.aktion}


@router.get("/{book_id}/cover")
async def get_cover(book_id: int, _token: str = Depends(verify_token_query)):
    """Gibt das Cover-Bild eines Buches zurueck."""
    book = await db.fetch_one(
        "SELECT hash, cover_path FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    cover_path = get_sidecar_path(book["hash"], "cover.jpg")
    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="Kein Cover vorhanden")

    return FileResponse(cover_path, media_type="image/jpeg")


@router.get("/{book_id}/file")
async def get_file(book_id: int, _token: str = Depends(verify_token_query)):
    """Streamt die Buchdatei (mit Range-Request-Unterstuetzung)."""
    book = await db.fetch_one(
        "SELECT hash, file_name, file_format FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    file_path = get_original_file(book["hash"])
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    media_types = {
        "pdf": "application/pdf",
        "epub": "application/epub+zip",
        "mobi": "application/x-mobipocket-ebook",
        "txt": "text/plain; charset=utf-8",
        "md": "text/markdown; charset=utf-8",
    }
    media_type = media_types.get(book["file_format"], "application/octet-stream")

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=book["file_name"],
        headers={"Accept-Ranges": "bytes"},
    )


@router.post("/{book_id}/isbn-scan")
async def isbn_scan(book_id: int, _token: str = Depends(verify_token)):
    """Scannt ein Buch erneut nach ISBNs.

    Liest den Volltext und extrahiert alle gueltigen ISBNs.
    Liefert fuer jede gefundene ISBN beide Varianten (ISBN-10/13).
    """
    import isbnlib

    from backend.app.services.isbn_extractor import extract_isbns_from_text

    book = await db.fetch_one(
        "SELECT id, hash, isbn FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    # Volltext laden
    fulltext_path = get_sidecar_path(book["hash"], "fulltext.txt")
    if not fulltext_path.exists():
        return {"gefunden": [], "aktuell": book["isbn"] or ""}

    text = fulltext_path.read_text(encoding="utf-8", errors="ignore")
    # Erste und letzte 30.000 Zeichen durchsuchen
    scan_text = text[:30000]
    if len(text) > 30000:
        scan_text += "\n" + text[-30000:]

    raw_isbns = extract_isbns_from_text(scan_text)

    # Alle Varianten mit isbnlib berechnen
    ergebnisse = []
    gesehen = set()
    for isbn in raw_isbns:
        canonical = isbnlib.canonical(isbn)
        if not canonical or canonical in gesehen:
            continue
        gesehen.add(canonical)

        eintrag = {"original": canonical, "varianten": []}

        # ISBN-13 Variante
        isbn13 = isbnlib.to_isbn13(canonical) if len(canonical) == 10 else canonical
        if isbn13 and isbnlib.is_isbn13(isbn13):
            eintrag["isbn13"] = isbn13
            if isbn13 not in gesehen:
                gesehen.add(isbn13)

        # ISBN-10 Variante
        isbn10 = isbnlib.to_isbn10(canonical) if len(canonical) == 13 else canonical
        if isbn10 and isbnlib.is_isbn10(isbn10):
            eintrag["isbn10"] = isbn10
            if isbn10 not in gesehen:
                gesehen.add(isbn10)

        # Formatiert
        try:
            eintrag["formatiert"] = isbnlib.mask(canonical)
        except Exception:
            eintrag["formatiert"] = canonical

        ergebnisse.append(eintrag)

    return {
        "gefunden": ergebnisse,
        "aktuell": book["isbn"] or "",
        "anzahl": len(ergebnisse),
    }
