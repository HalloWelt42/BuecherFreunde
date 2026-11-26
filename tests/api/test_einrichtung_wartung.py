"""Wieder öffnen unter Wartung (BF-82): nur die Schritte von "Neu beginnen" ohne Konto; was der Assistent ändern würde, steht
als Liste da und gilt erst, wenn es angehakt und bestätigt ist. Gelöscht wird nichts, auch nicht beim Schließen ohne
Übernehmen. Eine laufende Probeinstallation in tmp_path, Gegenstellen aus einem Netz im Speicher."""

from __future__ import annotations

import httpx
import pytest

from backend.app.core import schluessel
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.einrichtung import anschluesse
from tests.api.conftest import buch_erstellen
from tests.api.einrichtung_hilfen import LEITSTELLE, laufend, netz, neu, orte  # noqa: F401 - Fixtures

pytestmark = pytest.mark.asyncio
NEUE_LEITSTELLE = "https://leitstelle-zwei.probe.test"


@pytest.fixture
def gegenstellen(monkeypatch):
    def modelle(a: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "probe/modell"}]})

    monkeypatch.setattr(settings, "sprechdienst", "")
    monkeypatch.setattr(anschluesse, "_client", netz({"GET /v1/models": modelle}))


async def _zaehlen() -> dict[str, int]:
    return {t: (await db.fetch_one(f"SELECT COUNT(*) AS n FROM {t}"))["n"] for t in ("books", "profil", "categories", "book_notes")}


async def test_wieder_oeffnen_aendert_nur_bestaetigtes_und_loescht_nichts(laufend, gegenstellen, client, test_db, monkeypatch):
    monkeypatch.setattr(settings, "leitstelle_adresse", LEITSTELLE)
    schluessel.eintragen(schluessel.Art.LEITSTELLE, "ls_alter_schluessel_1")
    buch = await buch_erstellen(test_db, title="Bleibt im Regal", hash="f" * 64)
    await db.execute("INSERT INTO book_notes(profil_id, book_id, content) SELECT id, ?, 'bleibt' FROM profil LIMIT 1", (buch,))
    await db.commit()
    vorher = await _zaehlen()

    e = (await client.post("/api/einrichtung/oeffnen")).json()
    assert e["modus"] == "wartung" and e["zeigen"] and e["ausgangslagen"] == []
    assert [s["schluessel"] for s in e["schritte"]] == ["orte", "anschluesse", "katalog", "familie", "buecher", "abschluss"]

    a = (await client.put("/api/einrichtung/anschluesse/leitstelle", json={"adresse": NEUE_LEITSTELLE, "schluessel": "ls_neuer_schluessel_2"})).json()
    assert a["angewandt"] is False and a["aenderung"]["was"] == f"Leitstelle: Adresse {NEUE_LEITSTELLE} und neuer Schlüssel"
    assert settings.leitstelle_adresse == LEITSTELLE and schluessel.lesen(schluessel.Art.LEITSTELLE) == "ls_alter_schluessel_1", "noch nichts geändert"
    assert schluessel.stand(schluessel.Art.LEITSTELLE).vorgemerkt
    k = (await client.post("/api/einrichtung/katalog", json={"wahl": "standard"})).json()
    p = (await client.post("/api/einrichtung/familie/profile", json={"name": "Kalle Probe", "rolle": "erwachsen"})).json()
    assert not k["angewandt"] and not p["angewandt"] and await _zaehlen() == vorher

    liste = (await client.get("/api/einrichtung/aenderungen")).json()
    assert [x["art"] for x in liste["aenderungen"]] == ["anschluss", "katalog", "profil"]
    assert set(liste["unveraendert"]) == {"Speicherorte", "Erste Bücher"}
    assert (await client.get("/api/einrichtung")).json()["aenderungen"] == 3
    assert (await client.post("/api/einrichtung/uebernehmen", json={"stand": "anders", "ids": []})).status_code == 409

    gewaehlt = [liste["aenderungen"][0]["id"], liste["aenderungen"][2]["id"]]
    u = (await client.post("/api/einrichtung/uebernehmen", json={"stand": liste["stand"], "ids": gewaehlt})).json()
    assert [x["art"] for x in u["uebernommen"]] == ["anschluss", "profil"] and u["verworfen"] == 1
    assert settings.leitstelle_adresse == NEUE_LEITSTELLE and schluessel.lesen(schluessel.Art.LEITSTELLE) == "ls_neuer_schluessel_2"
    nachher = await _zaehlen()
    assert nachher == vorher | {"profil": vorher["profil"] + 1}, "nur das neue Profil kam dazu; der Katalog blieb, nichts ging weg"
    assert (await client.get("/api/einrichtung")).json()["modus"] == "aus"


async def test_schliessen_ohne_uebernehmen_verwirft_vorgemerktes(laufend, gegenstellen, client, monkeypatch):
    monkeypatch.setattr(settings, "leitstelle_adresse", LEITSTELLE)
    schluessel.eintragen(schluessel.Art.LEITSTELLE, "ls_alter_schluessel_1")
    await client.post("/api/einrichtung/oeffnen")
    await client.put("/api/einrichtung/anschluesse/leitstelle", json={"adresse": NEUE_LEITSTELLE, "schluessel": "ls_neuer_schluessel_2"})
    e = (await client.post("/api/einrichtung/schliessen")).json()
    assert e["modus"] == "aus" and not schluessel.stand(schluessel.Art.LEITSTELLE).vorgemerkt
    assert schluessel.lesen(schluessel.Art.LEITSTELLE) == "ls_alter_schluessel_1" and settings.leitstelle_adresse == LEITSTELLE
    assert (await client.get("/api/einrichtung/aenderungen")).status_code == 409


async def test_wieder_oeffnen_nicht_waehrend_der_ersteinrichtung(neu, client_ohne_auth, client):
    assert (await client_ohne_auth.post("/api/einrichtung/oeffnen")).status_code == 401
    assert (await client.post("/api/einrichtung/oeffnen")).status_code == 409
