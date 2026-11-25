"""Der Takt eines Rechners: eine Anfrage zugleich, Abstand dazwischen, höchstens so viele je Minute. Wer mit Vorrang
wartet, kommt vor den Hintergrundläufen dran; die dürfen von der Minute nur einen Teil verbrauchen."""

from __future__ import annotations

import asyncio
import heapq
import itertools
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from backend.app.quellen.vorrang import Vorrang

HINTERGRUND_ANTEIL = 0.6
MINUTE_S = 60.0


@dataclass(order=True)
class Karte:
    """Ein Platz in der Schlange."""

    vorrang: Vorrang
    nummer: int
    fertig: bool = field(default=False, compare=False)


class Takt:
    def __init__(self, abstand: Callable[[], float], je_minute: Callable[[], int], uhr: Callable[[], float] = time.monotonic) -> None:
        self._abstand, self._je_minute, self._uhr = abstand, je_minute, uhr
        self._schlange: list[Karte] = []
        self._nummern = itertools.count()
        self._belegt = False
        self._zuletzt = float("-inf")
        self._minute: deque[float] = deque()
        self._neu = asyncio.Condition()

    def karte(self, vorrang: Vorrang) -> Karte:
        return Karte(vorrang, next(self._nummern))

    def wartet(self, vorrang: Vorrang) -> float:
        """So lange darf mit diesem Vorrang noch nicht gefragt werden."""
        jetzt = self._uhr()
        while self._minute and self._minute[0] <= jetzt - MINUTE_S:
            self._minute.popleft()
        pause = self._zuletzt + self._abstand() - jetzt
        grenze = self._je_minute()
        if vorrang is Vorrang.HINTERGRUND:
            grenze = max(1, int(grenze * HINTERGRUND_ANTEIL))
        if len(self._minute) >= grenze:
            pause = max(pause, self._minute[-grenze] + MINUTE_S - jetzt)
        return max(0.0, pause)

    async def vorziehen(self, karte: Karte, vorrang: Vorrang) -> None:
        """Ein Mensch wartet jetzt auch auf diese Anfrage."""
        if vorrang >= karte.vorrang or karte.fertig:
            return
        async with self._neu:
            karte.vorrang = vorrang
            heapq.heapify(self._schlange)
            self._neu.notify_all()

    @asynccontextmanager
    async def an_der_reihe(self, karte: Karte) -> AsyncIterator[None]:
        await self._anstellen(karte)
        try:
            yield
        finally:
            self._zuletzt = self._uhr()
            self._minute.append(self._zuletzt)
            await self._freigeben()

    async def _anstellen(self, karte: Karte) -> None:
        async with self._neu:
            heapq.heappush(self._schlange, karte)
            self._neu.notify_all()
            try:
                while not await self._dran(karte):
                    pass
            except BaseException:
                self._schlange.remove(karte)
                heapq.heapify(self._schlange)
                self._neu.notify_all()
                raise
            heapq.heappop(self._schlange)
            self._belegt, karte.fertig = True, True

    async def _dran(self, karte: Karte) -> bool:
        """Wahr, wenn die Karte vorn steht und fragen darf; sonst warten, bis sich etwas ändert."""
        if self._belegt or self._schlange[0] is not karte:
            await self._neu.wait()
            return False
        pause = self.wartet(karte.vorrang)
        if pause <= 0:
            return True
        try:
            await asyncio.wait_for(self._neu.wait(), pause)
        except TimeoutError:
            pass
        return False

    async def _freigeben(self) -> None:
        async with self._neu:
            self._belegt = False
            self._neu.notify_all()
