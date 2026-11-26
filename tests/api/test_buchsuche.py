"""Suche im Buch (BF-3): nie in der Ereignisschleife; ein regulärer Ausdruck läuft mit Zeitgrenze in einem eigenen Prozess
und hält die App nicht auf."""

import asyncio
import time

import pytest

from backend.app.core.config import settings
from backend.app.services.storage import save_fulltext
from tests.api.conftest import buch_erstellen

TEXT = "Erste Seite mit dem Wort Schleife.\fZweite Seite: eine Schleife, noch eine Schleife.\f" + "a" * 40 + "!"


@pytest.fixture
async def buch(test_db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "speicher")
    save_fulltext("suchhash1", TEXT)
    return await buch_erstellen(test_db, hash="suchhash1", file_format="txt", page_count=3)


async def test_wort_und_ausdruck(client, buch):
    r = (await client.get(f"/api/books/{buch}/volltext-suche", params={"q": "schleife"})).json()
    assert r["gesamt"] == 3 and [t["seite"] for t in r["treffer"]] == [1, 2, 2] and "<mark>Schleife</mark>" in r["treffer"][0]["kontext"]
    r = (await client.get(f"/api/books/{buch}/volltext-suche", params={"q": r"Sch\w+e,", "regex": True})).json()
    assert r["gesamt"] == 1 and r["grund"] == ""
    r = (await client.get(f"/api/books/{buch}/volltext-suche", params={"q": "Wort <b>", "regex": False})).json()
    assert r["gesamt"] == 0


async def test_ungueltiger_ausdruck_nennt_den_grund(client, buch):
    r = (await client.get(f"/api/books/{buch}/volltext-suche", params={"q": "(offen", "regex": True})).json()
    assert r["gesamt"] == 0 and r["grund"].startswith("Kein gültiger regulärer Ausdruck")


async def test_festgerechneter_ausdruck_wird_beendet_und_haelt_nichts_auf(client, buch, monkeypatch):
    monkeypatch.setattr(settings, "suche_ausdruck_s", 1.5)
    beginn = time.monotonic()
    suche = asyncio.create_task(client.get(f"/api/books/{buch}/volltext-suche", params={"q": "(a+)+$", "regex": True}))
    await asyncio.sleep(0.3)
    gesund = time.monotonic()
    assert (await client.get("/api/health")).status_code == 200 and time.monotonic() - gesund < 1.0      # die App antwortet weiter
    r = (await suche).json()
    assert r["gesamt"] == 0 and "länger als 1.5 s" in r["grund"] and time.monotonic() - beginn < 5
