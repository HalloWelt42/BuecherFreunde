"""Altersangabe am Buch (BF-78): mit Herkunft aus den Quellen übernommen, von Erwachsenen überschreibbar, für Kinder nicht."""

from __future__ import annotations

from tests.api.conftest import buch_erstellen
from tests.api.familie_hilfen import familie_anlegen


async def test_alter_ueberschreiben_und_leeren(client, test_db):
    f = await familie_anlegen(client, test_db)
    weg = f"/api/books/{f.buch['mond']}"
    r = await client.patch(weg, json={"alter_von": 5, "alter_bis": 8}, headers=f.kopf["bert"])
    assert r.status_code == 200 and (r.json()["alter_von"], r.json()["alter_bis"], r.json()["alter_quelle"]) == (5, 8, "hand")
    liste = (await client.get("/api/books", headers=f.kopf["ada"])).json()["buecher"]
    assert next(b for b in liste if b["id"] == f.buch["mond"])["alter_von"] == 5
    r = await client.patch(weg, json={"alter_von": None, "alter_bis": None}, headers=f.kopf["ada"])
    assert (r.json()["alter_von"], r.json()["alter_bis"]) == (None, None)
    assert (await client.patch(weg, json={"alter_von": 120}, headers=f.kopf["ada"])).status_code == 422
    assert (await client.patch(weg, json={"alter_von": 3}, headers=f.kopf["emil"])).status_code == 403


async def test_alter_aus_dem_vorschlag_mit_herkunft(client, test_db):
    nr = await buch_erstellen(test_db, hash="alt01", title="Die Probe im Wald")
    felder = {"alter_von": 6, "alter_bis": None, "herkunft": {"alter": "dnb"}, "quelle": "alle"}
    r = await client.post(f"/api/metadata/buch/{nr}/uebernehmen", json=felder)
    assert r.status_code == 200
    buch = (await client.get(f"/api/books/{nr}")).json()
    assert (buch["alter_von"], buch["alter_bis"], buch["alter_quelle"]) == (6, None, "dnb")
    assert (await client.post(f"/api/metadata/buch/{nr}/uebernehmen", json={"alter_von": "viel"})).status_code == 422
