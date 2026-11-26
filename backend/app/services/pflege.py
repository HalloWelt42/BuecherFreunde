"""Pflege im Hintergrund: Wissensstand neuer Bücher, Codestellen der Bücher, die noch keine haben (je Runde nur wenige),
Sicherung nach der Regel (auch in die Kellerwolke, wenn eingeschaltet, ablage/sicherungen.py), Begleiter, deren Angaben sich
geändert haben (Titel, Autor; Persönliches führt einrichtung/nachfuehren.py laufend nach), und abgelaufene Antworten der Quellen."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from backend.app.ablage import auszug, sicherungen
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.annahme.dienst import annahme
from backend.app.codestellen.dienst import codestellen
from backend.app.codestellen.vorpruefung import vorpruefer
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.quellen.abruf import abruf
from backend.app.services import sicherung

logger = logging.getLogger("buecherfreunde.pflege")
WISSEN_S = 10 * 60
NACHTS = range(3, 5)
BEGLEITER_JE_NACHT = 300
# Geänderte Angaben (Titel, Autor, Art ...); Persönliches führt der Auftrag "Auszüge nachführen" laufend nach (BF-82)
GEAENDERT = """
SELECT b.id, b.hash, a.knoten FROM books b JOIN ablage_datei a ON a.hash = b.hash
WHERE b.updated_at > a.abgelegt_am
ORDER BY b.id LIMIT ?
"""


async def sichern() -> None:
    lauf = await asyncio.to_thread(sicherung.sichern, sicherung.Anlass.REGELMAESSIG)
    if lauf.neu:
        await sicherungen.ablegen(lauf.datei)


async def begleiter() -> int:
    zeilen = await db.fetch_all(GEAENDERT, (BEGLEITER_JE_NACHT,)) if wolke.bereit else []
    for z in zeilen:
        kennung = await wolke.auszug_schreiben(z["knoten"], await auszug.bauen(z["id"], z["hash"]))
        await db.execute("UPDATE ablage_datei SET begleiter = ?, abgelegt_am = datetime('now') WHERE hash = ?", (kennung, z["hash"]))
        await db.commit()
        await asyncio.sleep(.5)
    return len(zeilen)


async def laufen() -> None:
    letzte_nacht = None
    while True:
        try:
            await annahme.wissen_pruefen()
            await codestellen.nachlauf(settings.codestellen_je_runde)
            vorpruefer.anstossen()
            jetzt = datetime.now()
            if jetzt.hour in NACHTS and letzte_nacht != jetzt.date():
                letzte_nacht = jetzt.date()
                logger.info("%d gemerkte Antworten der Quellen abgelaufen", await abruf().vorrat.aufraeumen())
                await sichern()
                logger.info("%d Begleiter erneuert", await begleiter())
        except (WolkeFehler, OSError) as f:
            logger.warning("Pflege: %s", f)
        except Exception:                                   # noqa: BLE001 - Pflege darf nie still enden
            logger.exception("Pflege")
        await asyncio.sleep(WISSEN_S)
