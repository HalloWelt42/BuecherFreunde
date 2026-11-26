"""Einordnen über die Leitstelle (BF-10): derselbe Anschluss wie die Vorprüfung, gegen eine Attrappe; ohne Leitstelle keine
Vorschläge mit Grund."""

import json
from urllib.parse import unquote

import httpx

from backend.app.core.config import settings
from backend.app.core.database import Database
from backend.app.services.ki import ki
from tests.api.conftest import buch_erstellen
from tests.api.test_ausfuehren import LEITSTELLE, chat_antwort, leitstelle  # noqa: F401 - Attrappe der Leitstelle


async def test_ohne_leitstelle_keine_vorschlaege(client, test_db, monkeypatch):
    monkeypatch.setattr(settings, "leitstelle_adresse", "")
    buch = await buch_erstellen(test_db)
    r = await client.post(f"/api/ai/buch/{buch}/kategorisieren")
    assert r.status_code == 503 and "Keine Leitstelle" in r.json()["detail"]
    assert (await client.get("/api/ai/status")).json()["aktiviert"] is False
    assert (await client.get("/api/config/oberflaeche")).json()["anschluesse"]["ki"] is False
    assert (await client.get("/api/config")).json()["lm_studio"]["aktiviert"] is False
    assert (await client.get("/api/ai/scan")).status_code in (404, 405)            # keine eigene Suche nach Modell-Läufern mehr


async def test_einordnen_ueber_die_leitstelle(client, test_db, leitstelle, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "ki_modell", "qwen/qwen3-next-80b")
    modelle = leitstelle.antwort
    leitstelle.antwort = lambda r: modelle(r) if r.url.path == "/v1/models" else chat_antwort(
        'Gern: [{"kategorie": "Informatik", "konfidenz": 0.9}, {"kategorie": "Mathematik"}]')
    buch = await buch_erstellen(test_db, title="Rechnen mit Python")
    r = (await client.post(f"/api/ai/buch/{buch}/kategorisieren")).json()
    assert r["vorschlaege"] == [{"kategorie": "Informatik", "konfidenz": 0.9}, {"kategorie": "Mathematik", "konfidenz": 0.5}]
    anfrage = leitstelle.anfragen[-1]
    koerper = json.loads(anfrage.content)
    assert anfrage.url == httpx.URL(f"{LEITSTELLE}/v1/chat/completions") and koerper["model"] == "qwen/qwen3-next-80b"
    assert koerper["messages"][0]["role"] == "system" and "Titel: Rechnen mit Python" in koerper["messages"][1]["content"]
    assert unquote(anfrage.headers["X-Leitstelle-Titel"]) == "BücherFreunde: Einordnen: Rechnen mit Python"
    assert "X-Leitstelle-Prioritaet" not in anfrage.headers                           # ein Mensch wartet: Vorgabe der App
    assert (await client.get("/api/config/oberflaeche")).json()["anschluesse"]["ki"] is True
    s = (await client.get("/api/ai/status")).json()
    assert s == {"erreichbar": True, "grund": "", "modelle": ["qwen/qwen3-next-80b", "qwen/qwen3-coder-next"], "url": LEITSTELLE,
                 "modell": "qwen/qwen3-next-80b", "gewaehlt": "", "aktiviert": True}


async def test_modell_waehlen_und_adresse_nur_in_der_einrichtung(client, test_db, leitstelle, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "ki_modell", "qwen/qwen3-next-80b")
    r = await client.patch("/api/ai/config", json={"lm_studio_model": "qwen/qwen3-coder-next"})
    assert r.json() == {"url": LEITSTELLE, "modell": "qwen/qwen3-coder-next", "aktiviert": True}
    assert (await test_db.fetch_one("SELECT value FROM app_settings WHERE key = 'ki_modell'"))["value"] == "qwen/qwen3-coder-next"
    ki._wahl = None
    assert (await ki.gilt())[0] == "qwen/qwen3-coder-next"                             # gilt auch nach einem Neustart
    r = await client.patch("/api/ai/config", json={"lm_studio_url": "http://rechner:1234/v1"})
    assert r.status_code == 422 and "LEITSTELLE_ADRESSE" in r.json()["detail"]


async def test_nicht_angebotene_wahl_gilt_nicht(client, test_db, leitstelle, monkeypatch):  # noqa: F811
    """Im Betrieb stand ein Name der früheren Anbindung als Wahl, den die Leitstelle nicht kennt: es gilt die Vorgabe, mit
    Grund; die Wahl bleibt stehen."""
    monkeypatch.setattr(settings, "ki_modell", "qwen/qwen3-next-80b")
    await test_db.execute("INSERT OR REPLACE INTO app_settings(key, value) VALUES ('ki_modell', 'qwen3-next-80b-a3b-instruct-mlx')")
    await test_db.commit()
    modelle = leitstelle.antwort
    leitstelle.antwort = lambda r: modelle(r) if r.url.path == "/v1/models" else chat_antwort('[{"kategorie": "Informatik"}]')
    buch = await buch_erstellen(test_db)
    assert (await client.post(f"/api/ai/buch/{buch}/kategorisieren")).status_code == 200
    assert json.loads(leitstelle.anfragen[-1].content)["model"] == "qwen/qwen3-next-80b"
    s = (await client.get("/api/ai/status")).json()
    assert s["erreichbar"] and s["modell"] == "qwen/qwen3-next-80b" and s["gewaehlt"] == "qwen3-next-80b-a3b-instruct-mlx"
    assert s["grund"] == "Das gewählte Modell qwen3-next-80b-a3b-instruct-mlx bietet die Leitstelle nicht an; es gilt die Vorgabe qwen/qwen3-next-80b"
    v = {x["kennung"]: x for x in (await client.get("/api/verbindungen")).json()}
    assert v["leitstelle"]["stand"] == "warn" and v["leitstelle"]["text"] == s["grund"]
    assert (await client.get("/api/ai/config")).json()["modell"] == "qwen/qwen3-next-80b"
    assert (await test_db.fetch_one("SELECT value FROM app_settings WHERE key = 'ki_modell'"))["value"] == "qwen3-next-80b-a3b-instruct-mlx"


async def test_fruehere_wahl_nur_wenn_angeboten(client, test_db, leitstelle, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "ki_modell", "qwen/qwen3-next-80b")
    await test_db.execute("DELETE FROM app_settings WHERE key = 'ki_modell'")
    await test_db.execute("INSERT OR REPLACE INTO app_settings(key, value) VALUES ('lm_studio_model', 'qwen3-next-80b-a3b-instruct-mlx')")
    await test_db.commit()
    assert await ki.gilt() == ("qwen/qwen3-next-80b", "")                               # unbekannt: keine Wahl, kein Grund
    assert await test_db.fetch_one("SELECT value FROM app_settings WHERE key = 'ki_modell'") is None
    await test_db.execute("UPDATE app_settings SET value = 'qwen3-coder-next' WHERE key = 'lm_studio_model'")
    await test_db.commit()
    ki._wahl = None
    assert await ki.gilt() == ("qwen3-coder-next", "")                                  # die Leitstelle kennt ihn ohne Anbieter
    assert (await test_db.fetch_one("SELECT value FROM app_settings WHERE key = 'ki_modell'"))["value"] == "qwen3-coder-next"
    assert (await test_db.fetch_one("SELECT value FROM app_settings WHERE key = 'lm_studio_model'"))["value"] == "qwen3-coder-next"


async def test_gesperrt_wird_nicht_wiederholt(client, test_db, leitstelle):  # noqa: F811
    leitstelle.antwort = lambda r: httpx.Response(429, json={"error": {"code": "gesperrt", "message": "von Hand gesperrt"}})
    buch = await buch_erstellen(test_db)
    r = await client.post(f"/api/ai/buch/{buch}/kategorisieren")
    assert r.status_code == 503 and "gesperrt" in r.json()["detail"] and len(leitstelle.anfragen) == 1


async def test_kein_kopieren_beim_start(tmp_path):
    d = Database(db_path=tmp_path / "alt.db")
    await d.connect()
    await d.execute("INSERT OR REPLACE INTO app_settings(key, value) VALUES ('lm_studio_model', 'qwen3-next-80b-a3b-instruct-mlx')")
    await d.commit()
    await d.disconnect()
    await d.connect()
    assert await d.fetch_one("SELECT value FROM app_settings WHERE key = 'ki_modell'") is None
    await d.disconnect()
