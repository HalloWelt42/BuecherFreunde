"""FTS5 Volltextsuche - Indexverwaltung und Suchfunktionen."""

import logging
import re
from dataclasses import dataclass

from backend.app.core.database import db
from backend.app.services.query_parser import ParsedQuery, parse_query

logger = logging.getLogger("buecherfreunde.search")

# Erlaubte HTML-Tags in Suchergebnissen (alles andere wird entfernt)
_ALLOWED_TAGS = {"b", "mark"}
_STRIP_TAGS_RE = re.compile(
    r"</?(?!" + "|".join(_ALLOWED_TAGS) + r")(\w+)[^>]*>", re.IGNORECASE
)


def _sanitize_html(text: str) -> str:
    """Entfernt alle HTML-Tags ausser den erlaubten (b, mark).

    Verhindert Stored XSS durch bösartige Buchtitel oder Metadaten
    die per highlight()/snippet() mit HTML-Markup versehen werden.
    """
    if not text:
        return text
    return _STRIP_TAGS_RE.sub("", text)


@dataclass
class SearchResult:
    """Ein einzelnes Suchergebnis."""

    book_id: int
    title: str
    author: str
    snippet: str
    relevance: float


def _build_filter_conditions(parsed: ParsedQuery) -> tuple[list[str], list]:
    """Baut WHERE-Bedingungen und Parameter fuer strukturierte Filter."""
    conditions = []
    params = []

    if parsed.autor:
        conditions.append("LOWER(books.author) LIKE LOWER(?)")
        params.append(f"%{parsed.autor}%")

    if parsed.format:
        conditions.append("books.file_format = ?")
        params.append(parsed.format)

    if parsed.jahr_exakt:
        conditions.append("books.year = ?")
        params.append(parsed.jahr_exakt)
    else:
        if parsed.jahr_von:
            conditions.append("books.year >= ?")
            params.append(parsed.jahr_von)
        if parsed.jahr_bis:
            conditions.append("books.year <= ?")
            params.append(parsed.jahr_bis)

    return conditions, params


async def search_books(
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[SearchResult], ParsedQuery]:
    """Durchsucht den FTS-Index und gibt Ergebnisse mit Snippets zurueck.

    Unterstuetzt:
    - Einfache Suche: "python programmierung"
    - Phrasensuche: '"machine learning"'
    - Praefixsuche: "program*"
    - Boolsche Operatoren: "python AND NOT java"
    - Erweiterte Filter: autor:, format:, datum:
    """
    parsed = parse_query(query)

    if not parsed.fts_query and not parsed.hat_filter:
        return [], parsed

    filter_conds, filter_params = _build_filter_conditions(parsed)

    try:
        if parsed.fts_query:
            # Fall A: FTS-Query vorhanden (ggf. mit zusaetzlichen Filtern)
            where_parts = ["books_fts MATCH ?"]
            params = [parsed.fts_query]
            where_parts.extend(filter_conds)
            params.extend(filter_params)

            sql = f"""
                SELECT
                    books.id,
                    books.title,
                    books.author,
                    snippet(books_fts, 2, '<mark>', '</mark>', '...', 40) as snippet,
                    rank
                FROM books_fts
                JOIN books ON books.id = books_fts.rowid
                WHERE {' AND '.join(where_parts)}
                ORDER BY rank
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            rows = await db.fetch_all(sql, tuple(params))
            results = [
                SearchResult(
                    book_id=row["id"],
                    title=_sanitize_html(row["title"]),
                    author=_sanitize_html(row["author"]),
                    snippet=_sanitize_html(row["snippet"] or ""),
                    relevance=abs(row["rank"]),
                )
                for row in rows
            ]
        else:
            # Fall B: Nur Filter, kein FTS-Query
            where_clause = " AND ".join(filter_conds) if filter_conds else "1=1"
            sql = f"""
                SELECT id, title, author, '' as snippet, 0 as rank
                FROM books
                WHERE {where_clause}
                ORDER BY title
                LIMIT ? OFFSET ?
            """
            params = filter_params + [limit, offset]
            rows = await db.fetch_all(sql, tuple(params))
            results = [
                SearchResult(
                    book_id=row["id"],
                    title=_sanitize_html(row["title"]),
                    author=_sanitize_html(row["author"]),
                    snippet="",
                    relevance=0,
                )
                for row in rows
            ]

        return results, parsed
    except Exception as e:
        logger.error("Suchfehler fuer '%s': %s", query, e)
        return [], parsed


async def search_count(query: str) -> int:
    """Zaehlt die Gesamtanzahl der Treffer fuer eine Suchanfrage."""
    if not query or not query.strip():
        return 0

    parsed = parse_query(query)

    if not parsed.fts_query and not parsed.hat_filter:
        return 0

    filter_conds, filter_params = _build_filter_conditions(parsed)

    try:
        if parsed.fts_query:
            where_parts = ["books_fts MATCH ?"]
            params = [parsed.fts_query]
            where_parts.extend(filter_conds)
            params.extend(filter_params)

            sql = f"""
                SELECT COUNT(*) as total
                FROM books_fts
                JOIN books ON books.id = books_fts.rowid
                WHERE {' AND '.join(where_parts)}
            """
            row = await db.fetch_one(sql, tuple(params))
        else:
            where_clause = " AND ".join(filter_conds) if filter_conds else "1=1"
            sql = f"""
                SELECT COUNT(*) as total
                FROM books
                WHERE {where_clause}
            """
            row = await db.fetch_one(sql, tuple(filter_params))

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
            {"id": row["id"], "titel": _sanitize_html(row["title_hl"]), "autor": _sanitize_html(row["author"]), "typ": "titel"}
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
                        {"id": row["id"], "titel": _sanitize_html(row["title"]), "autor": _sanitize_html(row["author_hl"]), "typ": "autor"}
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
