"""Schritt Katalog (BF-82): der mitgelieferte Katalog, leer beginnen oder später aus dem Bestand vorschlagen. Angenommen wird wie
unter Einstellungen, Katalog (`katalog/kategorien.annehmen`): gleicher Schlüssel ändert, sonst anlegen, gelöscht wird nichts.
"Aus dem Bestand" beginnt mit dem mitgelieferten und stößt nach dem Abschluss den Entwurf aus dem Bestand an, wenn Bücher da sind."""

from __future__ import annotations

from backend.app.core import einstellungen
from backend.app.core.database import db
from backend.app.katalog import entwurf, kategorien
from backend.app.katalog.bestandslauf import bestandslauf

WAHL = "einrichtung_katalog"                  # app_settings: was im Schritt gewählt ist
NAMEN = {"standard": "Mitgelieferter Katalog", "leer": "Leer begonnen", "bestand": "Mitgelieferter Katalog, Vorschlag aus dem Bestand"}


async def anwenden(wahl: str) -> str:
    if wahl in ("standard", "bestand"):
        await kategorien.annehmen(entwurf.aus_standard())
    await einstellungen.schreiben(WAHL, wahl)
    return NAMEN[wahl]


async def nach_dem_abschluss() -> None:
    if await einstellungen.lesen(WAHL) == "bestand" and await db.fetch_one("SELECT 1 FROM books LIMIT 1"):
        await bestandslauf.beginnen()
