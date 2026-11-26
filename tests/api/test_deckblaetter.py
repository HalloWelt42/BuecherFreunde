"""Gestaltete Deckblätter (BF-59): Gattungen, Umschlagangaben an Liste und Buch, Einordnen von Hand und die Umschlagprüfung
mit kleinen Testbildern. Das Einordnen mit Regeln und der lokalen KI prüft tests/api/test_einordnung.py."""

import asyncio
import os

import pytest

from backend.app.core.config import settings
from backend.app.models.book import GATTUNGEN, umschlag_zeigen
from backend.app.services import umschlagpruefung as pruefung_modul
from backend.app.services.storage import get_sidecar_path, save_cover
from backend.app.services.umschlagpruefung import Umschlagpruefung
from tests.api.conftest import buch_erstellen
from tests.backend.test_deckblatt import bild, titelseite

ROT = (200, 20, 20)


@pytest.fixture
def orte(tmp_path, monkeypatch):
    """Eigene Orte für Umschläge und Volltexte je Test."""
    for ort in ("storage_dir", "umschlaege_dir"):
        monkeypatch.setattr(settings, ort, tmp_path / ort)


def umschlag(file_hash: str, daten: bytes, stand: int) -> None:
    """Ein Umschlag mit festem Stand (der Stand zählt in Sekunden: zweimal in derselben Sekunde wäre derselbe)."""
    os.utime(save_cover(file_hash, daten), (stand, stand))


async def zeile(test_db, buch: int) -> dict:
    return await test_db.fetch_one("SELECT typ, gattung, umschlag_wahl, umschlag_schlicht, umschlag_geprueft, einordnung, "
                                   "manuell_bearbeitet, updated_at FROM books WHERE id = ?", (buch,))


async def setzen(test_db, buch: int, **spalten) -> None:
    await test_db.execute(f"UPDATE books SET {', '.join(f'{k} = ?' for k in spalten)} WHERE id = ?", (*spalten.values(), buch))
    await test_db.commit()


# -- Gattungen, Umschlag an Liste und Buch ----------------------------------------------------------------------------------

async def test_gattungen_in_fester_reihenfolge(client):
    r = (await client.get("/api/collections/gattungen")).json()
    assert [g["id"] for g in r] == ["krimi", "thriller", "historisch", "fantasy", "liebesroman", "roman", "klassiker", "sachbuch",
                                    "ratgeber", "informatik", "mathematik", "fachbuch", "wirtschaft"]
    assert r == GATTUNGEN and r[2] == {"id": "historisch", "name": "Historischer Roman"} and r[-1]["name"] == "Wirtschaft und Recht"


@pytest.mark.parametrize(("wahl", "schlicht", "umschlag_"), [
    ("", False, "titelseite"), ("", True, "gestaltet"), ("titelseite", True, "titelseite"), ("gestaltet", False, "gestaltet"),
])
def test_umschlag_aus_wahl_und_befund(wahl, schlicht, umschlag_):
    assert umschlag_zeigen(wahl, schlicht) == umschlag_


async def test_liste_und_buch_tragen_die_umschlagangaben(client, test_db):
    ungeprueft = await buch_erstellen(test_db, hash="u1", title="A ungeprüft", author="Gleich")
    schlicht = await buch_erstellen(test_db, hash="s1", title="B schlicht", author="Gleich")
    gewaehlt = await buch_erstellen(test_db, hash="g1", title="C gewählt", author="Gleich")
    await setzen(test_db, schlicht, umschlag_schlicht=1)
    await setzen(test_db, gewaehlt, umschlag_schlicht=1, umschlag_wahl="titelseite", gattung="krimi")
    erwartet = {ungeprueft: ("", "", False, "titelseite"), schlicht: ("", "", True, "gestaltet"),
                gewaehlt: ("krimi", "titelseite", True, "titelseite")}

    def angaben(b: dict) -> tuple:
        return b["gattung"], b["umschlag_wahl"], b["umschlag_schlicht"], b["umschlag"]

    liste = (await client.get("/api/books")).json()["buecher"]
    assert {b["id"]: angaben(b) for b in liste} == erwartet
    for nr, werte in erwartet.items():
        assert angaben((await client.get(f"/api/books/{nr}")).json()) == werte
    aehnliche = (await client.get(f"/api/books/{ungeprueft}/aehnliche")).json()["vom_autor"]
    assert {b["id"]: angaben(b) for b in aehnliche} == {k: v for k, v in erwartet.items() if k != ungeprueft}


# -- Ändern von Hand ----------------------------------------------------------------------------------------------------------

async def test_typ_oder_gattung_setzen_heisst_von_hand(client, test_db):
    krimi = await buch_erstellen(test_db, hash="k1")
    akte = await buch_erstellen(test_db, hash="a1")
    r = await client.patch(f"/api/books/{krimi}", json={"gattung": "krimi"})
    assert r.status_code == 200 and r.json()["gattung"] == "krimi"
    assert (await client.patch(f"/api/books/{akte}", json={"typ": "dokument"})).json()["typ"] == "dokument"
    for nr in (krimi, akte):
        z = await zeile(test_db, nr)
        assert z["einordnung"] == "hand" and z["manuell_bearbeitet"] == 1


async def test_umschlag_waehlen_bearbeitet_keine_angabe(client, test_db):
    buch = await buch_erstellen(test_db, hash="w1")
    await setzen(test_db, buch, umschlag_schlicht=1, updated_at="2026-01-01 00:00:00")
    r = (await client.patch(f"/api/books/{buch}", json={"umschlag_wahl": "titelseite"})).json()
    assert r["umschlag_wahl"] == "titelseite" and r["umschlag"] == "titelseite"
    z = await zeile(test_db, buch)
    assert z["manuell_bearbeitet"] == 0 and z["updated_at"] == "2026-01-01 00:00:00" and z["einordnung"] == ""
    assert (await client.patch(f"/api/books/{buch}", json={"umschlag_wahl": ""})).json()["umschlag"] == "gestaltet"   # wieder automatisch
    await client.patch(f"/api/books/{buch}", json={"umschlag_wahl": "gestaltet", "title": "Neu"})
    z = await zeile(test_db, buch)
    assert z["umschlag_wahl"] == "gestaltet" and z["manuell_bearbeitet"] == 1 and z["einordnung"] == ""                # der Titel schon


async def test_typ_fuer_viele_heisst_von_hand(client, test_db):
    buecher = [await buch_erstellen(test_db, hash=f"v{i}") for i in range(2)]
    r = await client.post("/api/books/bulk", json={"book_ids": buecher, "aktion": "typ_setzen", "wert": "dokument"})
    assert r.json()["betroffen"] == 2
    assert [(await zeile(test_db, b))["einordnung"] for b in buecher] == ["hand", "hand"]


# -- Umschläge prüfen -------------------------------------------------------------------------------------------------------

async def test_umschlagpruefung(client, test_db, orte, monkeypatch):
    monkeypatch.setattr(pruefung_modul, "TEIL", 2)          # drei Bücher: zwei Teile
    monkeypatch.setattr(pruefung_modul, "PAUSE_S", 0)
    weiss = await buch_erstellen(test_db, hash="weiss1")
    bunt = await buch_erstellen(test_db, hash="bunt1")
    ohne = await buch_erstellen(test_db, hash="ohne1")
    umschlag("weiss1", titelseite(), 1_000_000)
    umschlag("bunt1", bild(ROT, art="JPEG"), 1_000_000)
    pruefung, gemeldet = Umschlagpruefung(), []
    pruefung.nach_runde.append(lambda: gemeldet.append(True))

    assert await pruefung.runde() == 3 and gemeldet == [True]
    befund = lambda z: (z["umschlag_schlicht"], z["umschlag_geprueft"])          # noqa: E731
    befunde = [befund(await zeile(test_db, b)) for b in (weiss, bunt, ohne)]
    assert befunde == [(1, 1_000_000), (0, 1_000_000), (1, 0)]                      # ohne Datei: schlicht
    assert (await client.get(f"/api/books/{bunt}")).json()["umschlag"] == "titelseite"

    assert await pruefung.runde() == 0 and gemeldet == [True]                       # nichts Neues, nichts zu tun
    umschlag("bunt1", titelseite(), 1_000_100)                                      # ein neuer Umschlag, gleich woher
    umschlag("ohne1", bild(ROT, art="JPEG"), 1_000_100)
    assert await pruefung.runde() == 2
    assert [befund(await zeile(test_db, b)) for b in (bunt, ohne)] == [(1, 1_000_100), (0, 1_000_100)]
    assert (await client.get(f"/api/books/{bunt}")).json()["umschlag"] == "gestaltet"
    get_sidecar_path("ohne1", "cover.jpg").unlink()                                 # Umschlag fort: wieder schlicht
    assert await pruefung.runde() == 1 and befund(await zeile(test_db, ohne)) == (1, 0)


async def test_umschlagpruefung_laeuft_gleich_beim_start(test_db, orte, monkeypatch):
    monkeypatch.setattr(pruefung_modul, "PAUSE_S", 0)
    buch = await buch_erstellen(test_db, hash="start1")
    pruefung, gemeldet = Umschlagpruefung(), asyncio.Event()
    pruefung.nach_runde.append(gemeldet.set)
    pruefung.starten()
    try:
        await asyncio.wait_for(gemeldet.wait(), 5)
    finally:
        await pruefung.stoppen()
    assert (await zeile(test_db, buch))["umschlag_schlicht"] == 1
