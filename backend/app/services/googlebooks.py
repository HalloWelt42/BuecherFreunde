"""Google Books API-Anbindung für Metadatenanreicherung (Primärquelle)."""

import io
import logging
import re

import httpx
from PIL import Image

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.googlebooks")

COVER_MAX_WIDTH = 800
COVER_MAX_HEIGHT = 1200
COVER_QUALITY = 85

# Kategorien die wir rausfiltern (Meta-Informationen, keine echten Kategorien)
_SKIP_CATEGORIES = {
    "general",
}


def _extract_year(date_str: str) -> int | None:
    """Extrahiert das Jahr aus Google Books Datumsformaten."""
    if not date_str:
        return None
    match = re.search(r"\b(\d{4})\b", date_str)
    return int(match.group(1)) if match else None


def _clean_categories(categories: list[str]) -> list[str]:
    """Bereinigt Google Books Kategorien."""
    result = set()
    for cat in categories:
        # Google liefert manchmal "Fiction / Romance / Historical"
        parts = [p.strip() for p in cat.split("/")]
        for part in parts:
            if part and part.lower() not in _SKIP_CATEGORIES and len(part) > 1:
                result.add(part)
    return sorted(result)


async def lookup_isbn(isbn: str) -> dict | None:
    """Sucht ein Buch per ISBN bei Google Books."""
    if not settings.google_books_enabled or not isbn:
        return None

    clean_isbn = isbn.replace("-", "").replace(" ", "")
    return await _search(f"isbn:{clean_isbn}")


async def search_books(query: str, limit: int = 5) -> list[dict]:
    """Sucht Bücher bei Google Books nach Titel/Autor."""
    if not settings.google_books_enabled or not query or len(query.strip()) < 3:
        return []

    params = {"q": query, "maxResults": limit, "printType": "books"}
    if settings.google_books_api_key:
        params["key"] = settings.google_books_api_key

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://www.googleapis.com/books/v1/volumes",
                params=params,
                headers={"User-Agent": "BuecherFreunde/1.0"},
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("items", [])[:limit]:
                parsed = _parse_volume(item)
                if parsed:
                    results.append(parsed)
            return results

    except httpx.HTTPError as e:
        logger.warning("Google Books Suche fehlgeschlagen: %s", e)
        return []


async def _search(query: str) -> dict | None:
    """Interne Suche, gibt das erste Ergebnis zurück."""
    params = {"q": query, "maxResults": 1, "printType": "books"}
    if settings.google_books_api_key:
        params["key"] = settings.google_books_api_key

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://www.googleapis.com/books/v1/volumes",
                params=params,
                headers={"User-Agent": "BuecherFreunde/1.0"},
            )
            if response.status_code == 429:
                logger.warning("Google Books Rate-Limit erreicht")
                return None
            response.raise_for_status()
            data = response.json()

            if data.get("totalItems", 0) == 0:
                return None

            items = data.get("items", [])
            if not items:
                return None

            return _parse_volume(items[0])

    except httpx.HTTPError as e:
        logger.warning("Google Books Fehler: %s", e)
        return None


def _parse_volume(item: dict) -> dict | None:
    """Parst ein Google Books Volume-Objekt."""
    info = item.get("volumeInfo", {})
    if not info:
        return None

    # ISBN extrahieren
    isbn = ""
    for ident in info.get("industryIdentifiers", []):
        if ident.get("type") == "ISBN_13":
            isbn = ident.get("identifier", "")
            break
        if ident.get("type") == "ISBN_10" and not isbn:
            isbn = ident.get("identifier", "")

    # Cover-URL: Beste Qualität holen
    cover_url = ""
    image_links = info.get("imageLinks", {})
    for key in ("extraLarge", "large", "medium", "thumbnail", "smallThumbnail"):
        if key in image_links:
            url = image_links[key]
            # Google liefert oft HTTP - auf HTTPS umstellen
            # und zoom-Parameter erhöhen für bessere Qualität
            url = url.replace("http://", "https://")
            # Edge-Curling entfernen für sauberes Bild
            url = re.sub(r"&edge=\w+", "", url)
            cover_url = url
            break

    # Sprache
    sprache = info.get("language", "")

    result = {
        "titel": info.get("title", ""),
        "autor": ", ".join(info.get("authors", [])),
        "isbn": isbn,
        "verlag": info.get("publisher", ""),
        "jahr": _extract_year(info.get("publishedDate", "")),
        "seiten": info.get("pageCount", 0),
        "beschreibung": info.get("description", ""),
        "sprache": sprache,
        "kategorien": _clean_categories(info.get("categories", [])),
        "cover_url": cover_url,
        "quelle": "google_books",
    }

    # Rohdaten: alle Felder die nicht direkt gemappt sind
    raw = {}
    if info.get("subtitle"):
        raw["untertitel"] = info["subtitle"]
    if info.get("publishedDate"):
        raw["erscheinungsdatum"] = info["publishedDate"]
    if info.get("industryIdentifiers"):
        raw["identifiers"] = {
            i.get("type", ""): i.get("identifier", "")
            for i in info["industryIdentifiers"]
        }
    if info.get("readingModes"):
        raw["lesemodi"] = info["readingModes"]
    if info.get("maturityRating"):
        raw["altersfreigabe"] = info["maturityRating"]
    if info.get("contentVersion"):
        raw["inhaltsversion"] = info["contentVersion"]
    if info.get("previewLink"):
        raw["vorschau_link"] = info["previewLink"]
    if info.get("infoLink"):
        raw["info_link"] = info["infoLink"]
    if info.get("canonicalVolumeLink"):
        raw["google_books_link"] = info["canonicalVolumeLink"]
    if info.get("averageRating"):
        raw["durchschnittsbewertung"] = info["averageRating"]
    if info.get("ratingsCount"):
        raw["anzahl_bewertungen"] = info["ratingsCount"]
    if info.get("dimensions"):
        raw["abmessungen"] = info["dimensions"]
    result["raw"] = raw

    return result


async def download_cover(cover_url: str) -> bytes | None:
    """Lädt ein Cover-Bild herunter, skaliert und optimiert es."""
    if not cover_url:
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                cover_url,
                headers={"User-Agent": "BuecherFreunde/1.0"},
            )
            response.raise_for_status()
            image_data = response.content

            if len(image_data) < 1000:
                logger.info("Cover zu klein, wahrscheinlich Platzhalter")
                return None

            img = Image.open(io.BytesIO(image_data))

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            img.thumbnail((COVER_MAX_WIDTH, COVER_MAX_HEIGHT), Image.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=COVER_QUALITY, optimize=True)
            return buffer.getvalue()

    except Exception as e:
        logger.warning("Cover-Download fehlgeschlagen: %s - %s", cover_url, e)
        return None


async def check_connection() -> dict:
    """Prüft die Verbindung zu Google Books."""
    if not settings.google_books_enabled:
        return {"erreichbar": False, "grund": "Deaktiviert"}

    try:
        params = {"q": "test", "maxResults": 1}
        if settings.google_books_api_key:
            params["key"] = settings.google_books_api_key

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://www.googleapis.com/books/v1/volumes",
                params=params,
                headers={"User-Agent": "BuecherFreunde/1.0"},
            )
            return {
                "erreichbar": response.status_code == 200,
                "status_code": response.status_code,
            }
    except httpx.HTTPError as e:
        return {"erreichbar": False, "grund": str(e)}
