"""Mensch vor Hintergrund: wer gerade wartet, kommt zuerst dran; Läufe im Hintergrund haben eine Tagesgrenze."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import IntEnum


class Vorrang(IntEnum):
    MENSCH = 0
    HINTERGRUND = 1


_vorrang: ContextVar[Vorrang] = ContextVar("vorrang", default=Vorrang.MENSCH)


def jetzt() -> Vorrang:
    return _vorrang.get()


@contextmanager
def hintergrund() -> Iterator[None]:
    """Alles in diesem Block fragt die Quellen mit niedrigem Vorrang."""
    marke = _vorrang.set(Vorrang.HINTERGRUND)
    try:
        yield
    finally:
        _vorrang.reset(marke)
