"""Der Eingangsordner: was dort abgelegt wird, kommt von selbst in die Bibliothek, auf demselben Weg wie beim Hochladen. Die
Datei zieht dabei um, sie wird nicht kopiert. Was es schon gibt oder nicht lesbar ist, bleibt liegen.

Mit Kellerwolke liegt er dort (`Apps/BücherFreunde/Eingangsordner`), ohne sie auf dem Gerät (`EINGANGSORDNER_DIR`),
gleichwertig: jede Minute nachsehen, auch Unterordner, und dieselbe Liste mit dem Stand jeder Datei. Auf dem Gerät wird
eine Datei erst genommen, wenn sie eine Weile unverändert liegt (sie könnte noch geschrieben werden)."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from pathlib import Path

from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.annahme import ordner
from backend.app.annahme.dienst import annahme
from backend.app.core.config import settings
from backend.app.core.database import db

logger = logging.getLogger("buecherfreunde.eingangsordner")
ALLE_S = 60
RUHIG_S = 10                     # so lange muss eine Datei auf dem Gerät unverändert liegen, bevor sie genommen wird


def pfad() -> str:
    return f"{settings.ablage_ordner}/Eingangsordner" if wolke.bereit else str(settings.eingangsordner_dir)


def einrichten() -> None:
    """Ohne Kellerwolke: den Ordner auf dem Gerät anlegen, wenn es ihn noch nicht gibt."""
    if not wolke.bereit:
        try:
            settings.eingangsordner_dir.mkdir(parents=True, exist_ok=True)
        except OSError as f:
            logger.warning("Eingangsordner %s nicht anzulegen: %s", settings.eingangsordner_dir, f)


def _auf_dem_geraet() -> list[Path]:
    """Die Dateien im Ordner auf dem Gerät, die schon eine Weile unverändert liegen."""
    jetzt = time.time()
    return [f for f in ordner.dateien(settings.eingangsordner_dir, alle_formate=True) if jetzt - f.stat().st_mtime >= RUHIG_S]


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
        return await _inhalt_auf_dem_geraet()
    dateien = []
    async for k in _dateien():
        z = await db.fetch_one("SELECT stand, text, buch_id FROM aufnahme WHERE knoten = ? ORDER BY id DESC", (k["id"],))
        dateien.append({"name": k["name"], "groesse": k["groesse"], "stand": z["stand"] if z else "neu", "text": z["text"] if z else "Wird gleich aufgenommen", "buch_id": z["buch_id"] if z else None})
    return {"bereit": True, "pfad": pfad(), "dateien": dateien}


async def _inhalt_auf_dem_geraet() -> dict:
    ort = settings.eingangsordner_dir
    if not ort.is_dir():
        return {"bereit": False, "pfad": str(ort), "dateien": []}
    dateien = []
    for f in await asyncio.to_thread(ordner.dateien, ort, True):
        z = await db.fetch_one("SELECT stand, text, buch_id FROM aufnahme WHERE pfad = ? ORDER BY id DESC", (str(f),))
        dateien.append({"name": f.name, "groesse": f.stat().st_size, "stand": z["stand"] if z else "neu",
                        "text": z["text"] if z else "Wird gleich aufgenommen", "buch_id": z["buch_id"] if z else None})
    return {"bereit": True, "pfad": str(ort), "dateien": dateien}


async def aufnehmen() -> int:
    """Neues im Ordner aufnehmen; liefert, wie viele Dateien dazukamen."""
    if not wolke.bereit:
        if not settings.eingangsordner_dir.is_dir():
            return 0
        return await annahme.aus_ordner(await asyncio.to_thread(_auf_dem_geraet), "eingangsordner")
    neu = 0
    if wolke.bereit:
        async for k in _dateien():
            if await db.fetch_one("SELECT 1 AS da FROM aufnahme WHERE knoten = ?", (k["id"],)) is None:
                await annahme.aus_wolke(k)
                neu += 1
    return neu


async def laufen() -> None:
    """Im Hintergrund: Abgelegtes wird ohne Zutun erkannt."""
    einrichten()
    while True:
        try:
            if neu := await aufnehmen():
                logger.info("%d Dateien im Eingangsordner gefunden", neu)
        except WolkeFehler as f:
            logger.info("Eingangsordner: %s", f.meldung)
        except Exception:                                   # noqa: BLE001 - darf nie still enden
            logger.exception("Eingangsordner")
        await asyncio.sleep(ALLE_S)
