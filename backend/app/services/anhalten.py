"""Lange Läufe anhalten: sofort, auch mitten im Warten auf eine Quelle."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any


class Anhalter:
    def __init__(self) -> None:
        self._halt: asyncio.Event | None = None

    def beginne(self) -> None:
        self._halt = asyncio.Event()

    def halte(self) -> None:
        if self._halt is not None:
            self._halt.set()

    @property
    def gehalten(self) -> bool:
        return self._halt is not None and self._halt.is_set()

    async def bis(self, aufgabe: Coroutine[Any, Any, Any]) -> Any:
        """Das Ergebnis der Aufgabe, oder None, wenn vorher angehalten wurde."""
        assert self._halt is not None, "erst beginne()"
        lauf, halt = asyncio.ensure_future(aufgabe), asyncio.ensure_future(self._halt.wait())
        try:
            await asyncio.wait({lauf, halt}, return_when=asyncio.FIRST_COMPLETED)
            return lauf.result() if lauf.done() else None
        finally:
            halt.cancel()
            if not lauf.done():
                lauf.cancel()
