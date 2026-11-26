"""Eine Transaktion je Anfrage (BF-49): was eine Anfrage vor einem Fehler geändert hat, wird zurückgerollt und nie von
einem fremden Aufruf mitgespeichert; Hintergrundläufe schreiben nicht in fremde Transaktionen."""

import asyncio
import sqlite3

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.database import db
from backend.app.main import app
from tests.api.conftest import buch_erstellen, kategorie_erstellen


@pytest.fixture
async def ohne_ausnahmen(test_db, auth_headers):
    """Wie der Browser: ein Fehler im Server kommt als Antwort 500, nicht als Ausnahme im Test."""
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver",
                           headers=auth_headers) as c:
        yield c


def gebucht(sql: str, *werte) -> list[tuple]:
    """Was gebucht ist, gelesen über eine zweite Verbindung (sieht nichts, was noch in einer Transaktion hängt)."""
    c = sqlite3.connect(f"file:{db.db_path}?mode=ro", uri=True)
    try:
        return c.execute(sql, werte).fetchall()
    finally:
        c.close()


async def regale(buch: int) -> list[int]:
    return [z[0] for z in gebucht("SELECT category_id FROM book_categories WHERE book_id = ? ORDER BY category_id", buch)]


async def test_halbe_aenderung_wird_nicht_mitgespeichert(ohne_ausnahmen, test_db):
    buch = await buch_erstellen(test_db)
    regal = await kategorie_erstellen(test_db, "Krimi")
    assert (await ohne_ausnahmen.post(f"/api/categories/{buch}/zuordnen", json=[regal])).status_code == 200
    r = await ohne_ausnahmen.post(f"/api/categories/{buch}/zuordnen", json=[999_999])      # das Regal gibt es nicht
    assert r.status_code >= 400
    andere = await buch_erstellen(test_db, hash="anderes", title="Anderes")
    assert (await ohne_ausnahmen.post(f"/api/books/{andere}/notes", json={"content": "fremder Aufruf", "page_reference": "1"})).status_code == 200
    assert await regale(buch) == [regal], "das Löschen vor dem Fehler darf kein fremder Aufruf mitspeichern"


async def test_fehlerantwort_rollt_zurueck_und_erfolg_bucht(ohne_ausnahmen, test_db, monkeypatch):
    buch = await buch_erstellen(test_db)
    regal = await kategorie_erstellen(test_db, "Roman")

    from backend.app.api import categories

    echt = categories.db.commit

    async def ohne_commit():                               # ein Weg, der das Buchen vergisst, bucht trotzdem am Ende
        return None

    monkeypatch.setattr(categories.db, "commit", ohne_commit)
    assert (await ohne_ausnahmen.post(f"/api/categories/{buch}/zuordnen", json=[regal])).status_code == 200
    monkeypatch.setattr(categories.db, "commit", echt)
    assert await regale(buch) == [regal]


async def test_hintergrund_schreibt_nicht_in_die_anfrage(ohne_ausnahmen, test_db):
    buch = await buch_erstellen(test_db)
    regal = await kategorie_erstellen(test_db, "Lyrik")
    await test_db.execute("INSERT INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'import')", (buch, regal))
    await test_db.commit()
    geschrieben = asyncio.Event()

    async def hintergrund():                               # schreibt, ohne zu buchen, während eine Anfrage scheitert
        await db.execute("UPDATE books SET title = 'Vom Hintergrund' WHERE id = ?", (buch,))
        geschrieben.set()

    await asyncio.create_task(hintergrund())
    assert (await ohne_ausnahmen.post(f"/api/categories/{buch}/zuordnen", json=[999_999])).status_code >= 400
    assert geschrieben.is_set()
    assert gebucht("SELECT title FROM books WHERE id = ?", buch) == [("Vom Hintergrund",)]
    assert await regale(buch) == [regal]
