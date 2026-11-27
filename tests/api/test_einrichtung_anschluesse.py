"""Anschlüsse und Schlüsseldatei (BF-82): Kellerwolke, Leitstelle, Vertonung und Nachschlag mit Adresse und "Verbindung prüfen". Der
Schlüssel geht nur in die eigene Schlüsseldatei (Modus 0600) und nie zurück; eine Datei aus der Einrichtung gilt weiter, bis in
der App einer eingetragen ist. Gegenstellen sind Antworten aus einem Netz im Speicher, nie die echten."""

from __future__ import annotations

import json
import stat

import httpx
import pytest

from backend.app.ablage.wolke import wolke
from backend.app.core import anmeldung as anmeldung_modul, schluessel
from backend.app.core.config import settings
from backend.app.einrichtung import anschluesse
from backend.app.services.ki import ki
from tests.api.einrichtung_hilfen import APP_ZUGANG, LEITSTELLE, WOLKE, json_antwort, netz, neu, orte  # noqa: F401 - Fixtures
from tests.api.vertonung_hilfen import VERTONUNG, vertonung  # noqa: F401 - Fixture

pytestmark = pytest.mark.asyncio
LEITSTELLE_SCHLUESSEL = "ls_probe_schluessel_abcdef"


def _gegenstellen(monkeypatch, *, wolke_ok: bool = True) -> list[httpx.Request]:
    gesehen: list[httpx.Request] = []

    def ich(a: httpx.Request) -> httpx.Response:
        gesehen.append(a)
        if a.headers.get("authorization") != f"Bearer {APP_ZUGANG}" or not wolke_ok:
            return httpx.Response(401, json={"detail": "unbekannt"})
        return httpx.Response(200, json={"app": "BücherFreunde", "konto": "mira"})

    def modelle(a: httpx.Request) -> httpx.Response:
        if a.headers.get("authorization") != f"Bearer {LEITSTELLE_SCHLUESSEL}":
            return httpx.Response(401, json={"detail": "Schlüssel unbekannt", "grund": "schluessel_ungueltig"})
        return httpx.Response(200, json={"data": [{"id": "probe/modell-a"}, {"id": "probe/modell-b"}]})

    monkeypatch.setattr(anschluesse, "_client", netz({
        "GET /api/v1/ablage/ich": ich, "GET /v1/models": modelle,
        "GET /api/v1/buecher": json_antwort({"buecher": [{"kennung": "lex", "titel": "Probelexikon"}]}),
    }))
    return gesehen


async def test_schluessel_geht_nur_in_die_eigene_datei_und_nie_zurueck(neu, client_ohne_auth, monkeypatch):
    _gegenstellen(monkeypatch)
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    r = await client_ohne_auth.put("/api/einrichtung/anschluesse/leitstelle", json={"adresse": LEITSTELLE, "schluessel": LEITSTELLE_SCHLUESSEL})
    assert r.status_code == 200 and r.json()["angewandt"], r.text
    datei = settings.schluessel_pfad
    assert stat.S_IMODE(datei.stat().st_mode) == 0o600
    assert json.loads(datei.read_text())["schluessel"] == {"leitstelle": LEITSTELLE_SCHLUESSEL}
    liste = await client_ohne_auth.get("/api/einrichtung/anschluesse")
    assert LEITSTELLE_SCHLUESSEL not in liste.text and LEITSTELLE_SCHLUESSEL not in r.text
    eintrag = {a["art"]: a for a in liste.json()}["leitstelle"]
    assert eintrag["adresse"] == LEITSTELLE and eintrag["herkunft"] == "app"
    assert eintrag["schluessel"] == {"eingetragen": True, "herkunft": "app", "vorgemerkt": False}
    assert eintrag["pruefung"]["ok"] and eintrag["pruefung"]["text"] == "KI mit 2 Modellen"
    assert ki.bereit and settings.leitstelle_adresse == LEITSTELLE, "die KI liest denselben Schlüsselbund"
    assert [p.name for p in datei.parent.iterdir()] == [datei.name], "keine Teildatei bleibt liegen"


async def test_falscher_schluessel_wird_nicht_eingetragen_der_alte_gilt(neu, client_ohne_auth, monkeypatch):
    _gegenstellen(monkeypatch)
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    await client_ohne_auth.put("/api/einrichtung/anschluesse/leitstelle", json={"adresse": LEITSTELLE, "schluessel": LEITSTELLE_SCHLUESSEL})
    r = await client_ohne_auth.put("/api/einrichtung/anschluesse/leitstelle", json={"adresse": LEITSTELLE, "schluessel": "ganz-falscher-schluessel"})
    assert r.status_code == 422 and r.json()["detail"].startswith("Verbindung: ") and "Schlüssel" in r.json()["detail"]
    assert schluessel.lesen(schluessel.Art.LEITSTELLE) == LEITSTELLE_SCHLUESSEL
    p = (await client_ohne_auth.post("/api/einrichtung/anschluesse/kellerwolke/pruefen", json={"adresse": WOLKE, "schluessel": "kw_app_falsch_123"})).json()
    assert p["ok"] is False and p["grund"] == "Die Kellerwolke kennt diesen App-Zugang nicht"
    p = (await client_ohne_auth.post("/api/einrichtung/anschluesse/kellerwolke/pruefen", json={})).json()
    assert p == p | {"ok": False, "grund": "Keine Adresse eingetragen"}


async def test_datei_der_einrichtung_gilt_weiter_bis_die_app_einen_eintraegt(neu, tmp_path, monkeypatch):
    alt = tmp_path / "einrichtung" / "leitstelle.schluessel"
    alt.parent.mkdir()
    alt.write_text("aus_der_einrichtung_123\n")
    monkeypatch.setattr(settings, "leitstelle_schluessel_datei", str(alt))
    assert schluessel.lesen(schluessel.Art.LEITSTELLE) == "aus_der_einrichtung_123"
    assert schluessel.stand(schluessel.Art.LEITSTELLE).herkunft == "einrichtung"
    schluessel.eintragen(schluessel.Art.LEITSTELLE, "aus_der_app_456")
    assert schluessel.lesen(schluessel.Art.LEITSTELLE) == "aus_der_app_456"
    assert alt.read_text() == "aus_der_einrichtung_123\n", "die Datei der Einrichtung bleibt unberührt"


async def test_nachschlag_ohne_schluessel(neu, client_ohne_auth, monkeypatch):
    _gegenstellen(monkeypatch)
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    r = await client_ohne_auth.put("/api/einrichtung/anschluesse/nachschlag", json={"adresse": "https://nachschlag.probe.test", "schluessel": "irgendein-schluessel"})
    assert r.status_code == 422 and "keinen" in r.json()["detail"]
    r = await client_ohne_auth.put("/api/einrichtung/anschluesse/nachschlag", json={"adresse": "https://nachschlag.probe.test/"})
    assert r.status_code == 200 and settings.nachschlag_url == "https://nachschlag.probe.test"
    n = {a["art"]: a for a in (await client_ohne_auth.get("/api/einrichtung/anschluesse")).json()}["nachschlag"]
    assert n["schluessel"] is None and n["pruefung"]["text"] == "1 Lexika und Handbücher"
    assert (await client_ohne_auth.put("/api/einrichtung/anschluesse/nachschlag", json={"adresse": "ftp://x"})).status_code == 422


async def test_vertonung_ohne_eigenen_schluessel_mit_stimmen_und_freigabe(neu, vertonung, client_ohne_auth, monkeypatch):
    monkeypatch.setattr(settings, "vertonung_url", "")
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    p = (await client_ohne_auth.post("/api/einrichtung/anschluesse/vertonung/pruefen", json={"adresse": VERTONUNG})).json()
    assert p["ok"] and p["text"].startswith("Stimmen: 2 eingebaut, 1 fremd; ") and "in der Vertonung unter Private Stimmen für" in p["text"]
    assert vertonung.anfragen[-1].headers["authorization"].startswith("Bearer kw_app_"), "der App-Zugang der Kellerwolke"
    r = await client_ohne_auth.put("/api/einrichtung/anschluesse/vertonung", json={"adresse": VERTONUNG + "/"})
    assert r.status_code == 200 and settings.vertonung_url == VERTONUNG
    v = {a["art"]: a for a in (await client_ohne_auth.get("/api/einrichtung/anschluesse")).json()}["vertonung"]
    assert (v["schluessel"], v["herkunft"], v["pruefung"]["ok"]) == (None, "app", True)
    r = await client_ohne_auth.put("/api/einrichtung/anschluesse/vertonung", json={"adresse": VERTONUNG, "schluessel": "irgendein-schluessel"})
    assert r.status_code == 422 and "keinen" in r.json()["detail"]
    vertonung.privat_frei = True
    p = (await client_ohne_auth.post("/api/einrichtung/anschluesse/vertonung/pruefen", json={})).json()
    assert p["text"] == "Stimmen: 2 eingebaut, 1 fremd, 1 privat"
    vertonung.ablehnen = (401, "Anmeldung erforderlich")
    p = (await client_ohne_auth.post("/api/einrichtung/anschluesse/vertonung/pruefen", json={})).json()
    assert p["ok"] is False and "lässt das nicht zu" in p["grund"]
    r = await client_ohne_auth.put("/api/einrichtung/anschluesse/vertonung", json={"adresse": "https://andere-vertonung.probe.test"})
    assert r.status_code == 422 and settings.vertonung_url == VERTONUNG, "die alte gilt weiter"


async def test_vertonung_ohne_app_zugang_der_kellerwolke_nennt_den_grund(neu, client_ohne_auth):
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    p = (await client_ohne_auth.post("/api/einrichtung/anschluesse/vertonung/pruefen", json={"adresse": VERTONUNG})).json()
    assert p["ok"] is False and "App-Zugang der Kellerwolke" in p["grund"], "geprüft wird ohne Aufruf, der Verbund hält vorher an"


async def test_konto_mit_der_kellerwolke_traegt_adresse_und_schluessel_ein(neu, client_ohne_auth, monkeypatch):
    gesehen = _gegenstellen(monkeypatch)
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    r = await client_ohne_auth.post("/api/einrichtung/konto/kellerwolke", json={"adresse": WOLKE, "schluessel": APP_ZUGANG})
    assert r.status_code == 200 and r.json() == {"anmeldung": "kellerwolke", "app": "BücherFreunde", "besitzer": "mira"}
    assert gesehen[-1].url.host == "wolke.probe.test"
    assert APP_ZUGANG not in r.text and wolke.bereit and settings.kellerwolke_url == WOLKE
    assert anmeldung_modul.anmeldung.eigene is None, "die Anmeldung gilt jetzt über die Kellerwolke"
    e = (await client_ohne_auth.get("/api/einrichtung")).json()
    assert e["anmeldung"] == "kellerwolke" and e["konto"]
    # ein zweites Konto gibt es nicht; ohne Anmeldung ist die Einrichtung jetzt zu
    assert (await client_ohne_auth.post("/api/einrichtung/konto/kellerwolke", json={"adresse": WOLKE, "schluessel": APP_ZUGANG})).status_code == 401


async def test_ohne_anmeldung_nur_auf_einer_neuen_installation(neu, client, client_ohne_auth, monkeypatch):
    _gegenstellen(monkeypatch)
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    await client_ohne_auth.post("/api/anmeldung/einrichten", json={"kennung": "Mira Probe", "passwort": "ein langes Kennwort"})
    assert (await client_ohne_auth.get("/api/einrichtung/anschluesse")).status_code == 401
    assert (await client.get("/api/einrichtung/anschluesse")).status_code == 200


async def test_pruefwege_vor_dem_ersten_konto_nur_https_mit_namen_und_selten(neu, client, client_ohne_auth, monkeypatch):
    from backend.app.einrichtung import zugang

    _gegenstellen(monkeypatch)
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    pruefen = "/api/einrichtung/anschluesse/kellerwolke/pruefen"
    for adresse in ("http://wolke.probe.test", "https://192.168.10.20", "https://[fd00::1]", "https://localhost", "https://wolke.localhost",
                    "https://wolke.probe.test:80", "https://wolke.probe.test:22", "https://wolke.probe.test:12x"):
        r = await client_ohne_auth.post(pruefen, json={"adresse": adresse, "schluessel": APP_ZUGANG})
        assert r.status_code == 422 and r.json()["detail"].startswith("Adresse:"), (adresse, r.text)
    for weg, koerper in (("/api/einrichtung/konto/kellerwolke", {"adresse": "https://10.0.0.5", "schluessel": APP_ZUGANG}),
                         ("/api/einrichtung/umzug/verbinden", {"adresse": "https://127.0.0.1", "code": "ABCD-EFGH"})):
        assert (await client_ohne_auth.post(weg, json=koerper)).status_code == 422, weg
    assert (await client_ohne_auth.put("/api/einrichtung/anschluesse/leitstelle", json={"adresse": "https://172.16.0.9"})).status_code == 422
    for adresse in ("https://wolke.probe.test", "https://wolke.probe.test:443", "https://wolke.probe.test:8443"):
        assert (await client_ohne_auth.post(pruefen, json={"adresse": adresse, "schluessel": APP_ZUGANG})).status_code == 200, adresse

    monkeypatch.setattr(settings, "einrichtung_pruefungen_je_minute", 3)
    zugang._zuletzt.clear()
    jetzt = [1000.0]
    monkeypatch.setattr(zugang, "uhr", lambda: jetzt[0])
    for _ in range(3):
        assert (await client_ohne_auth.post(pruefen, json={"adresse": WOLKE, "schluessel": APP_ZUGANG})).status_code == 200
    r = await client_ohne_auth.post(pruefen, json={"adresse": WOLKE, "schluessel": APP_ZUGANG})
    assert r.status_code == 429 and r.headers["Retry-After"] == "61" and "Zu viele" in r.json()["detail"]
    jetzt[0] += 61
    assert (await client_ohne_auth.post(pruefen, json={"adresse": WOLKE, "schluessel": APP_ZUGANG})).status_code == 200

    # nach dem ersten Konto: nur angemeldet, dann ohne diese Grenzen
    await client_ohne_auth.post("/api/anmeldung/einrichten", json={"kennung": "Mira Probe", "passwort": "ein langes Kennwort"})
    assert (await client_ohne_auth.post(pruefen, json={"adresse": WOLKE, "schluessel": APP_ZUGANG})).status_code == 401
    for _ in range(5):
        r = await client.post(pruefen, json={"adresse": "https://192.168.10.20:8443", "schluessel": APP_ZUGANG})
        assert r.status_code == 200, r.text
