"""Gemeinfreie Bücher (Project Gutenberg) als Quelle der Annahme: die Datei holen und danach Nummer, Regal "Gutenberg" und
Umschlag eintragen. Gesucht wird über api/gutenberg.py, aufgenommen wie jede andere Datei (annahme/dienst.py)."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from pathlib import Path

from backend.app.core.database import db
from backend.app.quellen.gutenberg import download_buch, download_cover
from backend.app.services.storage import save_cover

logger = logging.getLogger("buecherfreunde.gemeinfrei")
QUELLE = "gemeinfrei"


def herkunft(z: dict) -> dict:
    return json.loads(z["herkunft"] or "{}")


async def holen(z: dict, ziel: Path) -> Path:
    """Die Datei an `ziel` (Zwischenspeicher der Aufnahme); wirft QuelleFehler mit dem Grund."""
    h = herkunft(z)
    vorlaeufig = await download_buch(int(h.get("gutenberg_id") or 0), str(h.get("download_url") or ""))
    ziel.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(shutil.move, vorlaeufig, ziel)
    return ziel


async def schon_da(gutenberg_id: int) -> dict | None:
    return await db.fetch_one("SELECT id, title FROM books WHERE gutenberg_id = ?", (gutenberg_id,)) if gutenberg_id else None


async def _regal() -> int:
    await db.execute("""INSERT OR IGNORE INTO categories (name, slug, description, icon, color, spezial)
                        VALUES ('Gutenberg', 'gutenberg', 'Gemeinfreie Bücher von Project Gutenberg', 'fa-landmark-dome', '#8b5cf6', 1)""")
    return (await db.fetch_one("SELECT id FROM categories WHERE slug = 'gutenberg'"))["id"]


async def nachher(z: dict, buch: int, file_hash: str) -> None:
    """Nummer bei Gutenberg, Regal und, wenn es einen gibt, der Umschlag des Verzeichnisses."""
    h = herkunft(z)
    bild = await download_cover(str(h["cover_url"])) if h.get("cover_url") else None        # vor dem Schreiben, es kann dauern
    if bild:
        await asyncio.to_thread(save_cover, file_hash, bild)
    async with db.einheit():
        await db.execute("UPDATE books SET gutenberg_id = ? WHERE id = ?", (int(h.get("gutenberg_id") or 0) or None, buch))
        await db.execute("INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'import')", (buch, await _regal()))
        if bild:
            await db.execute("UPDATE books SET cover_path = 'cover.jpg' WHERE id = ?", (buch,))
