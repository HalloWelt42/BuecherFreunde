"""Codestellen je Buch: einmal im Hintergrund erkannt, als Begleiter codestellen.json neben seiten.json gemerkt.

Die Stellen selbst stehen nur im Begleiter; die Tabelle `codestellen` führt Buch für Buch, mit welcher Fassung erkannt
wurde und wie weit die Vorprüfung ist. Erkannt wird in einem eigenen Prozess, ein Buch nach dem anderen: wer ein Buch öffnet,
kommt zuerst dran, dann neue Bücher, dann der schonende Nachlauf der Pflege (je Runde nur wenige Bücher, die noch keine
Erkennung haben). Ist das Original gerade nicht zu holen, bleibt das Buch für eine spätere Runde."""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
from collections.abc import Awaitable, Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from typing import Literal

from backend.app.codestellen.erkennung import FORMATE, erkennen
from backend.app.codestellen.modelle import FASSUNG, Begleiter
from backend.app.core.database import db
from backend.app.services.storage import get_original_file, get_sidecar_path

logger = logging.getLogger("buecherfreunde.codestellen")
BEGLEITER = "codestellen.json"
ZEITGRENZE_S = 30 * 60                     # so lange darf das Lesen einer Datei dauern (wie in der Annahme)

Stand = Literal["erkannt", "ausstehend", "ohne"]


def begleiter_lesen(file_hash: str) -> Begleiter | None:
    """Der Begleiter, wenn es ihn in der aktuellen Fassung gibt."""
    pfad = get_sidecar_path(file_hash, BEGLEITER)
    try:
        b = Begleiter.model_validate_json(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return b if b.fassung == FASSUNG else None


def begleiter_schreiben(file_hash: str, b: Begleiter) -> None:
    pfad = get_sidecar_path(file_hash, BEGLEITER)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    teil = pfad.with_name(f".{BEGLEITER}.teil")
    teil.write_text(b.model_dump_json(), encoding="utf-8")
    teil.replace(pfad)


def _im_prozess(pfad: str, fmt: str) -> str:
    return erkennen(Path(pfad), fmt).model_dump_json()


class Codestellen:
    def __init__(self) -> None:
        self._vorrang: list[int] = []
        self._reihe: list[int] = []
        self._neu = asyncio.Event()
        self._lauf: asyncio.Task | None = None
        self._prozess: ProcessPoolExecutor | None = None
        self.erkannt: list[Callable[[int], Awaitable[None]]] = []     # wer nach einer Erkennung Bescheid bekommt

    # -- Leben -----------------------------------------------------------------------------------------------------------
    def starten(self) -> None:
        self._neu = asyncio.Event()
        self._lauf = asyncio.create_task(self._arbeiten())

    async def stoppen(self) -> None:
        if self._lauf is not None:
            self._lauf.cancel()
            self._lauf = None
        if self._prozess is not None:
            self._prozess.shutdown(wait=False, cancel_futures=True)
            self._prozess = None

    # -- Aufträge --------------------------------------------------------------------------------------------------------
    def vormerken(self, buch: int, vorrang: bool = False) -> None:
        if buch in self._vorrang or (buch in self._reihe and not vorrang):
            return
        if vorrang:
            if buch in self._reihe:
                self._reihe.remove(buch)
            self._vorrang.append(buch)
        else:
            self._reihe.append(buch)
        self._neu.set()

    @property
    def wartend(self) -> int:
        return len(self._vorrang) + len(self._reihe)

    async def nachlauf(self, anzahl: int) -> int:
        """Pflege: höchstens `anzahl` Bücher ohne Erkennung (oder mit älterer Fassung) vormerken, neueste zuerst; nie
        mehr, solange die vorigen noch warten."""
        frei = anzahl - len(self._reihe)
        if frei <= 0:
            return 0
        formate = tuple(FORMATE)
        zeilen = await db.fetch_all(
            f"""SELECT b.id FROM books b LEFT JOIN codestellen c ON c.buch_id = b.id
                WHERE (c.buch_id IS NULL OR c.fassung < ?) AND lower(b.file_format) IN ({",".join("?" * len(formate))})
                ORDER BY b.id DESC LIMIT ?""", (FASSUNG, *formate, frei + len(self._vorrang) + len(self._reihe)))
        neu = [z["id"] for z in zeilen if z["id"] not in self._reihe and z["id"] not in self._vorrang][:frei]
        for buch in neu:
            self.vormerken(buch)
        return len(neu)

    async def stellen(self, buch: int) -> tuple[Stand, Begleiter | None]:
        """Die erkannten Stellen eines Buchs; fehlen sie, kommt das Buch sofort an die Reihe."""
        z = await db.fetch_one("SELECT hash, file_format FROM books WHERE id = ?", (buch,))
        if z is None:
            raise KeyError(buch)
        if (z["file_format"] or "").lower() not in FORMATE:
            return "ohne", None
        begleiter = await asyncio.to_thread(begleiter_lesen, z["hash"])
        if begleiter is None:
            self.vormerken(buch, vorrang=True)
            return "ausstehend", None
        return "erkannt", begleiter

    # -- Arbeit ----------------------------------------------------------------------------------------------------------
    async def _arbeiten(self) -> None:
        while True:
            if not (self._vorrang or self._reihe):
                self._neu.clear()
                await self._neu.wait()
                continue
            buch = (self._vorrang or self._reihe).pop(0)
            try:
                await self.erkennen(buch)
            except asyncio.CancelledError:
                raise
            except Exception:                              # noqa: BLE001 - ein Buch darf die übrigen nie aufhalten
                logger.exception("Codestellen von Buch %d", buch)

    async def erkennen(self, buch: int) -> Begleiter | None:
        """Ein Buch erkennen, Begleiter und Tabelle schreiben. None, wenn das Original gerade nicht zu holen ist."""
        z = await db.fetch_one("SELECT hash, file_format FROM books WHERE id = ?", (buch,))
        if z is None:
            return None
        fmt = (z["file_format"] or "").lower()
        if fmt not in FORMATE:
            return None
        pfad = await asyncio.to_thread(get_original_file, z["hash"])
        if pfad is None:
            logger.info("Codestellen von Buch %d: Original gerade nicht zu holen, später", buch)
            return None
        begleiter = await self.lesen(pfad, fmt)
        await asyncio.to_thread(begleiter_schreiben, z["hash"], begleiter)
        await db.execute(
            """INSERT INTO codestellen(buch_id, fassung, anzahl, grund, erkannt_am, vorgeprueft)
               VALUES (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'), '')
               ON CONFLICT(buch_id) DO UPDATE SET fassung = excluded.fassung, anzahl = excluded.anzahl, grund = excluded.grund,
               erkannt_am = excluded.erkannt_am, vorgeprueft = ''""",
            (buch, FASSUNG, len(begleiter.stellen), begleiter.grund))
        await db.commit()
        logger.info("Codestellen von Buch %d: %d erkannt%s", buch, len(begleiter.stellen), f" ({begleiter.grund})" if begleiter.grund else "")
        for melden in self.erkannt:
            await melden(buch)
        return begleiter

    async def lesen(self, pfad: Path, fmt: str) -> Begleiter:
        """In einem eigenen Prozess: die App antwortet weiter, und eine Datei, die den Leser abstürzen lässt, trifft nur sie."""
        if self._prozess is None:
            self._prozess = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"), max_tasks_per_child=10)
        art = FORMATE[fmt]
        try:
            roh = await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(self._prozess, _im_prozess, str(pfad), fmt), ZEITGRENZE_S)
        except BrokenProcessPool:
            self._prozess = None
            return Begleiter(format=art, grund="Die Datei bringt die Erkennung zum Absturz")
        except TimeoutError:
            if self._prozess is not None:
                self._prozess.shutdown(wait=False, cancel_futures=True)
                self._prozess = None
            return Begleiter(format=art, grund="Die Erkennung dauerte länger als eine halbe Stunde")
        return Begleiter.model_validate_json(roh)


codestellen = Codestellen()
