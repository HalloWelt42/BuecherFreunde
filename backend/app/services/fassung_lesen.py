"""Lesen einer Fassung (BF-71): welche Fassung "Lesen" auf der Buchseite öffnet, und wo man in einer Übersetzung liest.

Die Wahl steht je Profil und Buch in `user_book_data.fassung_wahl` (leer: das Original, sonst die Sprache der Fassung), so gilt sie
auf jedem Gerät. Der Lesestand einer Übersetzung steht je Profil in `fassung_lesestand`, getrennt vom Lesestand des Originals
(`user_book_data.reading_position`): Stellen einer Fassung passen nicht ins Original, bis der gemeinsame Lesestand über die
Blöcke kommt (docs/neubau/UEBERSETZUNG.md, Lesen). Notizen, Markierungen und die Vorlesestelle hängen nur am Original.
Beides gehört dem Profil (BF-78)."""

from __future__ import annotations

from backend.app.core.database import db
from backend.app.models.fassung import Lesestand


async def wahl(profil_id: str, buch_id: int) -> str:
    """Die Sprache der gewählten Fassung; leer: das Original."""
    z = await db.fetch_one("SELECT fassung_wahl FROM user_book_data WHERE profil_id = ? AND book_id = ?", (profil_id, buch_id))
    return (z["fassung_wahl"] if z else "") or ""


async def waehlen(profil_id: str, buch_id: int, sprache: str | None) -> None:
    await db.execute("""INSERT INTO user_book_data (profil_id, book_id, fassung_wahl) VALUES (?, ?, ?)
                        ON CONFLICT(profil_id, book_id) DO UPDATE SET fassung_wahl = excluded.fassung_wahl""", (profil_id, buch_id, sprache or ""))


async def lesestand(profil_id: str, fid: int) -> Lesestand:
    z = await db.fetch_one("SELECT position, gelesen_am FROM fassung_lesestand WHERE profil_id = ? AND fassung_id = ?", (profil_id, fid))
    return Lesestand(**z) if z else Lesestand()


async def merken(profil_id: str, fid: int, position: str) -> Lesestand:
    await db.execute("""INSERT INTO fassung_lesestand (profil_id, fassung_id, position, gelesen_am)
                        VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                        ON CONFLICT(profil_id, fassung_id) DO UPDATE SET position = excluded.position, gelesen_am = excluded.gelesen_am""",
                     (profil_id, fid, position))
    return await lesestand(profil_id, fid)
