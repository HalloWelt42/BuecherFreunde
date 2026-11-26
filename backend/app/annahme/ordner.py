"""Ordner auf dem Gerät als Quelle der Annahme (Einlese-Ordner und externe Sammlung): welche Dateien dort liegen und, für die
Vorschau, welche es schon gibt. Aufgenommen wird über annahme/dienst.py (aus_ordner)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from backend.app.core.database import db
from backend.app.services.storage import SUPPORTED_FORMATS, compute_hash


def dateien(verzeichnis: Path, alle_formate: bool = False) -> list[Path]:
    """Die lesbaren Formate im Ordner, auch in Unterordnern (`alle_formate`: jede Datei, damit Fremdes mit Grund in der Liste
    steht); ohne Prüfsumme, kehrt sofort zurück. Verborgene Dateien zählen nie."""
    if not verzeichnis.is_dir():
        return []
    return [f for f in sorted(verzeichnis.rglob("*")) if f.is_file() and not f.name.startswith(".")
            and (alle_formate or f.suffix.lower() in SUPPORTED_FORMATS)]


async def vorschau(verzeichnis: Path) -> list[dict]:
    """Je Datei Name, Ort, Größe, Format und ob es den Inhalt schon gibt (Prüfsumme in einem Faden)."""
    aus = []
    for f in await asyncio.to_thread(dateien, verzeichnis):
        try:
            summe = await asyncio.to_thread(compute_hash, f)
        except OSError:
            continue
        da = await db.fetch_one("SELECT title FROM books WHERE hash = ?", (summe,))
        aus.append({"pfad": str(f), "name": f.name, "groesse": f.stat().st_size, "format": f.suffix.lower(), "hash": summe,
                    "ist_duplikat": da is not None, "bestehendes_buch": da["title"] if da else None})
    return aus
