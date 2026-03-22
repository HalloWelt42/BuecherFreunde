"""API-Endpunkte für Bücher."""

import logging
import math
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.app.core.auth import verify_token, verify_token_query
from backend.app.core.database import db
from backend.app.models.book import BookListResponse, BookListItem, BookResponse, BookUpdate
from backend.app.services.storage import get_original_file, get_sidecar_path, save_cover, save_fulltext

router = APIRouter(prefix="/api/books", tags=["Bücher"])

_IMAGE_MAGIC = (
    b"\xff\xd8\xff",      # JPEG
    b"\x89PNG",           # PNG
    b"GIF8",             # GIF
    b"RIFF",             # WebP
)

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _extract_cover_from_zip(epub_path: Path, logger) -> bytes | None:
    """Extrahiert das Cover direkt per zipfile -- Fallback wenn ebooklib scheitert."""
    import zipfile

    try:
        with zipfile.ZipFile(epub_path) as zf:
            namen = zf.namelist()

            # 1. Datei mit "cover" im Namen und Bild-Endung
            for name in namen:
                lower = name.lower()
                if "cover" in lower and any(lower.endswith(ext) for ext in _IMAGE_EXTENSIONS):
                    data = zf.read(name)
                    if data and len(data) > 500:
                        logger.info("ZIP-Fallback: Cover gefunden in %s (%d Bytes)", name, len(data))
                        return data

            # 2. Groesstes Bild im Archiv
            groesstes = None
            groesste_bytes = 0
            groesster_name = ""
            for name in namen:
                lower = name.lower()
                if any(lower.endswith(ext) for ext in _IMAGE_EXTENSIONS):
                    data = zf.read(name)
                    if data and len(data) > groesste_bytes:
                        groesste_bytes = len(data)
                        groesstes = data
                        groesster_name = name

            if groesstes and groesste_bytes > 1000:
                logger.info("ZIP-Fallback: Groesstes Bild als Cover: %s (%d Bytes)", groesster_name, groesste_bytes)
                return groesstes

            # 3. Beliebige Datei mit Bild-Magic-Bytes
            for name in namen:
                data = zf.read(name)
                if data and len(data) > 1000 and any(data.startswith(m) for m in _IMAGE_MAGIC):
                    logger.info("ZIP-Fallback: Bild per Magic Bytes: %s (%d Bytes)", name, len(data))
                    return data

    except Exception as e:
        logger.warning("ZIP-Fallback fehlgeschlagen: %s", e)

    return None


async def _get_book_categories(book_id: int) -> list[dict]:
    """Lädt Kategorien eines Buches."""
    rows = await db.fetch_all(
        """SELECT c.id, c.name, c.slug FROM categories c
           JOIN book_categories bc ON bc.category_id = c.id
           WHERE bc.book_id = ?""",
        (book_id,),
    )
    return rows


async def _get_book_sammlung(book: dict) -> dict | None:
    """Lädt die Sammlung eines Buches (1:1 über FK)."""
    if not book.get("sammlung_id"):
        return None
    row = await db.fetch_one(
        "SELECT id, name, color FROM collections WHERE id = ?",
        (book["sammlung_id"],),
    )
    if row:
        result = dict(row)
        result["band_nummer"] = book.get("band_nummer", "")
        return result
    return None


async def _get_book_authors(book_id: int) -> list[dict]:
    """Lädt Autoren eines Buches."""
    rows = await db.fetch_all(
        """SELECT a.id, a.name, a.slug, a.photo_path, ba.role
           FROM authors a
           JOIN book_authors ba ON ba.author_id = a.id
           WHERE ba.book_id = ?
           ORDER BY ba.sort_order ASC""",
        (book_id,),
    )
    return rows


async def _get_user_data(book_id: int) -> dict:
    """Lädt Nutzerdaten eines Buches."""
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
    """Reichert ein Buch-Dict mit Relationen an (Einzelbuch-Fallback)."""
    ud = await _get_user_data(book["id"])
    cats = await _get_book_categories(book["id"])
    sammlung = await _get_book_sammlung(book)
    return BookListItem(
        **book,
        is_favorite=bool(ud.get("is_favorite")),
        is_to_read=bool(ud.get("is_to_read")),
        rating=ud.get("rating", 0),
        reading_position=ud.get("reading_position", ""),
        last_read_at=ud.get("last_read_at"),
        categories=cats,
        sammlung=sammlung,
    )


async def _batch_enrich_book_list(rows: list[dict]) -> list[BookListItem]:
    """Reichert eine Liste von Buechern per Batch-Queries an (statt N+1)."""
    if not rows:
        return []

    book_ids = [r["id"] for r in rows]
    ph = ",".join("?" * len(book_ids))

    # 1. user_book_data batch
    ud_rows = await db.fetch_all(
        f"SELECT * FROM user_book_data WHERE book_id IN ({ph})",
        tuple(book_ids),
    )
    ud_map = {r["book_id"]: r for r in ud_rows}

    # 2. Kategorien batch
    cat_rows = await db.fetch_all(
        f"""SELECT bc.book_id, c.id, c.name, c.slug
            FROM book_categories bc
            JOIN categories c ON c.id = bc.category_id
            WHERE bc.book_id IN ({ph})""",
        tuple(book_ids),
    )
    cat_map: dict[int, list] = {}
    for r in cat_rows:
        cat_map.setdefault(r["book_id"], []).append(
            {"id": r["id"], "name": r["name"], "slug": r["slug"]}
        )

    # 3. Sammlungen batch (nur fuer Buecher mit sammlung_id)
    samml_ids = list({r["sammlung_id"] for r in rows if r.get("sammlung_id")})
    samml_map: dict[int, dict] = {}
    if samml_ids:
        sph = ",".join("?" * len(samml_ids))
        samml_rows = await db.fetch_all(
            f"SELECT id, name, color FROM collections WHERE id IN ({sph})",
            tuple(samml_ids),
        )
        samml_map = {r["id"]: dict(r) for r in samml_rows}

    # Zusammenbauen
    result = []
    for book in rows:
        bid = book["id"]
        ud = ud_map.get(bid, {})
        cats = cat_map.get(bid, [])
        sammlung = None
        if book.get("sammlung_id") and book["sammlung_id"] in samml_map:
            sammlung = {**samml_map[book["sammlung_id"]], "band_nummer": book.get("band_nummer", "")}

        result.append(BookListItem(
            **book,
            is_favorite=bool(ud.get("is_favorite")),
            is_to_read=bool(ud.get("is_to_read")),
            rating=ud.get("rating", 0),
            reading_position=ud.get("reading_position", ""),
            last_read_at=ud.get("last_read_at"),
            categories=cats,
            sammlung=sammlung,
        ))
    return result


@router.get("", response_model=BookListResponse)
async def list_books(
    _token: str = Depends(verify_token),
    seite: int = Query(1, ge=1, description="Seitennummer"),
    pro_seite: int = Query(24, ge=1, le=100, description="Einträge pro Seite"),
    kategorie: str | None = Query(None, description="Kategorie-ID(s), kommagetrennt"),
    sammlung: int | None = Query(None, description="Sammlungs-ID Filter"),
    typ: str | None = Query(None, description="Typ-Filter (heft, katalog, broschuere)"),
    favorit: bool | None = Query(None, description="Nur Favoriten"),
    zu_lesen: bool | None = Query(None, description="Nur Zum-Lesen"),
    bewertung_min: int | None = Query(None, ge=0, le=5, description="Mindestbewertung"),
    format: str | None = Query(None, description="Dateiformat (.pdf, .epub, ...)"),
    gelesen: bool | None = Query(None, description="Nur gelesene Bücher"),
    hat_isbn: bool | None = Query(None, description="True=mit ISBN, False=ohne ISBN"),
    weiterlesen: bool | None = Query(None, description="Bücher mit Leseposition"),
    hat_labels: bool | None = Query(None, description="Bücher mit Labels"),
    hat_highlights: bool | None = Query(None, description="Bücher mit Textmarkierungen"),
    autor: str | None = Query(None, description="Autor-Filter (exakter Match oder LIKE)"),
    verlag: str | None = Query(None, description="Verlag-Filter (exakter Match oder LIKE)"),
    jahr_von: int | None = Query(None, description="Erscheinungsjahr ab"),
    jahr_bis: int | None = Query(None, description="Erscheinungsjahr bis"),
    sortierung: str = Query("titel", description="Sortierung: titel, autor, datum, bewertung, größe, jahr, verlag"),
    richtung: str = Query("asc", description="Sortierrichtung: asc, desc"),
):
    """Listet Bücher paginiert und filterbar auf."""
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

    if sammlung is not None:
        conditions.append("b.sammlung_id = ?")
        params.append(sammlung)

    if typ is not None and typ.strip():
        conditions.append("b.typ = ?")
        params.append(typ.strip())

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

    if hat_labels is not None:
        conditions.append("b.id IN (SELECT DISTINCT book_id FROM book_highlights WHERE label_name != '')")

    if hat_highlights is not None:
        conditions.append("b.id IN (SELECT DISTINCT book_id FROM book_highlights)")

    if hat_isbn is not None:
        if hat_isbn:
            conditions.append("b.isbn IS NOT NULL AND b.isbn != ''")
        else:
            conditions.append("(b.isbn IS NULL OR b.isbn = '')")

    if autor is not None and autor.strip():
        conditions.append("b.author LIKE ?")
        params.append(f"%{autor.strip()}%")

    if verlag is not None and verlag.strip():
        conditions.append("b.publisher LIKE ?")
        params.append(f"%{verlag.strip()}%")

    if jahr_von is not None:
        conditions.append("b.year >= ?")
        params.append(jahr_von)

    if jahr_bis is not None:
        conditions.append("b.year <= ?")
        params.append(jahr_bis)

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
        "jahr": "b.year",
        "verlag": "b.publisher",
        "bewertung": "COALESCE(ud_sort.rating, 0)",
    }
    sort_col = sort_map.get(sortierung, "b.title")
    sort_dir = "DESC" if richtung.lower() == "desc" else "ASC"
    needs_ud_join = sortierung == "bewertung"

    # Gesamt zählen
    count_sql = f"SELECT COUNT(*) as total FROM books b WHERE {where}"
    count_row = await db.fetch_one(count_sql, tuple(params))
    gesamt = count_row["total"] if count_row else 0

    # Seite abfragen
    offset = (seite - 1) * pro_seite
    ud_join = "LEFT JOIN user_book_data ud_sort ON ud_sort.book_id = b.id" if needs_ud_join else ""
    select_sql = f"""
        SELECT b.id, b.hash, b.title, b.author, b.publisher, b.file_format,
               b.file_size, b.cover_path, b.page_count, b.year, b.isbn,
               b.typ, b.sammlung_id, b.band_nummer, b.created_at, b.updated_at
        FROM books b
        {ud_join}
        WHERE {where}
        ORDER BY {sort_col} {sort_dir}
        LIMIT ? OFFSET ?
    """
    rows = await db.fetch_all(select_sql, tuple(params) + (pro_seite, offset))

    buecher = await _batch_enrich_book_list(rows)

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
    """Gibt die zuletzt gelesenen Bücher zurück."""
    sql = """
        SELECT b.id, b.hash, b.title, b.author, b.publisher, b.file_format,
               b.file_size, b.cover_path, b.page_count, b.year, b.isbn,
               b.typ, b.sammlung_id, b.band_nummer, b.created_at, b.updated_at
        FROM books b
        JOIN user_book_data ud ON ud.book_id = b.id
        WHERE ud.last_read_at IS NOT NULL
        ORDER BY ud.last_read_at DESC
        LIMIT ?
    """
    rows = await db.fetch_all(sql, (limit,))
    return await _batch_enrich_book_list(rows)


@router.get("/{book_id}/aehnliche")
async def similar_books(
    book_id: int,
    _token: str = Depends(verify_token),
    limit: int = Query(6, ge=1, le=20),
):
    """Gibt aehnliche Buecher zurueck (gleicher Autor, gleiche Kategorie)."""
    book = await db.fetch_one(
        "SELECT id, author FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    result = {"vom_autor": [], "in_kategorie": []}

    # Vom selben Autor (ueber authors-Tabelle oder author-Feld)
    author_ids = await db.fetch_all(
        "SELECT author_id FROM book_authors WHERE book_id = ?", (book_id,)
    )
    if author_ids:
        placeholders = ",".join("?" for _ in author_ids)
        ids = [a["author_id"] for a in author_ids]
        rows = await db.fetch_all(
            f"""SELECT DISTINCT b.id, b.hash, b.title, b.author, b.publisher,
                       b.file_format, b.file_size, b.cover_path, b.page_count,
                       b.year, b.isbn, b.typ, b.sammlung_id, b.band_nummer,
                       b.created_at, b.updated_at
                FROM books b
                JOIN book_authors ba ON ba.book_id = b.id
                WHERE ba.author_id IN ({placeholders}) AND b.id != ?
                ORDER BY b.title LIMIT ?""",
            (*ids, book_id, limit),
        )
        result["vom_autor"] = await _batch_enrich_book_list(rows)
    elif book["author"]:
        rows = await db.fetch_all(
            """SELECT id, hash, title, author, publisher, file_format,
                      file_size, cover_path, page_count, year, isbn,
                      typ, sammlung_id, band_nummer, created_at, updated_at
               FROM books WHERE author = ? AND id != ?
               ORDER BY title LIMIT ?""",
            (book["author"], book_id, limit),
        )
        result["vom_autor"] = await _batch_enrich_book_list(rows)

    # In derselben Kategorie
    cat_ids = await db.fetch_all(
        "SELECT category_id FROM book_categories WHERE book_id = ?", (book_id,)
    )
    if cat_ids:
        # Spezial-Kategorien wie "Ungeordnet" ausschliessen
        filtered = []
        for c in cat_ids:
            is_special = await db.fetch_one(
                "SELECT spezial FROM categories WHERE id = ?", (c["category_id"],)
            )
            if not is_special or not is_special.get("spezial"):
                filtered.append(c["category_id"])

        if filtered:
            already = {book_id} | {b.id for b in result["vom_autor"]}
            placeholders = ",".join("?" for _ in filtered)
            exclude_ph = ",".join("?" for _ in already)
            rows = await db.fetch_all(
                f"""SELECT DISTINCT b.id, b.hash, b.title, b.author, b.publisher,
                           b.file_format, b.file_size, b.cover_path, b.page_count,
                           b.year, b.isbn, b.typ, b.sammlung_id, b.band_nummer,
                           b.created_at, b.updated_at
                    FROM books b
                    JOIN book_categories bc ON bc.book_id = b.id
                    WHERE bc.category_id IN ({placeholders}) AND b.id NOT IN ({exclude_ph})
                    ORDER BY b.title LIMIT ?""",
                (*filtered, *already, limit),
            )
            result["in_kategorie"] = await _batch_enrich_book_list(rows)

    return result


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: int, _token: str = Depends(verify_token)):
    """Gibt die vollständigen Details eines Buches zurück."""
    row = await db.fetch_one("SELECT * FROM books WHERE id = ?", (book_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    ud = await _get_user_data(book_id)
    cats = await _get_book_categories(book_id)
    sammlung = await _get_book_sammlung(row)
    authors = await _get_book_authors(book_id)

    return BookResponse(
        **row,
        is_favorite=bool(ud.get("is_favorite")),
        is_to_read=bool(ud.get("is_to_read")),
        rating=ud.get("rating", 0),
        reading_position=ud.get("reading_position", ""),
        last_read_at=ud.get("last_read_at"),
        categories=cats,
        sammlung=sammlung,
        authors=authors,
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
        f"UPDATE books SET {set_clause}, manuell_bearbeitet = 1, updated_at = datetime('now') WHERE id = ?",
        tuple(values),
    )

    # FTS aktualisieren falls Titel oder Autor geändert
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
    datei_loeschen: bool = Query(False, description="Auch die Datei im Speicher löschen"),
    _token: str = Depends(verify_token),
):
    """Löscht ein Buch aus der Datenbank."""
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
    """Massenbearbeitung für mehrere Bücher."""
    book_ids: list[int]
    aktion: str  # "loeschen", "kategorie_zuweisen", "sammlung_zuweisen", "typ_setzen", "favorit", "zu_lesen"
    wert: str | int | None = None  # z.B. Kategorie-ID, Tag-ID, true/false


@router.post("/bulk")
async def bulk_action(
    action: BulkAction,
    _token: str = Depends(verify_token),
):
    """Führt eine Massenbearbeitung für mehrere Bücher durch."""
    if not action.book_ids:
        raise HTTPException(status_code=400, detail="Keine Bücher ausgewählt")

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
                "INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'manuell')",
                (bid, kat_id),
            )
            betroffen += 1
        await db.commit()

    elif action.aktion == "sammlung_zuweisen":
        if action.wert is None:
            raise HTTPException(status_code=400, detail="Sammlungs-ID fehlt")
        samml_id = int(action.wert)
        for bid in action.book_ids:
            await db.execute(
                "UPDATE books SET sammlung_id = ? WHERE id = ?",
                (samml_id, bid),
            )
            betroffen += 1
        await db.commit()

    elif action.aktion == "typ_setzen":
        typ_wert = str(action.wert) if action.wert else ""
        for bid in action.book_ids:
            await db.execute(
                "UPDATE books SET typ = ? WHERE id = ?",
                (typ_wert, bid),
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


@router.delete("/kategorie/{category_id}/buecher")
async def delete_books_by_category(
    category_id: int,
    datei_loeschen: bool = Query(False, description="Auch Dateien im Speicher löschen"),
    _token: str = Depends(verify_token),
):
    """Löscht alle Bücher einer Kategorie.

    Entfernt die Bücher aus der DB. Optional werden auch die
    Dateien im Hash-Speicher gelöscht.
    """
    # Bücher in dieser Kategorie finden
    rows = await db.fetch_all(
        "SELECT b.id, b.hash FROM books b JOIN book_categories bc ON bc.book_id = b.id WHERE bc.category_id = ?",
        (category_id,),
    )
    if not rows:
        return {"geloescht": 0, "kategorie_id": category_id}

    if datei_loeschen:
        from backend.app.services.storage import delete_stored_file

    for row in rows:
        await db.execute("DELETE FROM books WHERE id = ?", (row["id"],))
        if datei_loeschen:
            try:
                delete_stored_file(row["hash"])
            except Exception:
                pass
    await db.commit()

    return {"geloescht": len(rows), "kategorie_id": category_id}


@router.delete("/alle")
async def delete_all_books(
    datei_loeschen: bool = Query(False, description="Auch Dateien im Speicher löschen"),
    bestaetigung: str = Query(..., description="Muss 'ALLE LOESCHEN' sein"),
    _token: str = Depends(verify_token),
):
    """Löscht ALLE Bücher aus der Datenbank.

    Erfordert explizite Bestätigung mit bestaetigung='ALLE LOESCHEN'.
    """
    if bestaetigung != "ALLE LOESCHEN":
        raise HTTPException(
            status_code=400,
            detail="Sicherheitsbestätigung fehlt. Sende bestaetigung='ALLE LOESCHEN'",
        )

    if datei_loeschen:
        from backend.app.services.storage import delete_stored_file

        rows = await db.fetch_all("SELECT hash FROM books")
        for row in rows:
            try:
                delete_stored_file(row["hash"])
            except Exception:
                pass

    result = await db.execute("DELETE FROM books")
    await db.execute("DELETE FROM book_categories")
    await db.execute("DELETE FROM book_authors")
    await db.execute("DELETE FROM user_book_data")
    await db.execute("DELETE FROM book_highlights")
    await db.execute("DELETE FROM book_labels")
    await db.execute("DELETE FROM book_notes")
    await db.execute("DELETE FROM import_tasks")
    await db.commit()

    # FTS-Index neu aufbauen
    try:
        await db.execute("INSERT INTO books_fts(books_fts) VALUES('rebuild')")
        await db.commit()
    except Exception:
        pass

    return {"geloescht": True, "hinweis": "Alle Bücher und zugehörige Daten gelöscht"}


@router.get("/{book_id}/cover")
async def get_cover(book_id: int, _token: str = Depends(verify_token_query)):
    """Gibt das Cover-Bild eines Buches zurück."""
    book = await db.fetch_one(
        "SELECT hash, cover_path FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    cover_path = get_sidecar_path(book["hash"], "cover.jpg")
    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="Kein Cover vorhanden")

    return FileResponse(cover_path, media_type="image/jpeg")


@router.post("/{book_id}/cover/neu-extrahieren")
async def re_extract_cover(book_id: int, _token: str = Depends(verify_token)):
    """Extrahiert das Cover neu aus der Buchdatei und überschreibt das bestehende."""
    import logging
    logger = logging.getLogger("buecherfreunde.api.books")

    book = await db.fetch_one(
        "SELECT id, hash, file_format FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    original = get_original_file(book["hash"])
    if not original or not original.exists():
        raise HTTPException(status_code=404, detail="Buchdatei nicht gefunden")

    fmt = book["file_format"].lower()
    cover_data = None

    if fmt == "pdf":
        from backend.app.services.processors.pdf_processor import PdfProcessor
        import fitz
        try:
            doc = fitz.open(str(original))
            proc = PdfProcessor()
            cover_data = proc._extract_cover(doc)
            doc.close()
        except Exception as e:
            logger.warning("PDF Cover-Extraktion fehlgeschlagen: %s", e)

    elif fmt == "epub":
        from backend.app.services.processors.epub_processor import EpubProcessor
        import ebooklib
        import ebooklib.epub
        try:
            epub_book = ebooklib.epub.read_epub(str(original), options={"ignore_ncx": True})
            proc = EpubProcessor()
            cover_data = proc._extract_cover(epub_book)
        except Exception as e:
            logger.warning("ebooklib fehlgeschlagen, versuche ZIP-Fallback: %s", e)

        # Fallback: Direkt per zipfile das Cover suchen (fuer kaputte EPUBs)
        if not cover_data:
            cover_data = _extract_cover_from_zip(original, logger)

    if not cover_data:
        raise HTTPException(status_code=422, detail="Kein eingebettetes Cover in der Datei gefunden")

    save_cover(book["hash"], cover_data)
    await db.execute(
        "UPDATE books SET cover_path = 'cover.jpg', updated_at = datetime('now') WHERE id = ?",
        (book_id,),
    )
    await db.commit()

    return {"gespeichert": True, "groesse": len(cover_data)}


@router.get("/{book_id}/file")
async def get_file(book_id: int, _token: str = Depends(verify_token_query)):
    """Streamt die Buchdatei (mit Range-Request-Unterstützung)."""
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

    Liest den Volltext und extrahiert alle gültigen ISBNs.
    Liefert für jede gefundene ISBN beide Varianten (ISBN-10/13).
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
    text = ""
    if fulltext_path.exists():
        text = fulltext_path.read_text(encoding="utf-8", errors="ignore")

    # Fallback: Volltext direkt aus EPUB extrahieren wenn Sidecar leer/fehlt
    if not text.strip():
        original = get_original_file(book["hash"])
        if original and original.exists() and original.suffix.lower() == ".epub":
            import zipfile
            try:
                with zipfile.ZipFile(original) as zf:
                    parts = []
                    html_files = sorted([n for n in zf.namelist() if n.lower().endswith((".html", ".xhtml", ".htm"))])
                    for html_name in html_files:
                        try:
                            from bs4 import BeautifulSoup
                            html_content = zf.read(html_name).decode("utf-8", errors="ignore")
                            soup = BeautifulSoup(html_content, "html.parser")
                            t = soup.get_text(separator="\n", strip=True)
                            if t:
                                parts.append(t)
                        except Exception:
                            continue
                    if parts:
                        text = "\n\n".join(parts)
                        # Volltext auch speichern fuer naechstes Mal
                        from backend.app.services.storage import save_fulltext
                        save_fulltext(book["hash"], text)
            except Exception:
                pass

    if not text.strip():
        return {"gefunden": [], "aktuell": book["isbn"] or ""}
    # Gesamten Text durchsuchen - ISBN kann an beliebiger Stelle stehen
    raw_isbns = extract_isbns_from_text(text)

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


@router.post("/rescan")
async def rescan_books(
    typen: str = Query("cover,isbn", description="Kommagetrennt: cover,isbn,metadaten,volltext"),
    kategorie: int | None = Query(None, description="Nur Buecher dieser Kategorie (0=ohne Kategorie)"),
    manuell_einschliessen: bool = Query(False, description="Auch manuell bearbeitete Buecher scannen"),
    _token: str = Depends(verify_token),
):
    """Startet einen selektiven Rescan."""
    from backend.app.services import rescan_service
    typ_liste = [t.strip() for t in typen.split(",") if t.strip()]
    return await rescan_service.starte_rescan(typ_liste, kategorie, manuell_einschliessen)


@router.get("/rescan/status")
async def rescan_get_status(_token: str = Depends(verify_token)):
    """Gibt den aktuellen Rescan-Status zurück."""
    from backend.app.services import rescan_service
    return rescan_service.status


@router.post("/rescan/abbrechen")
async def rescan_cancel(_token: str = Depends(verify_token)):
    """Bricht den laufenden Rescan ab."""
    from backend.app.services import rescan_service
    return rescan_service.abbrechen()


@router.get("/rescan/vorschau")
async def rescan_vorschau(
    typen: str = Query("cover,isbn", description="Kommagetrennt: cover,isbn,metadaten,volltext"),
    kategorie: int | None = Query(None, description="Nur Buecher dieser Kategorie"),
    manuell_einschliessen: bool = Query(False),
    _token: str = Depends(verify_token),
):
    """Vorschau: wie viele Buecher wuerden gescannt werden."""
    from backend.app.services import rescan_service
    typ_liste = [t.strip() for t in typen.split(",") if t.strip()]
    return await rescan_service.vorschau(typ_liste, kategorie, manuell_einschliessen)


@router.get("/rescan/kategorien")
async def rescan_kategorien(
    typen: str = Query("cover,isbn", description="Kommagetrennt: cover,isbn,metadaten,volltext"),
    manuell_einschliessen: bool = Query(False),
    _token: str = Depends(verify_token),
):
    """Zeigt betroffene Buecher pro Kategorie."""
    from backend.app.services import rescan_service
    typ_liste = [t.strip() for t in typen.split(",") if t.strip()]
    return await rescan_service.vorschau_kategorien(typ_liste, manuell_einschliessen)


@router.get("/{book_id}/volltext-suche")
async def fulltext_search_book(
    book_id: int,
    q: str = Query(..., min_length=1, description="Suchbegriff"),
    limit: int = Query(500, ge=1, le=5000),
    ganzes_wort: bool = Query(False, description="Nur ganze Woerter"),
    gross_klein: bool = Query(False, description="Gross-/Kleinschreibung beachten"),
    regex: bool = Query(False, description="Regulaerer Ausdruck"),
    _token: str = Depends(verify_token),
):
    """Durchsucht den Volltext eines einzelnen Buches.

    Gibt Treffer mit Seitennummer und Kontext-Snippet zurueck.
    """
    import re

    book = await db.fetch_one(
        "SELECT id, hash, page_count FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    fulltext_path = get_sidecar_path(book["hash"], "fulltext.txt")
    if not fulltext_path.exists():
        return {"treffer": [], "gesamt": 0, "suchbegriff": q}

    text = fulltext_path.read_text(encoding="utf-8", errors="ignore")
    if not text:
        return {"treffer": [], "gesamt": 0, "suchbegriff": q}

    # In Seiten aufteilen (gleiche Logik wie Volltext-Endpunkt)
    if "\f" in text:
        seiten = text.split("\f")
    else:
        total_pages = book["page_count"] or 1
        chars_per_page = max(len(text) // total_pages, 500)
        seiten = []
        for i in range(0, len(text), chars_per_page):
            seiten.append(text[i:i + chars_per_page])

    # Suchmuster erstellen
    try:
        if regex:
            pat_str = q
        else:
            pat_str = re.escape(q)
        if ganzes_wort:
            pat_str = r"\b" + pat_str + r"\b"
        flags = 0 if gross_klein else re.IGNORECASE
        pattern = re.compile(pat_str, flags)
    except re.error:
        return {"treffer": [], "gesamt": 0, "suchbegriff": q}

    treffer = []
    gesamt_count = 0
    text_len = len(text)
    seiten_offset = 0  # Zeichenoffset am Anfang der aktuellen Seite
    for seiten_nr, seite in enumerate(seiten, 1):
        for match in pattern.finditer(seite):
            gesamt_count += 1
            if len(treffer) >= limit:
                continue  # Weiterzaehlen aber nicht mehr speichern

            start = max(0, match.start() - 80)
            end = min(len(seite), match.end() + 80)
            kontext = seite[start:end].strip()
            # Treffer hervorheben
            kontext_marked = pattern.sub(
                lambda m: f"<mark>{m.group()}</mark>", kontext
            )
            if start > 0:
                kontext_marked = "..." + kontext_marked
            if end < len(seite):
                kontext_marked = kontext_marked + "..."

            # Globaler Offset und Prozent fuer positionsgenaue Navigation
            global_offset = seiten_offset + match.start()
            prozent = round((global_offset / text_len) * 100, 1) if text_len > 0 else 0

            treffer.append({
                "seite": seiten_nr,
                "kontext": kontext_marked,
                "position": match.start(),
                "prozent": prozent,
            })
        seiten_offset += len(seite) + 1  # +1 fuer \f oder Trennzeichen

    return {
        "treffer": treffer,
        "gesamt": gesamt_count,
        "seiten_gesamt": len(seiten),
        "suchbegriff": q,
    }
