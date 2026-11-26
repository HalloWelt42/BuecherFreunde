"""Zustand der Ersteinrichtung (BF-82): nur eine neue Installation sieht sie, eine laufende nie und wird durch sie nie verändert.
Schritte mit Pflicht und Überspringen, Weiter gesperrt mit Grund, Abschluss, wiederaufnehmbar nach einem Neustart. Alles mit
eigenen Orten in tmp_path."""

from __future__ import annotations

import pytest

from backend.app.ablage import orte as ablage_orte
from backend.app.core.config import settings
from backend.app.core.database import Database, db
from backend.app.einrichtung import zustand
from tests.api.conftest import buch_erstellen
from tests.api.einrichtung_hilfen import laufend, neu, orte  # noqa: F401 - Fixtures

pytestmark = pytest.mark.asyncio


def test_neu_ist_nur_leerer_bestand_ohne_marker(orte):
    """Die Erkennung beim Start (ablage/orte.py): leer und ohne Marker neu, mit Datenbank oder Marker nicht."""
    assert ablage_orte.einrichten() is True
    assert ablage_orte.einrichten() is False, "danach trägt jeder dauerhafte Ort seine Markerdatei"
    settings.database_path.write_bytes(b"")
    (settings.storage_dir / ablage_orte.MARKER).unlink()
    with pytest.raises(RuntimeError, match="eingehängt"):
        ablage_orte.einrichten()                            # Datenbank da, Volltexte leer ohne Marker: nie still als neu
    (settings.storage_dir / "ab").mkdir()
    assert ablage_orte.einrichten() is False, "eine Datenbank heißt: laufende Installation"


async def test_laufende_installation_sieht_die_einrichtung_nie(laufend, client, client_ohne_auth):
    e = (await client_ohne_auth.get("/api/einrichtung")).json()
    assert (e["modus"], e["zeigen"], e["schritte"], e["ausgangslagen"]) == ("aus", False, [], [])
    assert (await client.get("/api/einrichtung")).json()["zeigen"] is False
    # ohne Anmeldung geht nichts, mit Anmeldung ändert die Ersteinrichtung nichts
    for weg, koerper in (("/api/einrichtung/ausgangslage", {"ausgangslage": "neu"}), ("/api/einrichtung/wiederherstellen", {"quelle": "geraet", "kennung": "x"}),
                         ("/api/einrichtung/umzug/verbinden", {"adresse": "https://alt.probe.test", "code": "ABCD-EFGH"})):
        assert (await client_ohne_auth.post(weg, json=koerper)).status_code == 401
        assert (await client.post(weg, json=koerper)).status_code == 409, weg
    assert (await client_ohne_auth.get("/api/einrichtung/orte")).status_code == 401
    assert (await db.fetch_one("SELECT modus, ausgangslage FROM einrichtung"))["modus"] == "aus"


async def test_ohne_gemerkte_zeile_gilt_laufend(test_db, client):
    """Eine Datenbank, die nie mit dieser Fassung gestartet ist (etwa in Tests), zeigt den Assistenten nie."""
    assert (await client.get("/api/einrichtung")).json()["modus"] == "aus"


async def test_einmal_gemerkt_bleibt_es(laufend):
    await zustand.erkennen(True)                          # ein späterer Start mit leerem Ort macht daraus keine neue
    assert await zustand.modus() == "aus"


async def test_neue_installation_fuehrt_durch_die_schritte(neu, client_ohne_auth):
    e = (await client_ohne_auth.get("/api/einrichtung")).json()
    assert e["modus"] == "neu" and e["zeigen"] and e["ausgangslage"] is None
    assert [a["schluessel"] for a in e["ausgangslagen"]] == ["neu", "sicherung", "kellerwolke", "umzug"]
    e = (await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})).json()
    assert [s["schluessel"] for s in e["schritte"]] == ["konto", "orte", "anschluesse", "katalog", "familie", "buecher", "abschluss"]
    assert e["schritt"] == "konto" and not e["konto"]
    konto = e["schritte"][0]
    assert konto["pflicht"] and not konto["weiter"] and "Konto" in konto["grund"]
    # Pflicht lässt sich nicht überspringen, das Konto nicht von Hand setzen
    assert (await client_ohne_auth.post("/api/einrichtung/schritte/orte", json={"aktion": "ueberspringen"})).status_code == 422
    assert (await client_ohne_auth.post("/api/einrichtung/schritte/konto", json={"aktion": "erledigt"})).status_code == 422
    assert (await client_ohne_auth.post("/api/einrichtung/schritte/sicherung", json={"aktion": "erledigt"})).status_code == 404


async def test_orte_sperren_weiter_ohne_marker(neu, client_ohne_auth):
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    o = (await client_ohne_auth.get("/api/einrichtung/orte")).json()
    assert not o["weiter"] and "Bestand" in o["grund"]
    schlecht = {x["kennung"]: x for x in o["orte"] if x["stand"] == "schlecht"}
    assert schlecht["bestand"]["text"].startswith("Ohne Markerdatei")
    r = await client_ohne_auth.post("/api/einrichtung/schritte/orte", json={"aktion": "erledigt"})
    assert r.status_code == 409 and "Nicht bereit" in r.json()["detail"]
    ablage_orte.einrichten()                                # wie beim ersten Start: jeder Ort bekommt seinen Marker
    o = (await client_ohne_auth.get("/api/einrichtung/orte")).json()
    assert o["weiter"], o
    e = (await client_ohne_auth.post("/api/einrichtung/schritte/orte", json={"aktion": "erledigt"})).json()
    assert {s["schluessel"]: s["stand"] for s in e["schritte"]}["orte"] == "erledigt"


async def test_mit_konto_nur_noch_angemeldet_und_abschluss(neu, client, client_ohne_auth):
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    r = await client_ohne_auth.post("/api/anmeldung/einrichten", json={"kennung": "Mira Probe", "passwort": "ein langes Kennwort"})
    assert r.status_code == 201
    assert (await client_ohne_auth.get("/api/einrichtung/orte")).status_code == 401, "ab dem Konto nur angemeldet"
    e = (await client.get("/api/einrichtung")).json()
    assert e["konto"] and e["schritte"][0]["stand"] == "erledigt" and e["schritt"] == "orte"
    assert (await client.post("/api/einrichtung/abschliessen")).status_code == 409, "die Orte sind Pflicht"
    ablage_orte.einrichten()
    await client.post("/api/einrichtung/schritte/orte", json={"aktion": "erledigt"})
    for s in ("anschluesse", "familie", "buecher"):
        assert (await client.post(f"/api/einrichtung/schritte/{s}", json={"aktion": "ueberspringen"})).status_code == 200
    k = (await client.post("/api/einrichtung/katalog", json={"wahl": "leer"})).json()
    assert k == {"angewandt": True, "aenderung": None}
    e = (await client.post("/api/einrichtung/abschliessen")).json()
    assert e["modus"] == "aus" and not e["zeigen"]
    u = {s["schluessel"]: (s["stand"], s["text"]) for s in (await client.get("/api/einrichtung/uebersicht")).json()}
    assert u["katalog"] == ("erledigt", "Leer begonnen") and u["familie"][0] == "uebersprungen" and u["abschluss"][0] == "erledigt"
    assert (await client.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})).status_code == 409


async def test_wiederaufnehmbar_nach_neustart(neu, client_ohne_auth):
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    ablage_orte.einrichten()
    await client_ohne_auth.post("/api/einrichtung/schritte/orte", json={"aktion": "erledigt"})
    nochmal = Database(db_path=db.db_path)                  # wie ein Neustart: frisch verbunden, derselbe Bestand
    await nochmal.connect()
    z = await nochmal.fetch_one("SELECT modus, ausgangslage FROM einrichtung")
    s = await nochmal.fetch_one("SELECT stand FROM einrichtung_schritt WHERE schritt = 'orte'")
    await nochmal.disconnect()
    assert (z["modus"], z["ausgangslage"], s["stand"]) == ("neu", "neu", "erledigt")
    await zustand.erkennen(False)                           # der zweite Start sieht eine Datenbank, die Zeile bleibt
    assert (await client_ohne_auth.get("/api/einrichtung")).json()["schritt"] == "konto"


async def test_ausgangslage_wechselt_nicht_mehr_mit_buechern(neu, client_ohne_auth, test_db):
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    await buch_erstellen(test_db, title="Probebuch", hash="a" * 64)
    r = await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "sicherung"})
    assert r.status_code == 409 and (await db.fetch_one("SELECT ausgangslage FROM einrichtung"))["ausgangslage"] == "neu"
