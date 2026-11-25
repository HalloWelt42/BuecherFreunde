"""Text, Umschlag und Angaben aus einer Buchdatei, in einem eigenen Prozess: die App antwortet weiter, und stürzt eine
kaputte Datei den Prozess ab, betrifft das nur diese eine Aufnahme. Immer nur ein Buch zugleich (wenig Arbeitsspeicher)."""

from __future__ import annotations

import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from pathlib import Path

ZEITGRENZE_S = 30 * 60
_prozess: ProcessPoolExecutor | None = None


@dataclass
class Ergebnis:
    title: str = ""
    author: str = ""
    isbn: str = ""
    publisher: str = ""
    year: int | None = None
    language: str = ""
    description: str = ""
    page_count: int = 0
    fulltext: str = ""
    cover_data: bytes | None = None
    grund: str = ""                 # warum die Datei nicht lesbar ist; leer: lesbar

    @property
    def lesbar(self) -> bool:
        return not self.grund


def _lesen(pfad: str) -> Ergebnis:
    from backend.app.services.processor import process_book

    datei = Path(pfad)
    r = process_book(datei)
    e = Ergebnis(**{k: getattr(r, k) for k in ("title", "author", "isbn", "publisher", "year", "language", "description", "page_count", "fulltext", "cover_data")})
    inhalt = bool(e.fulltext.strip() or e.page_count)
    if not inhalt:
        e.grund = "Die Datei lässt sich nicht lesen" + (f" ({r.error})" if r.error else "")
    e.title = (e.title or "").strip() or datei.stem.replace("_", " ").replace("-", " ").strip()
    return e


async def auswerten(pfad: Path) -> Ergebnis:
    global _prozess
    if _prozess is None:
        _prozess = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"), max_tasks_per_child=20)
    try:
        return await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(_prozess, _lesen, str(pfad)), ZEITGRENZE_S)
    except BrokenProcessPool:
        _prozess = None
        return Ergebnis(grund="Die Datei bringt den Leser zum Absturz")
    except TimeoutError:
        schliessen()
        return Ergebnis(grund="Das Lesen dauerte länger als eine halbe Stunde")


def schliessen() -> None:
    global _prozess
    if _prozess is not None:
        _prozess.shutdown(wait=False, cancel_futures=True)
        _prozess = None
