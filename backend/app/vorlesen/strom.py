"""Der Strom des Vorlesens bis zu seinem ersten Satz. Solange er wartet, ist noch keine Antwort gesendet, und der Server merkt nicht
von selbst, dass der Leser geht: erst eine gesendete Antwort hört auf das Schließen der Verbindung. Darum schaut `erste_zeile`
nach. Geht der Leser, endet die Anfrage an die Vertonung und mit ihr ihr Auftrag in der Leitstelle; sonst blieb jeder Neuversuch
des Lesers als wartender Auftrag stehen und rechnete später ins Leere (BF-121)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable

BLICK_S = 1.0
"""So oft schaut der Server nach, ob der Leser noch da ist, solange der erste Satz aussteht"""
GEGANGEN = 499
"""Status, wenn der Leser vor dem ersten Satz gegangen ist (so schreibt es auch der Vorbau); niemand liest ihn mehr"""


class Gegangen(Exception):
    """Der Leser ist gegangen, bevor der erste Satz kam."""


async def erste_zeile(zeilen: AsyncGenerator[bytes, None], gegangen: Callable[[], Awaitable[bool]], blick_s: float = BLICK_S) -> bytes:
    """Die erste Zeile von `zeilen`, leer, wenn es keine gibt. Geht der Leser vorher (`gegangen`), wird `zeilen` geschlossen und
    `Gegangen` folgt; ein Fehler vor dem ersten Satz kommt so, wie `zeilen` ihn wirft."""
    naechste = asyncio.ensure_future(anext(zeilen))
    try:
        while True:
            fertig, _ = await asyncio.wait({naechste}, timeout=blick_s)
            if fertig:
                try:
                    return naechste.result()
                except StopAsyncIteration:
                    return b""
            if await gegangen():
                raise Gegangen
    except BaseException:
        naechste.cancel()
        await asyncio.wait({naechste})
        await zeilen.aclose()
        raise
