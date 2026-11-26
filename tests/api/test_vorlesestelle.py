"""Vorlesestelle je Buch (BF-37): gemerkt am Server, damit es auf jedem Gerät an demselben Satz weitergeht."""

import pytest

from tests.api.conftest import buch_erstellen


@pytest.mark.asyncio
async def test_ohne_gemerkte_stelle_kommt_nichts(client, test_db):
    buch = await buch_erstellen(test_db)
    r = await client.get(f"/api/books/{buch}/vorlesestelle")
    assert r.status_code == 200 and r.json() is None


@pytest.mark.asyncio
async def test_merkt_ersetzt_und_vergisst_die_stelle(client, test_db):
    buch = await buch_erstellen(test_db)
    erste = await client.put(f"/api/books/{buch}/vorlesestelle", json={"einheit": 11, "zeichen": 240, "bis_einheit": 14, "bis_zeichen": 0, "umfang": "Dieses Kapitel", "ort": "Seite 12"})
    assert erste.status_code == 200
    assert {k: v for k, v in erste.json().items() if k != "gemerkt_am"} == {"einheit": 11, "zeichen": 240, "bis_einheit": 14, "bis_zeichen": 0, "umfang": "Dieses Kapitel", "ort": "Seite 12"}
    assert erste.json()["gemerkt_am"].endswith("Z")
    await client.put(f"/api/books/{buch}/vorlesestelle", json={"einheit": 12, "zeichen": 8, "umfang": "Ab hier", "ort": "Seite 13"})
    zweite = (await client.get(f"/api/books/{buch}/vorlesestelle")).json()
    assert (zweite["einheit"], zweite["zeichen"], zweite["bis_einheit"], zweite["ort"]) == (12, 8, None, "Seite 13")
    assert (await client.delete(f"/api/books/{buch}/vorlesestelle")).status_code == 204
    assert (await client.get(f"/api/books/{buch}/vorlesestelle")).json() is None


@pytest.mark.asyncio
async def test_unbekanntes_buch_und_falsche_werte(client, test_db):
    assert (await client.get("/api/books/9999/vorlesestelle")).status_code == 404
    buch = await buch_erstellen(test_db)
    assert (await client.put(f"/api/books/{buch}/vorlesestelle", json={"einheit": -1, "zeichen": 0})).status_code == 422


@pytest.mark.asyncio
async def test_geht_mit_dem_buch(client, test_db):
    buch = await buch_erstellen(test_db)
    await client.put(f"/api/books/{buch}/vorlesestelle", json={"einheit": 1, "zeichen": 2})
    await test_db.execute("DELETE FROM books WHERE id = ?", (buch,))
    await test_db.commit()
    zeile = await test_db.fetch_one("SELECT COUNT(*) AS n FROM vorlesestelle")
    assert zeile["n"] == 0


@pytest.mark.asyncio
async def test_ohne_anmeldung_nichts(client_ohne_auth, test_db):
    buch = await buch_erstellen(test_db)
    assert (await client_ohne_auth.get(f"/api/books/{buch}/vorlesestelle")).status_code == 401
