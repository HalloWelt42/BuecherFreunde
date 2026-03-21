"""Open Library API-Anbindung fuer Metadatenanreicherung."""

import asyncio
import io
import logging
import re
from datetime import datetime
from pathlib import Path

import httpx
from PIL import Image

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.openlibrary")

_last_request: datetime | None = None

# Cover-Zielgroessen
COVER_MAX_WIDTH = 800
COVER_MAX_HEIGHT = 1200
COVER_QUALITY = 85


async def _rate_limit() -> None:
    """Wartet falls noetig um das Rate-Limit einzuhalten."""
    global _last_request
    if _last_request is not None:
        elapsed = (datetime.now() - _last_request).total_seconds()
        wait = (1.0 / settings.openlibrary_rate_limit) - elapsed
        if wait > 0:
            await asyncio.sleep(wait)
    _last_request = datetime.now()


async def _fetch_json(url: str, params: dict | None = None, timeout: float = 10.0) -> dict | None:
    """Holt JSON von einer URL mit Rate-Limiting."""
    await _rate_limit()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                url,
                params=params,
                headers={"User-Agent": "BuecherFreunde/1.0 (Buchverwaltung)"},
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.warning("Open Library Anfrage fehlgeschlagen: %s - %s", url, e)
        return None


def _extract_year(publish_date: str) -> int | None:
    """Extrahiert das Jahr aus verschiedenen Datumsformaten."""
    if not publish_date:
        return None
    # Fragezeichen und Sonderzeichen entfernen
    clean = publish_date.replace("?", "").strip()
    # 4-stellige Jahreszahl suchen
    match = re.search(r"\b(\d{4})\b", clean)
    if match:
        return int(match.group(1))
    return None


def _collect_subjects(data: dict) -> list[str]:
    """Sammelt alle Subject-Varianten als flache Liste."""
    subjects = set()
    for key in ("subjects", "subject_places", "subject_people", "subject_times"):
        for entry in data.get(key, []):
            name = entry.get("name", "") if isinstance(entry, dict) else str(entry)
            name = name.strip()
            if name and not name.startswith("series:"):
                # Meta-Eintraege filtern
                skip_patterns = (
                    "Reading Level-",
                    "open_syllabus_project",
                    "Long now manual",
                    "Pr6029",
                    "nyt:",
                )
                if not any(name.startswith(p) or name.lower().startswith(p.lower()) for p in skip_patterns):
                    subjects.add(name)
    return sorted(subjects)


async def lookup_bibkeys(isbn: str) -> dict | None:
    """Holt vollstaendige Buchdaten ueber die Bibkeys-API.

    Diese API liefert alles in einem Call: Titel, Autor, Verlag,
    Subjects, Cover-URLs, Excerpts, Links etc.
    """
    if not settings.openlibrary_enabled or not isbn:
        return None

    clean_isbn = isbn.replace("-", "").replace(" ", "")
    url = "https://openlibrary.org/api/books"
    params = {
        "bibkeys": f"ISBN:{clean_isbn}",
        "format": "json",
        "jscmd": "data",
    }

    data = await _fetch_json(url, params=params, timeout=15.0)
    if not data:
        return None

    key = f"ISBN:{clean_isbn}"
    if key not in data:
        logger.info("ISBN %s nicht bei Open Library gefunden", clean_isbn)
        return None

    book = data[key]
    logger.info("ISBN %s gefunden: %s", clean_isbn, book.get("title", ""))

    result = {
        "titel": book.get("title", ""),
        "autor": ", ".join(a.get("name", "") for a in book.get("authors", [])),
        "isbn": clean_isbn,
        "verlag": book.get("publishers", [{}])[0].get("name", "") if book.get("publishers") else "",
        "jahr": _extract_year(book.get("publish_date", "")),
        "seiten": book.get("number_of_pages", 0),
        "kategorien": _collect_subjects(book),
        "cover_url": book.get("cover", {}).get("large", ""),
        "identifiers": book.get("identifiers", {}),
        "excerpts": [e.get("text", "") for e in book.get("excerpts", [])],
        "links": [{"title": l.get("title", ""), "url": l.get("url", "")} for l in book.get("links", [])],
        "raw": book,
    }

    return result


async def lookup_isbn(isbn: str) -> dict | None:
    """Sucht ein Buch anhand der ISBN bei Open Library.

    Nutzt zuerst die Bibkeys-API (vollstaendig), faellt zurueck
    auf die Edition-API falls noetig.
    """
    # Zuerst Bibkeys versuchen (liefert alles)
    result = await lookup_bibkeys(isbn)
    if result:
        return result

    if not settings.openlibrary_enabled or not isbn:
        return None

    clean_isbn = isbn.replace("-", "").replace(" ", "")
    url = f"https://openlibrary.org/isbn/{clean_isbn}.json"

    data = await _fetch_json(url)
    if not data:
        return None

    result = _parse_edition(data)
    result["isbn"] = clean_isbn

    # Autorennamen aufloesen
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

    logger.info("ISBN %s gefunden (Edition-API): %s", clean_isbn, result.get("titel", ""))
    return result


async def search_books(query: str, limit: int = 5) -> list[dict]:
    """Sucht Buecher bei Open Library nach Titel/Autor."""
    if not settings.openlibrary_enabled:
        return []

    if not query or len(query.strip()) < 3:
        return []

    url = "https://openlibrary.org/search.json"
    params = {
        "q": query,
        "limit": limit,
        "fields": "key,title,author_name,isbn,publisher,first_publish_year,subject,cover_i",
    }

    data = await _fetch_json(url, params=params, timeout=15.0)
    if not data:
        return []

    results = []
    for doc in data.get("docs", []):
        results.append({
            "titel": doc.get("title", ""),
            "autor": ", ".join(doc.get("author_name", [])),
            "isbn": doc.get("isbn", [""])[0] if doc.get("isbn") else "",
            "verlag": doc.get("publisher", [""])[0] if doc.get("publisher") else "",
            "jahr": doc.get("first_publish_year"),
            "themen": doc.get("subject", [])[:20],
            "cover_id": doc.get("cover_i"),
        })

    return results


async def download_cover(cover_url: str) -> bytes | None:
    """Laedt ein Cover-Bild herunter, skaliert und optimiert es.

    Gibt JPEG-Bytes zurueck (max 800x1200, Qualitaet 85).
    """
    if not cover_url:
        return None

    await _rate_limit()

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                cover_url,
                headers={"User-Agent": "BuecherFreunde/1.0 (Buchverwaltung)"},
            )
            response.raise_for_status()
            image_data = response.content

            if len(image_data) < 1000:
                logger.info("Cover zu klein, wahrscheinlich Platzhalter")
                return None

            img = Image.open(io.BytesIO(image_data))

            # RGBA/P -> RGB konvertieren
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Skalieren wenn zu gross
            img.thumbnail((COVER_MAX_WIDTH, COVER_MAX_HEIGHT), Image.LANCZOS)

            # Als JPEG speichern
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=COVER_QUALITY, optimize=True)
            return buffer.getvalue()

    except Exception as e:
        logger.warning("Cover-Download fehlgeschlagen: %s - %s", cover_url, e)
        return None


async def _resolve_author(author_key: str) -> str | None:
    """Loest einen Autoren-Key in den Namen auf."""
    url = f"https://openlibrary.org{author_key}.json"
    data = await _fetch_json(url)
    if data:
        return data.get("name", "")
    return None


def _parse_edition(data: dict) -> dict:
    """Extrahiert relevante Felder aus einer Open Library Edition."""
    result = {}

    result["titel"] = data.get("title", "")

    publishers = data.get("publishers", [])
    if publishers:
        result["verlag"] = publishers[0]

    result["jahr"] = _extract_year(data.get("publish_date", ""))

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
    result["kategorien"] = _collect_subjects(data) if any(
        data.get(k) for k in ("subjects", "subject_places", "subject_people", "subject_times")
    ) else [s if isinstance(s, str) else s for s in subjects[:20]]

    return result


async def get_cover_url(cover_id: int, size: str = "M") -> str | None:
    """Gibt die URL fuer ein Open Library Cover zurueck."""
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
