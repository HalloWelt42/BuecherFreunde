"""Ohne Kellerwolke, KI und Hausdienste: eigenes Konto, und die App nennt nur, was angeschlossen ist."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.core import eigene_anmeldung
from backend.app.core.config import settings
from backend.app.core.eigene_anmeldung import EigeneAnmeldung


@pytest.fixture
def eigene(test_db, monkeypatch):
    monkeypatch.setattr(eigene_anmeldung, "_SCRYPT", {"n": 2 ** 4, "r": 8, "p": 1, "dklen": 32})
    return EigeneAnmeldung()


@pytest.mark.asyncio
async def test_konto_anlegen_geht_genau_einmal(eigene):
    assert not await eigene.eingerichtet()
    with pytest.raises(eigene_anmeldung.Unbrauchbar):
        await eigene.einrichten("Anna", "kurz")
    token, konto = await eigene.einrichten("Anna", "langes Kennwort")
    assert konto.name == "Anna" and (await eigene.pruefen(token)).mensch
    with pytest.raises(eigene_anmeldung.NichtErlaubt):
        await eigene.einrichten("Bert", "langes Kennwort")


@pytest.mark.asyncio
async def test_anmelden_abmelden_und_kennwort_aendern(eigene):
    alt, konto = await eigene.einrichten("Anna", "langes Kennwort")
    token, _ = await eigene.anmelden("anna", "langes Kennwort")
    await eigene.abmelden(token)
    assert await eigene.pruefen(token) is None and await eigene.pruefen(alt) is not None
    with pytest.raises(eigene_anmeldung.NichtErlaubt):
        await eigene.kennwort_aendern(konto, "falsch", "neues Kennwort")
    await eigene.kennwort_aendern(konto, "langes Kennwort", "neues Kennwort")
    assert await eigene.pruefen(alt) is None, "alle Anmeldungen enden"
    assert (await eigene.anmelden("Anna", "neues Kennwort"))[1].name == "Anna"


@pytest.mark.asyncio
async def test_nach_vielen_fehlversuchen_wartezeit(test_db, monkeypatch):
    monkeypatch.setattr(eigene_anmeldung, "_SCRYPT", {"n": 2 ** 4, "r": 8, "p": 1, "dklen": 32})
    jetzt = [0.0]
    a = EigeneAnmeldung(uhr=lambda: jetzt[0])
    await a.einrichten("Anna", "langes Kennwort")
    for _ in range(eigene_anmeldung.FREI):
        with pytest.raises(eigene_anmeldung.Abgelehnt):
            await a.anmelden("Anna", "falsch")
    with pytest.raises(eigene_anmeldung.ZuVieleVersuche):
        await a.anmelden("Anna", "langes Kennwort")
    jetzt[0] = 1000
    assert (await a.anmelden("Anna", "langes Kennwort"))[1].name == "Anna"


@pytest.mark.asyncio
async def test_fremdes_und_app_schluessel_gelten_nicht(eigene):
    await eigene.einrichten("Anna", "langes Kennwort")
    for token in ("", "irgendwas", "kw_app_abc"):
        assert await eigene.pruefen(token) is None


@pytest.mark.asyncio
async def test_wege_der_anmeldung(eigene, monkeypatch):
    from backend.app.api import auth as wege

    monkeypatch.setattr(wege, "anmeldung", eigene)
    app = FastAPI()
    app.include_router(wege.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/anmeldung/app")).json() == {"name": "BücherFreunde", "art": "eigen", "kellerwolke": "", "besitzer": None, "eingerichtet": False}
        assert (await c.post("/api/anmeldung/einrichten", json={"kennung": "Anna", "passwort": "x"})).status_code == 422
        r = await c.post("/api/anmeldung/einrichten", json={"kennung": "Anna", "passwort": "langes Kennwort"})
        assert r.status_code == 201 and r.json()["konto"]["name"] == "Anna"
        assert (await c.post("/api/anmeldung/einrichten", json={"kennung": "Bert", "passwort": "langes Kennwort"})).status_code == 403
        assert (await c.get("/api/anmeldung/app")).json()["eingerichtet"]


@pytest.mark.asyncio
async def test_anschluesse_und_verbindungen_nennen_nur_was_da_ist(client, auth_headers, monkeypatch):
    for name in ("kellerwolke_url", "fundus_url", "assistent_url", "nachschlag_url", "vorlesen_url", "codeschmiede_url", "leitstelle_adresse"):
        monkeypatch.setattr(settings, name, "")
    monkeypatch.setattr(settings, "lm_studio_enabled", False)
    o = (await client.get("/api/config/oberflaeche", headers=auth_headers)).json()
    assert o["anschluesse"] == {"ablage": "geraet", "anmeldung": "eigen", "bedeutung": False, "assistent": "", "nachschlag": "https://de.wikipedia.org",
                                    "nachschlag_art": "netz", "ki": False, "vorlesen": False, "ausfuehren": False}
    assert (await client.get("/api/verbindungen", headers=auth_headers)).json() == []
