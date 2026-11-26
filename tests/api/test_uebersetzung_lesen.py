"""Lesen einer Fassung (BF-71): welche Fassung "Lesen" öffnet, der Lesestand einer Übersetzung getrennt vom Original, und
die Fassungen in Arbeit für die Aufträge. Nur das erfundene Probebuch."""

from backend.app.services.ki import ki
from backend.app.services.uebersetzungslauf import Uebersetzungslauf
from tests.api.test_ausfuehren import leitstelle  # noqa: F401 - Attrappe der Leitstelle
from tests.api.uebersetzer import orte, probebuch, uebersetzer  # noqa: F401 - Fixtures

STELLE_ORIGINAL = 'epub:{"cfi":"epubcfi(/6/4!/4/2/1:0)","percent":12}'
STELLE_DEUTSCH = 'epub:{"cfi":"epubcfi(/6/8!/4/6/1:20)","percent":48}'


async def _gewaehlt(client, buch: int) -> list[tuple[str, bool]]:
    return [(e["sprache"], e["gewaehlt"]) for e in (await client.get(f"/api/books/{buch}/fassungen")).json()]


async def test_wahl_der_fassung(client, test_db, uebersetzer):
    buch = await probebuch(test_db)
    assert await _gewaehlt(client, buch) == [("en", True)]
    r = await client.put(f"/api/books/{buch}/fassungen/wahl", json={"sprache": "de"})
    assert r.status_code == 404 and r.json()["detail"] == "Diese Fassung gibt es noch nicht"
    await client.post(f"/api/books/{buch}/fassungen/de")
    assert await _gewaehlt(client, buch) == [("en", True), ("de", False)]          # ohne Wahl öffnet das Original
    r = await client.put(f"/api/books/{buch}/fassungen/wahl", json={"sprache": "de"})
    assert r.status_code == 200 and [(e["sprache"], e["gewaehlt"]) for e in r.json()] == [("en", False), ("de", True)]
    assert await _gewaehlt(client, buch) == [("en", False), ("de", True)]
    assert (await client.put(f"/api/books/{buch}/fassungen/wahl", json={"sprache": None})).json()[0]["gewaehlt"] is True
    assert await _gewaehlt(client, buch) == [("en", True), ("de", False)]
    assert (await client.put(f"/api/books/{buch}/fassungen/wahl", json={"sprache": "fr"})).status_code == 422
    assert (await client.put("/api/books/999/fassungen/wahl", json={"sprache": None})).status_code == 404


async def test_wahl_laesst_die_nutzerdaten_stehen(client, test_db, uebersetzer):
    buch = await probebuch(test_db)
    await client.patch(f"/api/books/{buch}/favorit")
    await client.patch(f"/api/books/{buch}/leseposition", json={"position": STELLE_ORIGINAL})
    await client.post(f"/api/books/{buch}/fassungen/de")
    await client.put(f"/api/books/{buch}/fassungen/wahl", json={"sprache": "de"})
    b = (await client.get(f"/api/books/{buch}")).json()
    assert b["is_favorite"] is True and b["reading_position"] == STELLE_ORIGINAL


async def test_lesestand_der_uebersetzung_getrennt_vom_original(client, test_db, uebersetzer):
    buch = await probebuch(test_db)
    fid = (await client.post(f"/api/books/{buch}/fassungen/de")).json()["id"]
    await Uebersetzungslauf(ki).runde()
    assert (await client.get(f"/api/fassungen/{fid}/leseposition")).json() == {"position": "", "gelesen_am": None}
    await client.patch(f"/api/books/{buch}/leseposition", json={"position": STELLE_ORIGINAL})
    r = await client.patch(f"/api/fassungen/{fid}/leseposition", json={"position": STELLE_DEUTSCH})
    assert r.status_code == 200 and r.json()["position"] == STELLE_DEUTSCH and r.json()["gelesen_am"].endswith("Z")
    assert (await client.get(f"/api/fassungen/{fid}/leseposition")).json()["position"] == STELLE_DEUTSCH
    assert (await client.get(f"/api/books/{buch}")).json()["reading_position"] == STELLE_ORIGINAL      # das Original bleibt
    await client.patch(f"/api/books/{buch}/leseposition", json={"position": STELLE_ORIGINAL.replace("12", "13")})
    assert (await client.get(f"/api/fassungen/{fid}/leseposition")).json()["position"] == STELLE_DEUTSCH  # und umgekehrt
    assert (await client.patch(f"/api/fassungen/{fid}/leseposition", json={"position": ""})).status_code == 422
    assert (await client.get("/api/fassungen/999/leseposition")).status_code == 404
    assert (await client.patch("/api/fassungen/999/leseposition", json={"position": STELLE_DEUTSCH})).status_code == 404


async def test_lesestand_geht_mit_der_fassung(client, test_db, uebersetzer):
    buch = await probebuch(test_db)
    fid = (await client.post(f"/api/books/{buch}/fassungen/de")).json()["id"]
    await client.patch(f"/api/fassungen/{fid}/leseposition", json={"position": STELLE_DEUTSCH})
    await test_db.execute("DELETE FROM fassung WHERE id = ?", (fid,))
    await test_db.commit()
    assert await test_db.fetch_one("SELECT * FROM fassung_lesestand WHERE fassung_id = ?", (fid,)) is None


async def test_fassungen_in_arbeit_fuer_die_auftraege(client, test_db, uebersetzer):
    assert (await client.get("/api/fassungen")).json() == []
    buch = await probebuch(test_db)
    fid = (await client.post(f"/api/books/{buch}/fassungen/de")).json()["id"]
    [lauf] = (await client.get("/api/fassungen")).json()
    assert {k: lauf[k] for k in ("id", "buch_id", "titel", "sprache", "stand", "anteil", "kapitel_fertig", "kapitel_gesamt", "grund")} == {
        "id": fid, "buch_id": buch, "titel": "Gardening with Small Machines", "sprache": "de", "stand": "laeuft", "anteil": 0.0,
        "kapitel_fertig": 0, "kapitel_gesamt": 0, "grund": ""}
    assert lauf["fertig_gegen"].endswith("Z")
    await client.post(f"/api/fassungen/{fid}/pause")
    [lauf] = (await client.get("/api/fassungen")).json()
    assert lauf["stand"] == "pause" and lauf["fertig_gegen"] is None
    await client.post(f"/api/fassungen/{fid}/fortsetzen")
    await Uebersetzungslauf(ki).runde()
    assert (await client.get("/api/fassungen")).json() == []                       # fertig: kein Auftrag mehr
    await client.post(f"/api/fassungen/{fid}/bloecke/3.2", json={"aktion": "neu"})  # ein Block neu: die Fassung läuft wieder
    [lauf] = (await client.get("/api/fassungen")).json()
    assert lauf["stand"] == "laeuft" and lauf["kapitel_gesamt"] == 4 and lauf["kapitel_fertig"] == 3 and 0.9 < lauf["anteil"] < 1
