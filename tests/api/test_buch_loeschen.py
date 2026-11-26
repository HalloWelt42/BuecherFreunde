"""Ein Buch löschen (BF-60): erst die Folgen, dann löschen; die Datei geht in den Papierkorb der Kellerwolke, und scheitert das,
bleibt alles, wie es war."""

import pytest
from httpx import AsyncClient

from backend.app.ablage.wolke import Wolke, WolkeFehler
from backend.app.core.config import settings
from backend.app.services.storage import get_sidecar_path, get_storage_path, save_cover
from tests.api.conftest import buch_erstellen, kategorie_erstellen, verwaltung


@pytest.fixture
def orte(tmp_path, monkeypatch):
    for ort in ("storage_dir", "umschlaege_dir", "zwischen_dir"):
        monkeypatch.setattr(settings, ort, tmp_path / ort)


@pytest.fixture
def papierkorb(monkeypatch):
    """Eine vorgetäuschte Kellerwolke; `antwort` steuert, was sie auf DELETE sagt."""
    rufe: list[tuple[str, str]] = []
    zustand = {"antwort": None}

    async def rufe_auf(_s, art, weg, **_w):
        rufe.append((art, weg))
        if zustand["antwort"] is not None:
            raise zustand["antwort"]
        return {}

    monkeypatch.setattr(Wolke, "bereit", property(lambda _s: True))
    monkeypatch.setattr(Wolke, "rufe", rufe_auf)
    return rufe, zustand


async def _buch_mit_allem(test_db, in_der_wolke: bool = True) -> int:
    buch = await buch_erstellen(test_db, hash="loesch01", title="Der Prozeß", author="Franz Kafka", file_size=173000, file_format="epub")
    profil = await verwaltung(test_db)
    for text in ("erste", "zweite"):
        await test_db.execute("INSERT INTO book_notes (profil_id, book_id, content) VALUES (?, ?, ?)", (profil, buch, text))
    for n in range(3):
        await test_db.execute("INSERT INTO book_highlights (profil_id, book_id, cfi_range) VALUES (?, ?, ?)", (profil, buch, f"epubcfi(/6/{n})"))
    await test_db.execute("INSERT INTO book_labels (profil_id, book_id, name) VALUES (?, ?, 'Merksatz')", (profil, buch))
    await test_db.execute("INSERT INTO user_book_data (profil_id, book_id, reading_position) VALUES (?, ?, 'epubcfi(/6/4)')", (profil, buch))
    await test_db.execute("INSERT INTO vorlesestelle (profil_id, buch_id, einheit, zeichen) VALUES (?, ?, 2, 10)", (profil, buch))
    await test_db.execute("INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)", (buch, await kategorie_erstellen(test_db, name="Klassiker")))
    ungeordnet = await kategorie_erstellen(test_db, name="Ungeordnet")          # vergibt die App selbst, zählt nicht als Regal
    await test_db.execute("INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)", (buch, ungeordnet))
    if in_der_wolke:
        await test_db.execute("INSERT INTO ablage_datei (hash, knoten, name, pfad, groesse) VALUES ('loesch01', 'k7', 'Der Prozeß.epub', "
                              "'Apps/BücherFreunde/Bücher/D/Der Prozeß.epub', 173000)")
    await test_db.commit()
    return buch


async def _noch_da(test_db, buch: int) -> tuple[int, int, int]:
    zaehle = lambda sql: test_db.fetch_one(sql, (buch,))
    return ((await zaehle("SELECT count(*) AS n FROM books WHERE id = ?"))["n"], (await zaehle("SELECT count(*) AS n FROM book_notes WHERE book_id = ?"))["n"],
            (await test_db.fetch_one("SELECT count(*) AS n FROM ablage_datei WHERE hash = 'loesch01'"))["n"])


@pytest.mark.asyncio
async def test_folgen_nennen_alles_was_verloren_geht(client: AsyncClient, test_db, orte):
    buch = await _buch_mit_allem(test_db)
    f = (await client.get(f"/api/books/{buch}/loeschfolgen")).json()
    assert (f["titel"], f["autor"], f["notizen"], f["markierungen"], f["etiketten"], f["lesestand"], f["vorlesestelle"], f["regale"]) == \
        ("Der Prozeß", "Franz Kafka", 2, 3, 1, True, True, 1)
    assert f["datei"] == {"pfad": "Apps/BücherFreunde/Bücher/D/Der Prozeß.epub", "groesse": 173000, "papierkorb": True}
    assert f["abschnitte"] is None


@pytest.mark.asyncio
async def test_folgen_eines_buchs_nur_auf_dem_geraet(client: AsyncClient, test_db, orte):
    buch = await _buch_mit_allem(test_db, in_der_wolke=False)
    ordner = get_storage_path("loesch01")
    ordner.mkdir(parents=True)
    (ordner / "Der Prozeß.epub").write_bytes(b"epub")
    f = (await client.get(f"/api/books/{buch}/loeschfolgen")).json()
    assert f["datei"] == {"pfad": "Der Prozeß.epub", "groesse": 173000, "papierkorb": False}


@pytest.mark.asyncio
async def test_loeschen_legt_die_datei_in_den_papierkorb_und_raeumt_auf(client: AsyncClient, test_db, orte, papierkorb):
    rufe, _ = papierkorb
    buch = await _buch_mit_allem(test_db)
    save_cover("loesch01", b"jpeg")
    get_storage_path("loesch01").mkdir(parents=True)
    (get_storage_path("loesch01") / "fulltext.txt").write_text("Text")
    antwort = await client.delete(f"/api/books/{buch}")
    assert antwort.status_code == 200 and antwort.json() == {"geloescht": True, "id": buch}
    assert rufe == [("DELETE", "/api/v1/ablage/knoten/k7")]
    assert await _noch_da(test_db, buch) == (0, 0, 0)
    assert not get_sidecar_path("loesch01", "cover.jpg").exists() and not get_storage_path("loesch01").exists()
    assert (await client.get(f"/api/books/{buch}/loeschfolgen")).status_code == 404


@pytest.mark.asyncio
async def test_scheitert_der_papierkorb_bleibt_alles(client: AsyncClient, test_db, orte, papierkorb):
    _, zustand = papierkorb
    zustand["antwort"] = WolkeFehler("Die Kellerwolke antwortet nicht (ConnectError)")
    buch = await _buch_mit_allem(test_db)
    save_cover("loesch01", b"jpeg")
    antwort = await client.delete(f"/api/books/{buch}")
    assert antwort.status_code == 502
    assert antwort.json()["detail"] == "Nicht gelöscht, das Buch bleibt: Die Kellerwolke antwortet nicht (ConnectError)"
    assert await _noch_da(test_db, buch) == (1, 2, 1)
    assert get_sidecar_path("loesch01", "cover.jpg").exists()


@pytest.mark.asyncio
async def test_ohne_angebundene_kellerwolke_wird_nichts_geloescht(client: AsyncClient, test_db, orte, monkeypatch):
    monkeypatch.setattr(Wolke, "bereit", property(lambda _s: False))
    buch = await _buch_mit_allem(test_db)
    antwort = await client.delete(f"/api/books/{buch}")
    assert antwort.status_code == 502 and "nicht angebunden" in antwort.json()["detail"]
    assert await _noch_da(test_db, buch) == (1, 2, 1)


@pytest.mark.asyncio
async def test_fehlt_die_datei_dort_schon_wird_trotzdem_geloescht(client: AsyncClient, test_db, orte, papierkorb):
    _, zustand = papierkorb
    zustand["antwort"] = WolkeFehler("Nicht gefunden", 404)
    buch = await _buch_mit_allem(test_db)
    assert (await client.delete(f"/api/books/{buch}")).status_code == 200
    assert await _noch_da(test_db, buch) == (0, 0, 0)


@pytest.mark.asyncio
async def test_unbekanntes_buch(client: AsyncClient, test_db, orte):
    assert (await client.get("/api/books/99999/loeschfolgen")).status_code == 404
    assert (await client.delete("/api/books/99999")).status_code == 404
