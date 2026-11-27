"""Hilfen für die Tests der Ersteinrichtung (BF-82): eigene Orte und eigene Schlüsseldatei in `tmp_path`, ein altes Gerät als
eigene Probedatenbank, Sicherungen daraus, ein Netz aus Antworten statt echter Gegenstellen. Nichts davon berührt den Betrieb,
die echte Kellerwolke, die echte Leitstelle oder echte Sicherungen. Alle Namen und Titel sind erfunden."""

from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from backend.app.core.config import settings
from backend.app.core.database import Database
from backend.app.einrichtung import anschluesse, zugang, zustand
from backend.app.einrichtung.auftrag import auftraege
from backend.app.einrichtung.nachfuehren import nachfuehren
from backend.app.services import sicherung

FELDER = ("kellerwolke_url", "leitstelle_adresse", "vertonung_url", "nachschlag_url", "kellerwolke_schluessel_datei",
          "leitstelle_schluessel_datei")
WOLKE = "https://wolke.probe.test"
LEITSTELLE = "https://leitstelle.probe.test"
APP_ZUGANG = "kw_app_probe_zugang_0123456789"


@pytest.fixture
def orte(tmp_path, monkeypatch) -> Path:
    """Eigene Orte und eigene Schlüsseldatei; Anschlüsse leer, keine Pausen."""
    for name in ("storage_dir", "umschlaege_dir", "zwischen_dir", "import_dir", "suche_dir"):
        monkeypatch.setattr(settings, name, tmp_path / name)
    monkeypatch.setattr(settings, "database_dir", tmp_path / "bestand")
    monkeypatch.setattr(settings, "schluessel_datei", tmp_path / "zugang" / "schluessel.json")
    for feld in FELDER:
        monkeypatch.setattr(settings, feld, "")
    for feld in ("einrichtung_abstand_s", "persoenlich_abstand_s", "persoenlich_ruhe_s"):
        monkeypatch.setattr(settings, feld, 0)
    monkeypatch.setattr(settings, "einrichtung_pruefungen_je_minute", 100)    # die Grenze prüft ein eigener Test
    zugang._zuletzt.clear()
    (tmp_path / "bestand").mkdir()
    return tmp_path


@pytest_asyncio.fixture
async def neu(test_db, orte):
    """Eine neue Installation: beim ersten Start leerer Bestand ohne Markerdatei."""
    await zustand.erkennen(True)
    yield orte
    for a in auftraege().values():
        await a.stoppen()
    await nachfuehren.stoppen()
    await anschluesse.neu_verbinden()


@pytest_asyncio.fixture
async def laufend(test_db, orte):
    """Eine laufende Installation: beim Start mit diesem Stand war der Bestand schon da."""
    await zustand.erkennen(False)
    yield orte
    await anschluesse.neu_verbinden()


def netz(antworten: dict[str, Callable[[httpx.Request], httpx.Response]]) -> Callable[..., httpx.AsyncClient]:
    """Eine Verbindung, deren Antworten nach "METHODE Pfad" kommen; was fehlt, ist 404. Nichts geht hinaus."""
    def weiter(anfrage: httpx.Request) -> httpx.Response:
        tun = antworten.get(f"{anfrage.method} {anfrage.url.path}")
        return tun(anfrage) if tun else httpx.Response(404, json={"detail": "nicht da"})

    def client(*_a, **art) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(weiter), base_url=art.get("base_url") or (_a[0] if _a else ""))

    return client


async def altes_geraet(ordner: Path, fuellen: Callable) -> Path:
    """Eine eigene Probedatenbank als altes Gerät; `fuellen(datenbank)` legt an, was es haben soll."""
    ordner.mkdir(parents=True, exist_ok=True)
    alt = Database(db_path=ordner / "buecherfreunde.db")
    await alt.connect()
    await fuellen(alt)
    await alt.commit()
    await alt.disconnect()
    return ordner / "buecherfreunde.db"


def sicherung_von(datenbank: Path, monkeypatch, ziel: Path) -> Path:
    """Eine Sicherung des alten Geräts nach der Sicherungsregel, abgelegt in `ziel`."""
    with monkeypatch.context() as m:
        m.setattr(settings, "database_dir", datenbank.parent)
        lauf = sicherung.sichern(sicherung.Anlass.HAND)
    ziel.mkdir(parents=True, exist_ok=True)
    return Path(shutil.copy2(lauf.datei, ziel / lauf.datei.name))


def zaehlen(datenbank: Path, tabelle: str) -> int:
    with closing(sqlite3.connect(datenbank)) as v:
        return v.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0]


def json_antwort(daten, status: int = 200) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _a: httpx.Response(status, content=json.dumps(daten).encode(), headers={"content-type": "application/json"})


async def als_verwaltung(client) -> dict[str, str]:
    """Nach dem Wiederherstellen gibt es mehrere Profile: das erste Profil Verwaltung wählen (ohne PIN)."""
    from backend.app.core.database import db

    z = await db.fetch_one("SELECT id FROM profil WHERE rolle = 'verwaltung' ORDER BY sortierung, angelegt_am LIMIT 1")
    r = await client.post("/api/familie/wahl", json={"profil_id": z["id"]})
    assert r.status_code == 200, r.text
    return {"X-Profil": r.json()["schluessel"]}
