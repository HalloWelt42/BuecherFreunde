"""Pflege im Hintergrund: Wissensstand neuer Bücher, Sicherung nach der Regel (auch in die Kellerwolke) und Begleiter, deren
Angaben sich geändert haben (Notizen, Markierungen, Lesestand, Titel)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.annahme.dienst import annahme
from backend.app.annahme.eintragen import auszug
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services import sicherung

logger = logging.getLogger("buecherfreunde.pflege")
WISSEN_S = 10 * 60
NACHTS = range(3, 5)
BEGLEITER_JE_NACHT = 300
GEAENDERT = """
SELECT b.id, b.hash, a.knoten FROM books b JOIN ablage_datei a ON a.hash = b.hash
LEFT JOIN user_book_data u ON u.book_id = b.id
WHERE b.updated_at > a.abgelegt_am OR COALESCE(u.last_read_at, '') > a.abgelegt_am
   OR EXISTS (SELECT 1 FROM book_notes n WHERE n.book_id = b.id AND n.updated_at > a.abgelegt_am)
   OR EXISTS (SELECT 1 FROM book_highlights h WHERE h.book_id = b.id AND h.created_at > a.abgelegt_am)
ORDER BY b.id LIMIT ?
"""


async def sichern() -> None:
    lauf = await asyncio.to_thread(sicherung.sichern, sicherung.Anlass.REGELMAESSIG)
    if lauf.neu and wolke.bereit:
        await wolke.ordner(f"{settings.ablage_ordner}/Sicherung")
        await wolke.datei_schreiben(f"{settings.ablage_ordner}/Sicherung/{lauf.datei.name}", lauf.datei)
        logger.info("Sicherung %s liegt in der Kellerwolke", lauf.datei.name)


async def begleiter() -> int:
    zeilen = await db.fetch_all(GEAENDERT, (BEGLEITER_JE_NACHT,)) if wolke.bereit else []
    for z in zeilen:
        kennung = await wolke.auszug_schreiben(z["knoten"], await auszug(z["id"], z["hash"]))
        await db.execute("UPDATE ablage_datei SET begleiter = ?, abgelegt_am = datetime('now') WHERE hash = ?", (kennung, z["hash"]))
        await db.commit()
        await asyncio.sleep(.5)
    return len(zeilen)


async def laufen() -> None:
    letzte_nacht = None
    while True:
        try:
            await annahme.wissen_pruefen()
            jetzt = datetime.now()
            if jetzt.hour in NACHTS and letzte_nacht != jetzt.date():
                letzte_nacht = jetzt.date()
                await sichern()
                logger.info("%d Begleiter erneuert", await begleiter())
        except (WolkeFehler, OSError) as f:
            logger.warning("Pflege: %s", f)
        except Exception:                                   # noqa: BLE001 - Pflege darf nie still enden
            logger.exception("Pflege")
        await asyncio.sleep(WISSEN_S)
