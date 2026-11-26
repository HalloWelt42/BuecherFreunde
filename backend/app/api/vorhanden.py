"""Gibt es das? Sonst 404 mit Namen (BF-50). Ein Weg, der etwas ändert oder löscht, das es nicht gibt, meldet das, statt
still mit 200 zu antworten."""

from __future__ import annotations

from typing import Any

import aiosqlite
from fastapi import HTTPException

from backend.app.core.database import db

BUCH_FEHLT = "Buch nicht gefunden"


async def eintrag(tabelle: str, nr: int, meldung: str, spalten: str = "*") -> dict[str, Any]:
    """Die Zeile mit dieser Nummer; `tabelle` und `spalten` kommen nur aus dem Code."""
    z = await db.fetch_one(f"SELECT {spalten} FROM {tabelle} WHERE id = ?", (nr,))
    if z is None:
        raise HTTPException(status_code=404, detail=meldung)
    return z


async def buch(nr: int, spalten: str = "id") -> dict[str, Any]:
    return await eintrag("books", nr, BUCH_FEHLT, spalten)


def getroffen(c: aiosqlite.Cursor, meldung: str) -> None:
    """Nach UPDATE oder DELETE: hat es etwas getroffen?"""
    if c.rowcount == 0:
        raise HTTPException(status_code=404, detail=meldung)
