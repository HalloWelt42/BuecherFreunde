"""Open Library API-Anbindung fuer Metadatenanreicherung."""

import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.openlibrary")

_last_request: datetime | None = None


async def _rate_limit() -> None:
    """Wartet falls noetig um das Rate-Limit einzuhalten."""
    global _last_request
    if _last_request is not None:
        elapsed = (datetime.now() - _last_request).total_seconds()
        wait = (1.0 / settings.openlibrary_rate_limit) - elapsed
        if wait > 0:
            await asyncio.sleep(wait)
    _last_request = datetime.now()


async def lookup_isbn(isbn: str) -> dict | None:
    """Sucht ein Buch anhand der ISBN bei Open Library.

    Returns:
        Dict mit Metadaten oder None wenn nicht gefunden.
    """
    if not settings.openlibrary_enabled:
        return None

    if not isbn:
        return None

    clean_isbn = isbn.replace("-", "").replace(" ", "")
    url = f"https://openlibrary.org/isbn/{clean_isbn}.json"

    await _rate_limit()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "BuecherFreunde/1.0 (Buchverwaltung)"},
            )
            if response.status_code == 404:
                logger.info("ISBN %s nicht bei Open Library gefunden", clean_isbn)
                return None
            response.raise_for_status()
            data = response.json()

            result = _parse_edition(data)
            result["isbn"] = clean_isbn

            # Autorennamen aufloeisen
            if "authors" in data:
                author_names = []
                for author_ref in data["authors"]:
                    key = author_ref.get("key", "")
                    if key:
                        name = await _resolve_author(key)
                        if name:
                            author_names.append(name)
                if author_names:
                    result["autor"] = ", ".join(author_names)

            logger.info("ISBN %s gefunden: %s", clean_isbn, result.get("titel", ""))
            return result

    except httpx.HTTPError as e:
        logger.warning("Open Library Fehler fuer ISBN %s: %s", clean_isbn, e)
        return None


async def search_books(query: str, limit: int = 5) -> list[dict]:
    """Sucht Buecher bei Open Library nach Titel/Autor.

    Returns:
        Liste von Ergebnissen mit Metadaten.
    """
    if not settings.openlibrary_enabled:
        return []

    if not query or len(query.strip()) < 3:
        return []

    url = "https://openlibrary.org/search.json"
    params = {"q": query, "limit": limit, "fields": "key,title,author_name,isbn,publisher,first_publish_year,subject,cover_i"}

    await _rate_limit()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url,
                params=params,
                headers={"User-Agent": "BuecherFreunde/1.0 (Buchverwaltung)"},
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for doc in data.get("docs", []):
                results.append({
                    "titel": doc.get("title", ""),
                    "autor": ", ".join(doc.get("author_name", [])),
                    "isbn": doc.get("isbn", [""])[0] if doc.get("isbn") else "",
                    "verlag": doc.get("publisher", [""])[0] if doc.get("publisher") else "",
                    "jahr": doc.get("first_publish_year"),
                    "themen": doc.get("subject", [])[:10],
                    "cover_id": doc.get("cover_i"),
                })

            return results

    except httpx.HTTPError as e:
        logger.warning("Open Library Suche fehlgeschlagen: %s", e)
        return []


async def _resolve_author(author_key: str) -> str | None:
    """Loest einen Autoren-Key in den Namen auf."""
    url = f"https://openlibrary.org{author_key}.json"

    await _rate_limit()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "BuecherFreunde/1.0 (Buchverwaltung)"},
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("name", "")
    except httpx.HTTPError:
        pass
    return None


def _parse_edition(data: dict) -> dict:
    """Extrahiert relevante Felder aus einer Open Library Edition."""
    result = {}

    result["titel"] = data.get("title", "")

    publishers = data.get("publishers", [])
    if publishers:
        result["verlag"] = publishers[0]

    publish_date = data.get("publish_date", "")
    if publish_date:
        # Versuche das Jahr zu extrahieren
        for part in publish_date.split():
            if part.isdigit() and len(part) == 4:
                result["jahr"] = int(part)
                break

    languages = data.get("languages", [])
    if languages:
        lang_key = languages[0].get("key", "")
        result["sprache"] = lang_key.split("/")[-1] if lang_key else ""

    description = data.get("description", "")
    if isinstance(description, dict):
        description = description.get("value", "")
    result["beschreibung"] = description

    result["seiten"] = data.get("number_of_pages", 0)

    subjects = data.get("subjects", [])
    result["themen"] = subjects[:20]

    return result


async def get_cover_url(cover_id: int, size: str = "M") -> str | None:
    """Gibt die URL fuer ein Open Library Cover zurueck.

    Size: S (klein), M (mittel), L (gross)
    """
    if not cover_id:
        return None
    return f"https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg"


async def check_connection() -> dict:
    """Prueft die Verbindung zu Open Library."""
    if not settings.openlibrary_enabled:
        return {"erreichbar": False, "grund": "Deaktiviert"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://openlibrary.org/search.json?q=test&limit=1",
                headers={"User-Agent": "BuecherFreunde/1.0 (Buchverwaltung)"},
            )
            return {
                "erreichbar": response.status_code == 200,
                "status_code": response.status_code,
            }
    except httpx.HTTPError as e:
        return {"erreichbar": False, "grund": str(e)}
