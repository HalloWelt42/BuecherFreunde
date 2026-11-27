"""Der Auftrag "Volltexte mit falschen Ligaturen neu lesen" (BF-104): betroffen sind gespeicherte Volltexte mit einem
Fehlzeichen mitten im Wort; sie werden aus dem Original neu gelesen, Seiten und Suche ziehen nach. Ohne Original oder
ohne lesbaren Text bleibt der alte Volltext. Eine laufende Probeinstallation in tmp_path, alle Texte erfunden."""

from __future__ import annotations

import asyncio

import fitz
import pytest

from backend.app.annahme import auswertung
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.einrichtung.ligaturen import OHNE_ORIGINAL, ligaturen
from backend.app.services.storage import get_sidecar_path, get_storage_path, load_fulltext, save_fulltext
from tests.api.conftest import buch_erstellen
from tests.api.einrichtung_hilfen import laufend, orte  # noqa: F401 - Fixtures

pytestmark = pytest.mark.asyncio
TI = chr(0x19F)                                          # so kam "ti" aus einer Fehlschrift
FALSCH = f"Die Funk{TI}on rechnet, und die Varia{TI}on bleibt."
RICHTIG = "Die Funktion rechnet, und die Variation bleibt."


@pytest.fixture(autouse=True)
def ohne_eigenen_prozess(monkeypatch):
    """Der Leser läuft im Test im selben Prozess (sonst ein eigener)."""
    async def text(pfad):
        return await asyncio.to_thread(auswertung._nur_text, str(pfad))

    monkeypatch.setattr(auswertung, "text", text)


async def _buch(test_db, kennung: str, volltext: str, mit_original: bool) -> int:
    nr = await buch_erstellen(test_db, hash=kennung, file_format="pdf", page_count=1, isbn="", fts_content="")
    save_fulltext(kennung, volltext)
    if mit_original:
        doc = fitz.open()
        doc.new_page().insert_text((72, 100), RICHTIG, fontname="helv", fontsize=11)
        doc.save(get_storage_path(kennung) / "buch.pdf")
    return nr


async def _befund() -> dict[int, str]:
    return {z["book_id"]: z["stand"] for z in await db.fetch_all("SELECT book_id, stand FROM ligatur_befund")}


async def test_betroffene_volltexte_werden_neu_gelesen_und_nichts_geht_verloren(laufend, test_db, client):  # noqa: F811
    betroffen = await _buch(test_db, "ligatur00betroffen", FALSCH, mit_original=True)
    heil = await _buch(test_db, "ligatur00heil", RICHTIG, mit_original=True)
    formel = await _buch(test_db, "ligatur00formel", f"Der Winkel {TI} steht allein.", mit_original=True)
    ohne = await _buch(test_db, "ligatur00ohne", FALSCH, mit_original=False)
    get_sidecar_path("ligatur00betroffen", "seiten.json").write_text("{}", encoding="utf-8")

    r = await client.post("/api/einrichtung/ligaturen")
    assert r.status_code == 200, r.text
    await ligaturen.warten()

    assert await _befund() == {betroffen: "neu", heil: "heil", formel: "heil", ohne: "ohne"}
    assert RICHTIG in load_fulltext("ligatur00betroffen") and TI not in load_fulltext("ligatur00betroffen")
    assert not get_sidecar_path("ligatur00betroffen", "seiten.json").exists()           # die Seiten ergeben sich neu
    assert load_fulltext("ligatur00ohne") == FALSCH                                     # ohne Original bleibt der alte Text
    assert load_fulltext("ligatur00heil") == RICHTIG
    treffer = await db.fetch_all("SELECT rowid FROM suche.buch_fts WHERE buch_fts MATCH 'Funktion'")
    assert [z["rowid"] for z in treffer] == [betroffen]                                 # die Suche findet das richtige Wort

    stand = next(a for a in (await client.get("/api/einrichtung/auftraege")).json() if a["art"] == "ligaturen")
    assert stand["stand"] == "fertig" and stand["gesamt"] == 4 and stand["fertig"] == 4
    assert {t["schluessel"]: t["fertig"] for t in stand["teile"]} == {"neu": 1, "heil": 2, "ohne": 1, "fehler": 0}
    grund = (await db.fetch_one("SELECT text FROM ligatur_befund WHERE book_id = ?", (ohne,)))["text"]
    assert grund == OHNE_ORIGINAL


async def test_angehalten_geht_es_an_derselben_stelle_weiter(laufend, test_db, client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "einrichtung_abstand_s", 0.2)                        # Zeit zum Anhalten zwischen zwei Stücken
    for i in range(3):
        await _buch(test_db, f"ligatur00weiter{i}", FALSCH, mit_original=True)
    await ligaturen.beginnen()
    await asyncio.sleep(0.05)
    await ligaturen.pause()
    await ligaturen.warten()
    vorher = await _befund()
    assert list(vorher.values()).count("offen") >= 1                                    # angehalten, bevor alles fertig war
    r = await client.post("/api/einrichtung/auftraege/ligaturen/fortsetzen")
    assert r.status_code == 200, r.text
    await ligaturen.warten()
    assert set((await _befund()).values()) == {"neu"}
