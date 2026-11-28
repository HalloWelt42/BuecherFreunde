"""Ein eigener Prozess für schwere Arbeit an einer Datei (Lesen beim Hinzufügen, Codestellen), mit Grenzen (BF-120).

Stürzt eine Datei den Prozess ab, betrifft das nur dieses eine Buch, die App antwortet weiter. Dazu zwei Grenzen:
- Speicher: Jeder Arbeitsprozess begrenzt seinen Adressraum selbst (RLIMIT_AS, `arbeitsprozess_speicher_mb`). Auf dem Pi ist
  die Speichergrenze für Container abgeschaltet, eine Grenze im Compose griffe dort nicht; ohne diese hier füllte eine einzige
  PDF-Seite alle 16 GB, und der Rechner stand. Darüber scheitert die Aufgabe (MemoryError) oder der Prozess endet.
- Zeit: Nach der Frist wird der Prozess beendet, nicht nur verlassen; sonst rechnete er im Hintergrund weiter.
Immer nur eine Aufgabe zugleich je Arbeitsprozess (wenig Arbeitsspeicher)."""

from __future__ import annotations

import asyncio
import multiprocessing
import resource
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import Any, TypeVar

from backend.app.core.config import settings

T = TypeVar("T")


class Abgestuerzt(Exception):
    """Der Prozess endete mitten in der Aufgabe (Absturz in einer Bibliothek oder über der Speichergrenze)."""


class ZuLange(Exception):
    """Die Frist ist um; der Prozess ist beendet."""


def grenze_setzen(groesse: int) -> None:
    """Im Arbeitsprozess, bevor er arbeitet: der Adressraum höchstens so groß. macOS kennt diese Grenze nicht (Entwicklung);
    dort gilt nur die Frist."""
    try:
        resource.setrlimit(resource.RLIMIT_AS, (groesse, groesse))
    except (ValueError, OSError):
        pass


def grenze_mb() -> int:
    return settings.arbeitsprozess_speicher_mb


class Arbeitsprozess:
    def __init__(self, aufgaben_je_prozess: int) -> None:
        self._aufgaben = aufgaben_je_prozess          # danach ein frischer Prozess (gibt Speicher sicher zurück)
        self._pool: ProcessPoolExecutor | None = None

    def _bereit(self) -> ProcessPoolExecutor:
        if self._pool is None:
            self._pool = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"), max_tasks_per_child=self._aufgaben,
                                             initializer=grenze_setzen, initargs=(grenze_mb() * 1024 * 1024,))
        return self._pool

    async def ausfuehren(self, aufgabe: Callable[..., T], *werte: Any, frist_s: float) -> T:
        """Die Aufgabe im Arbeitsprozess; Abgestuerzt oder ZuLange, wenn es nicht gut geht. Ausnahmen der Aufgabe selbst
        (auch MemoryError) kommen, wie sie sind."""
        try:
            return await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(self._bereit(), aufgabe, *werte), frist_s)
        except BrokenProcessPool as f:
            self.beenden()
            raise Abgestuerzt() from f
        except TimeoutError as f:
            self.beenden()
            raise ZuLange() from f

    def beenden(self) -> None:
        """Den Prozess wirklich beenden, auch mitten in einer Aufgabe (shutdown allein ließe sie weiterrechnen)."""
        pool, self._pool = self._pool, None
        if pool is None:
            return
        toeten = getattr(pool, "kill_workers", None)                        # ab Python 3.14
        if toeten is not None:
            toeten()
        else:
            for p in list((getattr(pool, "_processes", None) or {}).values()):
                p.kill()
        pool.shutdown(wait=False, cancel_futures=True)
