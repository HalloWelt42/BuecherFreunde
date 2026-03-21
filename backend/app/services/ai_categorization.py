"""LM Studio KI-Kategorisierung über OpenAI-kompatible API."""

import json
import logging

import httpx

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.ai")

# Fallback-Prompt falls DB noch leer
FALLBACK_PROMPT = """Du bist ein Bibliothekar der Bücher kategorisiert.
Analysiere den gegebenen Buchtitel, Autor und Textauszug.
Schlage 3-5 passende Kategorien vor.

Antworte ausschließlich als JSON-Array mit Objekten:
[{"kategorie": "Name", "konfidenz": 0.0-1.0}]

Verwende deutsche Kategorienamen."""


async def _load_prompt(schluessel: str) -> dict | None:
    """Lädt einen Prompt aus der Datenbank."""
    from backend.app.core.database import db
    return await db.fetch_one(
        "SELECT * FROM ai_prompts WHERE schluessel = ? AND aktiv = 1",
        (schluessel,),
    )


async def send_prompt(
    schluessel: str,
    user_message: str,
) -> str | None:
    """Sendet einen Prompt an LM Studio und gibt die Antwort zurück.

    Nutzt die Prompt-Konfiguration aus der Datenbank.
    """
    if not settings.lm_studio_enabled:
        return None

    prompt = await _load_prompt(schluessel)
    system_prompt = prompt["system_prompt"] if prompt else FALLBACK_PROMPT
    temperatur = prompt["temperatur"] if prompt else 0.3
    max_tokens = prompt["max_tokens"] if prompt else 500

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.lm_studio_url}/chat/completions",
                json={
                    "model": settings.lm_studio_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": temperatur,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    except httpx.ConnectError:
        logger.warning("LM Studio nicht erreichbar unter %s", settings.lm_studio_url)
        return None
    except httpx.HTTPError as e:
        logger.warning("LM Studio Fehler: %s", e)
        return None
    except Exception as e:
        logger.error("LM Studio Anfrage fehlgeschlagen: %s", e)
        return None


async def categorize_book(
    title: str,
    author: str,
    text_excerpt: str = "",
) -> list[dict]:
    """Kategorisiert ein Buch mittels LM Studio.

    Args:
        title: Buchtitel
        author: Autor
        text_excerpt: Erste 2000 Zeichen des Textes

    Returns:
        Liste von Kategorie-Vorschlägen mit Konfidenz.
    """
    excerpt = text_excerpt[:2000] if text_excerpt else ""
    user_msg = f"Titel: {title}\nAutor: {author}"
    if excerpt:
        user_msg += f"\n\nTextauszug:\n{excerpt}"

    content = await send_prompt("kategorisierung", user_msg)
    if not content:
        return []

    categories = _parse_categories(content)
    logger.info(
        "KI-Kategorisierung für '%s': %d Vorschläge",
        title,
        len(categories),
    )
    return categories


def _parse_categories(content: str) -> list[dict]:
    """Extrahiert Kategorien aus der KI-Antwort."""
    # Versuche JSON direkt zu parsen
    try:
        result = json.loads(content)
        if isinstance(result, list):
            return [
                {
                    "kategorie": item.get("kategorie", ""),
                    "konfidenz": min(1.0, max(0.0, float(item.get("konfidenz", 0.5)))),
                }
                for item in result
                if item.get("kategorie")
            ]
    except json.JSONDecodeError:
        pass

    # Versuche JSON aus dem Text zu extrahieren (zwischen [ und ])
    start = content.find("[")
    end = content.rfind("]")
    if start >= 0 and end > start:
        try:
            result = json.loads(content[start : end + 1])
            if isinstance(result, list):
                return [
                    {
                        "kategorie": item.get("kategorie", ""),
                        "konfidenz": min(1.0, max(0.0, float(item.get("konfidenz", 0.5)))),
                    }
                    for item in result
                    if item.get("kategorie")
                ]
        except json.JSONDecodeError:
            pass

    logger.warning("KI-Antwort konnte nicht geparst werden: %s", content[:200])
    return []


async def check_connection() -> dict:
    """Prüft ob LM Studio erreichbar ist."""
    if not settings.lm_studio_enabled:
        return {"erreichbar": False, "grund": "Deaktiviert"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.lm_studio_url}/models")
            if response.status_code == 200:
                data = response.json()
                models = [m.get("id", "") for m in data.get("data", [])]
                return {
                    "erreichbar": True,
                    "modelle": models,
                }
            return {"erreichbar": False, "status_code": response.status_code}
    except httpx.ConnectError:
        return {"erreichbar": False, "grund": "Verbindung fehlgeschlagen"}
    except httpx.HTTPError as e:
        return {"erreichbar": False, "grund": str(e)}
