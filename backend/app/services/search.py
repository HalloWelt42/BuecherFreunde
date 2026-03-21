"""FTS5 Volltextsuche - Indexverwaltung und Suchfunktionen."""

import logging
from dataclasses import dataclass

from backend.app.core.database import db

logger = logging.getLogger("buecherfreunde.search")


@dataclass
class SearchResult:
    """Ein einzelnes Suchergebnis."""

    book_id: int
    title: str
    author: str
    snippet: str
    relevance: float


async def search_books(
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> list[SearchResult]:
    """Durchsucht den FTS-Index und gibt Ergebnisse mit Snippets zurück.

    Unterstützt:
    - Einfache Suche: "python programmierung"
    - Phrasensuche: '"machine learning"'
    - Präfixsuche: "program*"
    - Boolsche Operatoren: "python AND NOT java"
    """
    if not query or not query.strip():
        return []

    sql = """
        SELECT
            books.id,
            books.title,
            books.author,
            snippet(books_fts, 2, '<mark>', '</mark>', '...', 40) as snippet,
            rank
        FROM books_fts
        JOIN books ON books.id = books_fts.rowid
        WHERE books_fts MATCH ?
        ORDER BY rank
        LIMIT ? OFFSET ?
    """

    try:
        rows = await db.fetch_all(sql, (query, limit, offset))
        return [
            SearchResult(
                book_id=row["id"],
                title=row["title"],
                author=row["author"],
                snippet=row["snippet"] or "",
                relevance=abs(row["rank"]),
            )
            for row in rows
        ]
    except Exception as e:
        logger.error("Suchfehler für '%s': %s", query, e)
        return []


async def search_count(query: str) -> int:
    """Zählt die Gesamtanzahl der Treffer für eine Suchanfrage."""
    if not query or not query.strip():
        return 0

    sql = """
        SELECT COUNT(*) as total
        FROM books_fts
        WHERE books_fts MATCH ?
    """
    try:
        row = await db.fetch_one(sql, (query,))
        return row["total"] if row else 0
    except Exception:
        return 0


async def suggest(query: str, limit: int = 5) -> list[dict]:
    """Autovervollständigung für die Suchleiste.

    Sucht in Titeln und Autoren nach Präfixübereinstimmungen.
    """
    if not query or len(query.strip()) < 2:
        return []

    prefix = query.strip() + "*"

    sql = """
        SELECT
            books.id,
            highlight(books_fts, 0, '<b>', '</b>') as title_hl,
            books.author
        FROM books_fts
        JOIN books ON books.id = books_fts.rowid
        WHERE books_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """

    try:
        # Suche in Titel
        title_query = f"title:{prefix}"
        rows = await db.fetch_all(sql, (title_query, limit))
        results = [
            {"id": row["id"], "titel": row["title_hl"], "autor": row["author"], "typ": "titel"}
            for row in rows
        ]

        # Suche in Autor falls nicht genug Ergebnisse
        if len(results) < limit:
            remaining = limit - len(results)
            author_query = f"author:{prefix}"
            sql_author = """
                SELECT DISTINCT books.id, books.title,
                    highlight(books_fts, 1, '<b>', '</b>') as author_hl
                FROM books_fts
                JOIN books ON books.id = books_fts.rowid
                WHERE books_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            author_rows = await db.fetch_all(sql_author, (author_query, remaining))
            existing_ids = {r["id"] for r in results}
            for row in author_rows:
                if row["id"] not in existing_ids:
                    results.append(
                        {"id": row["id"], "titel": row["title"], "autor": row["author_hl"], "typ": "autor"}
                    )

        return results
    except Exception as e:
        logger.error("Vorschlagsfehler für '%s': %s", query, e)
        return []


async def rebuild_index() -> int:
    """Baut den FTS-Index komplett neu auf.

    Gibt die Anzahl der indexierten Bücher zurück.
    """
    logger.info("FTS-Index wird neu aufgebaut...")

    # Index leeren
    await db.execute("INSERT INTO books_fts(books_fts) VALUES('delete-all')")

    # Alle Bücher neu indexieren
    sql = """
        INSERT INTO books_fts(rowid, title, author, fts_content)
        SELECT id, title, author, fts_content FROM books
    """
    await db.execute(sql)
    await db.commit()

    # Zählen
    row = await db.fetch_one("SELECT COUNT(*) as total FROM books")
    count = row["total"] if row else 0
    logger.info("FTS-Index neu aufgebaut: %d Bücher indexiert", count)
    return count


async def optimize_index() -> None:
    """Optimiert den FTS-Index (Merge aller Segmente)."""
    await db.execute("INSERT INTO books_fts(books_fts) VALUES('optimize')")
    await db.commit()
    logger.info("FTS-Index optimiert")
