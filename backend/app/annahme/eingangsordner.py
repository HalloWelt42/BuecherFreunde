"""Der Eingangsordner in der Kellerwolke: was dort abgelegt wird, kommt von selbst in die Bibliothek, auf demselben Weg wie
beim Hochladen. Die Datei zieht dabei um, sie wird nicht kopiert. Was es schon gibt oder nicht lesbar ist, bleibt liegen."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.annahme.dienst import annahme
from backend.app.core.config import settings
from backend.app.core.database import db

logger = logging.getLogger("buecherfreunde.eingangsordner")
ALLE_S = 60


def pfad() -> str:
    return f"{settings.ablage_ordner}/Eingangsordner"


async def _dateien() -> AsyncIterator[dict]:
    """Alle Dateien im Ordner, auch in Unterordnern."""
    offen = [(await wolke.ordner(pfad()))["id"]]
    while offen:
        async for k in wolke.kinder(offen.pop()):
            if k["typ"] == "ordner":
                offen.append(k["id"])
            elif k["typ"] == "datei" and k.get("sha256"):      # ohne Prüfsumme schreibt die Kellerwolke noch
                yield k


async def inhalt() -> dict:
    """Was im Ordner liegt und wie es damit steht, für die Oberfläche."""
    if not wolke.bereit:
        return {"bereit": False, "pfad": pfad(), "dateien": []}
    dateien = []
    async for k in _dateien():
        z = await db.fetch_one("SELECT stand, text, buch_id FROM aufnahme WHERE knoten = ? ORDER BY id DESC", (k["id"],))
        dateien.append({"name": k["name"], "groesse": k["groesse"], "stand": z["stand"] if z else "neu", "text": z["text"] if z else "Wird gleich aufgenommen", "buch_id": z["buch_id"] if z else None})
    return {"bereit": True, "pfad": pfad(), "dateien": dateien}


async def aufnehmen() -> int:
    """Neues im Ordner aufnehmen; liefert, wie viele Dateien dazukamen."""
    neu = 0
    if wolke.bereit:
        async for k in _dateien():
            if await db.fetch_one("SELECT 1 AS da FROM aufnahme WHERE knoten = ?", (k["id"],)) is None:
                await annahme.aus_wolke(k)
                neu += 1
    return neu


async def laufen() -> None:
    """Im Hintergrund: Abgelegtes wird ohne Zutun erkannt."""
    while True:
        try:
            if neu := await aufnehmen():
                logger.info("%d Dateien im Eingangsordner gefunden", neu)
        except WolkeFehler as f:
            logger.info("Eingangsordner: %s", f.meldung)
        except Exception:                                   # noqa: BLE001 - darf nie still enden
            logger.exception("Eingangsordner")
        await asyncio.sleep(ALLE_S)
