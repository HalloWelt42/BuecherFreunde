"""Fehlenden Volltext aus der Datei lesen: mit demselben Leser wie beim Aufnehmen (eigener Prozess), abgelegt und im Suchindex.
Für den Lauf "Volltext" in Bibliothek ergänzen und die ISBN-Suche, wenn ein Buch noch keinen Text hat (BF-111)."""

from __future__ import annotations

from pathlib import Path

from backend.app.annahme import auswertung
from backend.app.core.database import db
from backend.app.core.suchindex import SUCHTEXT_ZEICHEN
from backend.app.services.storage import save_fulltext


async def nachlesen(buch_id: int, file_hash: str, original: Path) -> str:
    """Liest den Text, legt ihn ab und gibt ihn über fts_content in den Suchindex (Trigger, danach wieder leer); eine fehlende
    Seitenzahl kommt gleich mit. Gibt den Text zurück; leer, wenn die Datei keinen hat."""
    e = await auswertung.text(original)
    if not e.lesbar or not e.fulltext.strip():
        return ""
    save_fulltext(file_hash, e.fulltext)
    async with db.einheit():
        await db.execute("UPDATE books SET fts_content = ?, page_count = CASE WHEN COALESCE(page_count, 0) = 0 THEN ? "
                         "ELSE page_count END, updated_at = datetime('now') WHERE id = ?", (e.fulltext[:SUCHTEXT_ZEICHEN], e.page_count, buch_id))
        await db.execute("UPDATE books SET fts_content = '' WHERE id = ?", (buch_id,))
    return e.fulltext
