"""Einstellungen des Nutzers in der Tabelle app_settings: je Schlüssel ein Text, gemerkt über einen Neustart.

Was ein Schlüssel bedeutet, welche Vorgabe und welche Grenzen gelten, steht bei dem, der ihn benutzt."""

from __future__ import annotations

from backend.app.core.database import db


async def lesen(schluessel: str) -> str | None:
    """Der gemerkte Wert; None, solange niemand einen gesetzt hat."""
    z = await db.fetch_one("SELECT value FROM app_settings WHERE key = ?", (schluessel,))
    return z["value"] if z else None


async def schreiben(schluessel: str, wert: str) -> None:
    await db.execute("""INSERT INTO app_settings(key, value) VALUES (?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')""", (schluessel, wert))
    await db.commit()
