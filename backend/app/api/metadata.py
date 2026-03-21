"""API-Endpunkte für Metadatenanreicherung."""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.core.auth import verify_token
from backend.app.core.database import db
from backend.app.services import googlebooks, openlibrary, wikipedia
from backend.app.services.storage import save_cover, load_fulltext

logger = logging.getLogger("buecherfreunde.api.metadata")

router = APIRouter(prefix="/api/metadata", tags=["Metadaten"])


def _slugify(text: str) -> str:
    """Erzeugt einen URL-freundlichen Slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


def _parse_author_string(author_str: str) -> list[str]:
    """Zerlegt einen Autoren-String intelligent in einzelne Autorennamen.

    Erkennt verschiedene Formate:
    - "Vorname Nachname, Vorname Nachname" (Komma-getrennt, mehrere Autoren)
    - "Nachname, Vorname" (einzelner Autor im Nachname-Vorname-Format)
    - "Autor1; Autor2" (Semikolon-getrennt)
    - "Autor1 und Autor2" / "Autor1 & Autor2"

    Heuristik: Wenn ein Komma nur EIN Wort links hat (Nachname) und EIN Wort rechts (Vorname),
    ist es wahrscheinlich "Nachname, Vorname". Wenn links und rechts je 2+ Worte stehen,
    sind es vermutlich separate Autoren.
    """
    if not author_str or not author_str.strip():
        return []

    # Semikolon ist eindeutig ein Separator
    if ";" in author_str:
        parts = [p.strip() for p in author_str.split(";")]
        result = []
        for part in parts:
            result.extend(_parse_author_string(part))
        return result

    # " und " / " & " sind eindeutig Separatoren
    parts = re.split(r'\s+und\s+|\s+&\s+', author_str)
    if len(parts) > 1:
        result = []
        for part in parts:
            result.extend(_parse_author_string(part))
        return result

    # Komma-Logik
    if "," in author_str:
        comma_parts = [p.strip() for p in author_str.split(",")]

        # Ein Komma mit genau 2 Teilen: Prüfe ob "Nachname, Vorname" oder "Autor1, Autor2"
        if len(comma_parts) == 2:
            left = comma_parts[0].strip()
            right = comma_parts[1].strip()
            left_words = left.split()
            right_words = right.split()

            # "Nachname, Vorname"-Heuristik:
            # - links 1 Wort (oder 2 mit Kleinwort-Präfix wie "le", "de", "von")
            # - rechts 1-2 Worte (Vorname + ggf. zweiter Vorname)
            left_is_surname = (
                len(left_words) == 1 or
                (len(left_words) == 2 and left_words[0].lower() in (
                    "le", "la", "de", "del", "di", "du", "von", "van", "der", "den",
                    "el", "al", "bin", "ibn", "mc", "mac", "st", "saint", "o'",
                ))
            )
            right_is_firstname = len(right_words) <= 2

            if left_is_surname and right_is_firstname:
                # "Nachname, Vorname" oder "le Carré, John" -> umkehren
                return [f"{right} {left}"]
            else:
                # Wahrscheinlich zwei separate Autoren
                return [left, right]

        # Mehrere Kommas: Prüfe ob "Nachname1, Vorname1, Nachname2, Vorname2" oder separate Autoren
        # Bei mehr als 2 Komma-Teilen: Wenn jeder Teil ein einzelnes Wort hat, ist es vermutlich
        # abwechselnd Nachname/Vorname. Sonst sind es separate Autoren.
        single_word_parts = all(len(p.split()) == 1 for p in comma_parts)
        if single_word_parts and len(comma_parts) % 2 == 0:
            # Paare bilden: "Nachname1, Vorname1, Nachname2, Vorname2"
            result = []
            for i in range(0, len(comma_parts), 2):
                result.append(f"{comma_parts[i+1]} {comma_parts[i]}")
            return result
        else:
            # Separate Autoren
            return [p for p in comma_parts if p]

    # Kein Separator -> einzelner Autor
    return [author_str.strip()]


async def _sync_book_authors(book_id: int, author_str: str) -> None:
    """Synchronisiert die authors/book_authors-Tabelle mit dem Autoren-String eines Buchs.

    Entfernt alte Verknüpfungen, parst den String und erstellt neue.
    """
    if not author_str:
        return

    namen = _parse_author_string(author_str)

    # Alte Verknüpfungen entfernen
    await db.execute("DELETE FROM book_authors WHERE book_id = ?", (book_id,))

    for i, name in enumerate(namen):
        name = name.strip()
        if not name or len(name) < 2:
            continue

        slug = _slugify(name)
        if not slug:
            continue

        existing = await db.fetch_one("SELECT id FROM authors WHERE slug = ?", (slug,))
        if existing:
            author_id = existing["id"]
        else:
            cursor = await db.execute(
                "INSERT INTO authors (name, slug) VALUES (?, ?)",
                (name, slug),
            )
            author_id = cursor.lastrowid

        await db.execute(
            "INSERT OR IGNORE INTO book_authors (book_id, author_id, sort_order) VALUES (?, ?, ?)",
            (book_id, author_id, i),
        )


async def _ensure_categories(names: list[str]) -> list[int]:
    """Stellt sicher, dass Kategorien existieren und gibt deren IDs zurück.

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

    Ohne Quellangabe: Google Books zuerst, dann Open Library, dann Wikipedia.
    Mit quelle=google_books/open_library/wikipedia: nur diese Quelle.
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
    suche_wiki = quelle in (None, "wikipedia")

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

    # 3. Wikipedia/Wikidata
    if not result and suche_wiki:
        if book["isbn"]:
            result = await wikipedia.lookup_isbn(book["isbn"])
        if result:
            quelle_name = "wikipedia"

    if not result:
        quelle_labels = {
            "google_books": "Google Books",
            "open_library": "Open Library",
            "wikipedia": "Wikipedia/Wikidata",
        }
        quelle_text = quelle_labels.get(quelle, "allen Quellen")
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
    """Übernimmt vorgeschlagene Metadaten für ein Buch.

    Aktualisiert Buchfelder, erstellt/verknüpft Kategorien,
    lädt Cover-Bild herunter und persistiert es.
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

    # Autoren-Tabelle synchronisieren
    if "author" in updates:
        await _sync_book_authors(book_id, updates["author"])

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



@router.get("/buch/{book_id}/volltext")
async def get_fulltext(
    book_id: int,
    seite_von: int = Query(1, ge=1, description="Startseite (1-basiert)"),
    seite_bis: int = Query(5, ge=1, description="Endseite (inklusiv)"),
    _token: str = Depends(verify_token),
):
    """Gibt einen Seitenbereich des Volltextes zurück.

    Der Volltext wird anhand von Seitenumbruch-Markern oder gleichmäßig
    in Seiten aufgeteilt.
    """
    book = await db.fetch_one(
        "SELECT hash, page_count FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    fulltext = load_fulltext(book["hash"])
    if not fulltext:
        return {"volltext": "", "seiten_gesamt": 0, "seite_von": 1, "seite_bis": 1}

    # Seiten aufteilen: Formfeed (\f) als Seitenumbruch oder gleichmäßig
    if "\f" in fulltext:
        seiten = fulltext.split("\f")
    else:
        # Gleichmäßig aufteilen basierend auf Seitenanzahl aus DB
        total_pages = book["page_count"] or 1
        chars_per_page = max(len(fulltext) // total_pages, 500)
        seiten = []
        for i in range(0, len(fulltext), chars_per_page):
            seiten.append(fulltext[i:i + chars_per_page])

    seiten_gesamt = len(seiten)
    # Bereich begrenzen
    von = max(1, min(seite_von, seiten_gesamt))
    bis = max(von, min(seite_bis, seiten_gesamt))

    ausschnitt = "\n".join(seiten[von - 1:bis])

    return {
        "volltext": ausschnitt,
        "seiten_gesamt": seiten_gesamt,
        "seite_von": von,
        "seite_bis": bis,
    }


@router.get("/verbindungsstatus")
async def connection_status(_token: str = Depends(verify_token)):
    """Prüft die Verbindung zu den Metadaten-Diensten."""
    gb = await googlebooks.check_connection()
    ol = await openlibrary.check_connection()
    wiki = await wikipedia.check_connection()
    return {
        "google_books": gb,
        "open_library": ol,
        "wikipedia": wiki,
    }
