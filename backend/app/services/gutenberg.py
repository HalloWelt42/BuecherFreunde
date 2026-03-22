"""Gutenberg-Service - Zugriff auf die Gutendex-API.

Gutendex (gutendex.com) ist eine JSON-API für Project Gutenberg.
Ermöglicht Suche, Vorschau und Download gemeinfreier Bücher.
"""

import logging
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger("buecherfreunde.gutenberg")

GUTENDEX_BASE = "https://gutendex.com"


async def suche(
    query: str = "",
    sprache: str = "",
    topic: str = "",
    seite: int = 1,
) -> dict:
    """Sucht Bücher über die Gutendex-API.

    Args:
        query: Suchbegriff (Titel, Autor)
        sprache: Sprachfilter (z.B. "de", "en", "de,en")
        topic: Thema/Kategorie
        seite: Seitennummer (1-basiert)

    Returns:
        Dict mit count, next, previous, results[]
    """
    params = {"page": seite}
    if query:
        params["search"] = query
    if sprache:
        params["languages"] = sprache
    if topic:
        params["topic"] = topic

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(f"{GUTENDEX_BASE}/books/", params=params)
        resp.raise_for_status()
        data = resp.json()

    # Ergebnisse aufbereiten
    buecher = []
    for b in data.get("results", []):
        buch = _parse_buch(b)
        if buch:
            buecher.append(buch)

    return {
        "gesamt": data.get("count", 0),
        "seite": seite,
        "naechste": data.get("next"),
        "vorherige": data.get("previous"),
        "buecher": buecher,
    }


def _parse_buch(raw: dict) -> dict | None:
    """Parst ein Gutendex-Ergebnis in unser Format."""
    gutenberg_id = raw.get("id")
    if not gutenberg_id:
        return None

    # Autoren zusammensetzen
    autoren = []
    for a in raw.get("authors", []):
        name = a.get("name", "")
        if name:
            autoren.append(name)
    autor = "; ".join(autoren) if autoren else ""

    # Beste Download-URL finden (Priorität: EPUB > TXT)
    formats = raw.get("formats", {})
    download_url = ""
    download_format = ""

    # EPUB bevorzugen
    for key in formats:
        if "epub" in key.lower() and "image" not in key.lower():
            download_url = formats[key]
            download_format = "epub"
            break

    # Fallback: Plain Text (UTF-8)
    if not download_url:
        for key in formats:
            if "text/plain" in key.lower() and "utf-8" in key.lower():
                download_url = formats[key]
                download_format = "txt"
                break

    # Fallback: irgendein Text
    if not download_url:
        for key in formats:
            if "text/plain" in key.lower():
                download_url = formats[key]
                download_format = "txt"
                break

    # Cover-Bild
    cover_url = ""
    for key in formats:
        if "image/jpeg" in key.lower():
            cover_url = formats[key]
            break

    # Sprachen
    sprachen = raw.get("languages", [])

    # Kategorien/Bookshelves
    regale = [s for s in raw.get("bookshelves", [])]
    themen = [s for s in raw.get("subjects", [])]

    return {
        "gutenberg_id": gutenberg_id,
        "titel": raw.get("title", f"Gutenberg #{gutenberg_id}"),
        "autor": autor,
        "sprachen": sprachen,
        "download_url": download_url,
        "download_format": download_format,
        "cover_url": cover_url,
        "regale": regale,
        "themen": themen,
        "download_count": raw.get("download_count", 0),
    }


async def download_buch(gutenberg_id: int, download_url: str) -> Path | None:
    """Lädt eine Buchdatei von Gutenberg herunter.

    Returns:
        Pfad zur temporären Datei oder None bei Fehler.
    """
    if not download_url:
        logger.warning("Keine Download-URL für Gutenberg #%d", gutenberg_id)
        return None

    # Dateiendung aus URL ableiten
    suffix = ".epub"
    if download_url.endswith(".txt") or download_url.endswith(".txt.utf-8"):
        suffix = ".txt"
    elif ".epub" in download_url:
        suffix = ".epub"

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(download_url)
            resp.raise_for_status()

            # In Temp-Datei speichern
            tmp = tempfile.NamedTemporaryFile(
                prefix=f"gutenberg_{gutenberg_id}_",
                suffix=suffix,
                delete=False,
            )
            tmp.write(resp.content)
            tmp.close()
            logger.info(
                "Gutenberg #%d heruntergeladen: %d Bytes -> %s",
                gutenberg_id, len(resp.content), tmp.name,
            )
            return Path(tmp.name)

    except Exception as e:
        logger.error("Download fehlgeschlagen für Gutenberg #%d: %s", gutenberg_id, e)
        return None


async def download_cover(cover_url: str) -> bytes | None:
    """Lädt ein Cover-Bild herunter."""
    if not cover_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(cover_url)
            resp.raise_for_status()
            if len(resp.content) > 100:
                return resp.content
    except Exception as e:
        logger.debug("Cover-Download fehlgeschlagen: %s", e)
    return None
