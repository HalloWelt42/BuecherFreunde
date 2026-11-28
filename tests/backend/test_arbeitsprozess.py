"""Arbeitsprozess mit Grenzen (BF-120): über der Speichergrenze scheitert nur die Aufgabe, nach der Frist endet der Prozess."""

import asyncio
import os
import sys
import time

import pytest

from backend.app.core import arbeitsprozess
from backend.app.core.arbeitsprozess import Abgestuerzt, Arbeitsprozess, ZuLange

pytestmark = pytest.mark.asyncio


def _belegen(mb: int) -> int:
    """Belegt so viel Speicher, wie verlangt, und gibt die Prozessnummer."""
    platz = bytearray(mb * 1024 * 1024)
    platz[-1] = 1
    return os.getpid()


def _schlafen(s: float) -> int:
    time.sleep(s)
    return os.getpid()


def _ende() -> None:
    os._exit(3)


def _lebt(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.skipif(sys.platform != "linux", reason="die Grenze für den Adressraum gibt es nur unter Linux (Betrieb)")
async def test_ueber_der_speichergrenze_scheitert_nur_die_aufgabe(monkeypatch):
    monkeypatch.setattr(arbeitsprozess.settings, "arbeitsprozess_speicher_mb", 600)
    p = Arbeitsprozess(aufgaben_je_prozess=5)
    try:
        assert await p.ausfuehren(_belegen, 50, frist_s=60) != os.getpid()
        with pytest.raises(MemoryError):
            await p.ausfuehren(_belegen, 2000, frist_s=60)
        assert await p.ausfuehren(_belegen, 50, frist_s=60)          # der nächste Auftrag geht wieder
    finally:
        p.beenden()


async def test_nach_der_frist_ist_der_prozess_beendet():
    p = Arbeitsprozess(aufgaben_je_prozess=5)
    try:
        pid = await p.ausfuehren(_schlafen, 0, frist_s=30)
        with pytest.raises(ZuLange):
            await p.ausfuehren(_schlafen, 30, frist_s=0.5)
        for _ in range(50):
            if not _lebt(pid):
                break
            await asyncio.sleep(0.1)
        assert not _lebt(pid)                                        # beendet, nicht nur verlassen
        assert await p.ausfuehren(_schlafen, 0, frist_s=30) != pid   # ein frischer Prozess
    finally:
        p.beenden()


async def test_ein_absturz_trifft_nur_die_aufgabe():
    p = Arbeitsprozess(aufgaben_je_prozess=5)
    try:
        with pytest.raises(Abgestuerzt):
            await p.ausfuehren(_ende, frist_s=30)
        assert await p.ausfuehren(_schlafen, 0, frist_s=30)
    finally:
        p.beenden()
