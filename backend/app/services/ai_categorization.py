"""Bücher einordnen mit der KI (BF-10): Vorschläge für Kategorien aus Titel, Autor und Textauszug, über den einen Weg zur
KI (services/ki.py, die Leitstelle). Die Anweisung kommt aus der Datenbank (Tabelle ai_prompts, in den Einstellungen
pflegbar). Ohne Leitstelle gibt es keine Vorschläge; eingeordnet wird dann von Hand."""

import json
import logging

from backend.app.core.database import db
from backend.app.services.data_cleaner import bereinige_kategorien
from backend.app.services.ki import KiFehler, ki

logger = logging.getLogger("buecherfreunde.ai")

# Rückfall, solange die Datenbank noch keine Anweisung hat
FALLBACK_PROMPT = """Du bist ein Bibliothekar der Bücher kategorisiert.
Analysiere den gegebenen Buchtitel, Autor und Textauszug.
Schlage 3-5 passende Kategorien vor.

Antworte ausschließlich als JSON-Array mit Objekten:
[{"kategorie": "Name", "konfidenz": 0.0-1.0}]

Verwende deutsche Kategorienamen."""


async def _load_prompt(schluessel: str) -> dict | None:
    return await db.fetch_one("SELECT * FROM ai_prompts WHERE schluessel = ? AND aktiv = 1", (schluessel,))


async def send_prompt(schluessel: str, user_message: str, titel: str) -> str:
    """Die Anweisung `schluessel` mit der Nachricht an die KI; wirft KiFehler mit dem Grund, wenn es nicht geht."""
    if not ki.bereit:
        raise KiFehler("Keine Leitstelle eingetragen (LEITSTELLE_ADRESSE)", "abgelehnt")
    prompt = await _load_prompt(schluessel)
    return await ki.antwort(prompt["system_prompt"] if prompt else FALLBACK_PROMPT, user_message, titel=titel,
                            temperature=prompt["temperatur"] if prompt else 0.3, max_tokens=prompt["max_tokens"] if prompt else 500)


async def categorize_book(title: str, author: str, text_excerpt: str = "") -> list[dict]:
    """Vorschläge `[{kategorie, konfidenz}]`, bereinigt; wirft KiFehler, wenn die KI nicht antwortet."""
    user_msg = f"Titel: {title}\nAutor: {author}"
    if text_excerpt:
        user_msg += f"\n\nTextauszug:\n{text_excerpt[:2000]}"
    content = await send_prompt("kategorisierung", user_msg, titel=f"Einordnen: {title[:80]}")
    categories = _parse_categories(content)
    bereinigt = {n.lower() for n in bereinige_kategorien([c["kategorie"] for c in categories])}
    categories = [c for c in categories if c["kategorie"].lower() in bereinigt]
    logger.info("KI-Einordnung für '%s': %d Vorschläge", title, len(categories))
    return categories


def _als_liste(result: object) -> list[dict]:
    if not isinstance(result, list):
        return []
    return [{"kategorie": item.get("kategorie", ""), "konfidenz": min(1.0, max(0.0, float(item.get("konfidenz", 0.5))))}
            for item in result if isinstance(item, dict) and item.get("kategorie")]


def _parse_categories(content: str) -> list[dict]:
    """Die Kategorien aus der Antwort; das JSON-Array darf von Text umgeben sein."""
    for kandidat in (content, content[content.find("["):content.rfind("]") + 1] if "[" in content else ""):
        try:
            return _als_liste(json.loads(kandidat))
        except (ValueError, TypeError):
            continue
    logger.warning("KI-Antwort nicht lesbar: %s", content[:200])
    return []
