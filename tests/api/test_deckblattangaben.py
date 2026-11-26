"""Suche, Suche nach Bedeutung und Autorenseite tragen dieselben Deckblattangaben wie die Bücherliste (BF-59)."""

import pytest
from httpx import AsyncClient

from backend.app.services import deckblattangaben
from tests.api.conftest import buch_erstellen


async def _zwei(test_db) -> tuple[int, int]:
    schlicht = await buch_erstellen(test_db, hash="db01", title="Sturmflut am Deich", author="Lena Hofer", fts_content="Sturmflut und Deich im Winter")
    bild = await buch_erstellen(test_db, hash="db02", title="Sturmflut im Hafen", author="Lena Hofer", fts_content="Sturmflut und Hafen im Herbst")
    await test_db.execute("UPDATE books SET umschlag_schlicht = 1, typ = 'dokument' WHERE id = ?", (schlicht,))
    await test_db.execute("UPDATE books SET umschlag_schlicht = 1, umschlag_wahl = 'titelseite', gattung = 'krimi' WHERE id = ?", (bild,))
    await test_db.commit()
    return schlicht, bild


@pytest.mark.asyncio
async def test_angaben_je_buch_mit_der_rechnung_des_umschlags(client: AsyncClient, test_db):
    schlicht, bild = await _zwei(test_db)
    a = await deckblattangaben.fuer([schlicht, bild, 99999])
    assert set(a) == {schlicht, bild}
    assert (a[schlicht].umschlag, a[schlicht].typ) == ("gestaltet", "dokument")
    assert (a[bild].umschlag, a[bild].gattung) == ("titelseite", "krimi")
    assert await deckblattangaben.fuer([]) == {}


@pytest.mark.asyncio
async def test_worttreffer_tragen_das_deckblatt(client: AsyncClient, test_db):
    schlicht, bild = await _zwei(test_db)
    treffer = {t["book_id"]: t["deckblatt"] for t in (await client.get("/api/search", params={"q": "Sturmflut"})).json()["treffer"]}
    assert treffer[schlicht]["umschlag"] == "gestaltet" and treffer[schlicht]["typ"] == "dokument"
    assert treffer[bild]["umschlag"] == "titelseite" and treffer[bild]["gattung"] == "krimi"


@pytest.mark.asyncio
async def test_werke_auf_der_autorenseite_tragen_das_deckblatt(client: AsyncClient, test_db):
    schlicht, bild = await _zwei(test_db)
    autor = (await test_db.execute("INSERT INTO authors (name, slug) VALUES ('Lena Hofer', 'lena-hofer')")).lastrowid
    for b in (schlicht, bild):
        await test_db.execute("INSERT INTO book_authors (book_id, author_id) VALUES (?, ?)", (b, autor))
    await test_db.commit()
    werke = {w["id"]: w for w in (await client.get(f"/api/authors/{autor}")).json()["books"]}
    assert werke[schlicht]["umschlag"] == "gestaltet" and werke[bild]["umschlag"] == "titelseite"
