"""Der Strom des Vorlesens bis zum ersten Satz (BF-121): geht der Leser, solange der erste Satz aussteht, endet die Anfrage an
die Vertonung sofort, statt als wartender Auftrag stehen zu bleiben."""

from __future__ import annotations

import asyncio

import pytest
from appkern.vorlesen import VorlesenFehler

from backend.app.vorlesen import strom


class Vertonung:
    """Ein Strom wie der von `sprechen.zeilen`: wartet `warten_s` auf den ersten Satz und merkt, ob er geschlossen wurde."""

    def __init__(self, warten_s: float, zeilen: list[bytes] | None = None, fehler: Exception | None = None) -> None:
        self.warten_s, self.zeilen, self.fehler = warten_s, zeilen or [], fehler
        self.geschlossen = False

    async def strom(self):
        try:
            await asyncio.sleep(self.warten_s)
            if self.fehler:
                raise self.fehler
            for z in self.zeilen:
                yield z
        finally:
            self.geschlossen = True


async def nie() -> bool:
    return False


async def test_die_erste_zeile_kommt_der_rest_bleibt_im_strom():
    v = Vertonung(0.01, [b"eins\n", b"zwei\n"])
    zeilen = v.strom()
    assert await strom.erste_zeile(zeilen, nie, blick_s=0.005) == b"eins\n"
    assert [z async for z in zeilen] == [b"zwei\n"] and v.geschlossen


async def test_ohne_zeile_leer():
    assert await strom.erste_zeile(Vertonung(0).strom(), nie) == b""


async def test_ein_fehler_vor_dem_ersten_satz_kommt_durch():
    v = Vertonung(0, fehler=VorlesenFehler("Die Vertonung antwortet nicht", 503))
    with pytest.raises(VorlesenFehler):
        await strom.erste_zeile(v.strom(), nie)
    assert v.geschlossen


async def test_geht_der_leser_endet_die_anfrage_an_die_vertonung():
    v = Vertonung(3600)
    blicke = 0

    async def gegangen() -> bool:
        nonlocal blicke
        blicke += 1
        return blicke >= 3

    with pytest.raises(strom.Gegangen):
        await asyncio.wait_for(strom.erste_zeile(v.strom(), gegangen, blick_s=0.01), 2)
    assert v.geschlossen and blicke == 3
