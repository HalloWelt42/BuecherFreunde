"""Anbieterweg für Fundus: nur mit App-Schlüssel, Treffer mit der besten Seite, Seiten lesen, Bestand."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.fundus import _beste_seiten, _woerter
from backend.app.core.config import settings
from backend.app.main import app
from backend.app.services.seiten import seiten_aus
from tests.api.conftest import FUNDUS_SCHLUESSEL, SITZUNG, buch_erstellen

SEITEN = ["Vorwort ohne Inhalt", "Die Photosynthese braucht Licht.", "Chlorophyll und Photosynthese im Blatt"]


@pytest.fixture
def ablage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    ordner = tmp_path / "fu" / "nd" / "fundushash"
    ordner.mkdir(parents=True)
    (ordner / "fulltext.txt").write_text("\f".join(SEITEN), encoding="utf-8")
    return tmp_path


@pytest.fixture
async def fundus(test_db, ablage):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                           headers={"Authorization": f"Bearer {FUNDUS_SCHLUESSEL}"}) as c:
        yield c


def test_seiten_und_beste_seite():
    seiten = seiten_aus("\f".join(SEITEN), 3)
    assert len(seiten) == 3
    beste = _beste_seiten(seiten, _woerter("Wie hängen Chlorophyll und Photosynthese zusammen?"))
    assert beste[0][0] == 3 and beste[1][0] == 2


async def test_ohne_app_schluessel_abgewiesen(client_ohne_auth):
    r = await client_ohne_auth.get("/api/v1/fundus/suche?q=test")
    assert r.status_code == 401
    r = await client_ohne_auth.get("/api/v1/fundus/suche?q=test", headers={"Authorization": f"Bearer {SITZUNG}"})
    assert r.status_code == 401                 # eine Sitzung eines Menschen ist kein App-Schlüssel


async def test_app_darf_keine_menschenwege(client_ohne_auth):
    r = await client_ohne_auth.get("/api/books", headers={"Authorization": f"Bearer {FUNDUS_SCHLUESSEL}"})
    assert r.status_code == 403


async def test_suche_inhalt_bestand(fundus, test_db):
    buch = await buch_erstellen(test_db, hash="fundushash", fts_content=" ".join(SEITEN), page_count=3)
    r = await fundus.get("/api/v1/fundus/suche", params={"q": "Was ist Photosynthese und Chlorophyll?"})
    assert r.status_code == 200
    t = r.json()["treffer"][0]
    assert t["buch"] == buch and t["seite"] == 3 and "Chlorophyll" in t["auszug"]
    assert t["verweise"][0]["pfad"].startswith(f"/book/{buch}/read?page=3")

    r = await fundus.get(f"/api/v1/fundus/inhalt/{buch}", params={"von": 2, "bis": 3})
    assert [s["seite"] for s in r.json()["seiten"]] == [2, 3]

    r = await fundus.get("/api/v1/fundus/bestand")
    b = r.json()["buecher"][0]
    assert b["buch"] == buch and b["volltext_zeichen"] > 0 and b["lesestand"] is False
