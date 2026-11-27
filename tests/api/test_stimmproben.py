"""Stimmproben (BF-114): einmal gesprochen und abgelegt, danach sofort da; der Auftrag vertont vorab jede Stimme, ruht ohne
Vertonung und bleibt von Hand angehalten stehen. Gegen die Attrappe der Vertonung, nur Katalogstimmen und erfundene Klonstimmen."""

from __future__ import annotations

import pytest

from backend.app.core.config import settings
from backend.app.vorlesen import proben, stimmen
from backend.app.vorlesen.proben import probenwache, stimmproben
from tests.api.familie_hilfen import familie_anlegen
from tests.api.vertonung_hilfen import KLON, vertonung  # noqa: F401 - Fixture

TON = "/api/v1/sprechen"
SERENA = "katalog:serena"


@pytest.fixture(autouse=True)
def ablage(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "texte")
    monkeypatch.setattr(settings, "stimmproben_abstand_s", 0)


async def _alles_vertonen() -> None:
    await probenwache.runde()
    await stimmproben.warten()


async def test_probe_im_leser_einmal_gesprochen_dann_sofort(client, test_db, vertonung):
    f = await familie_anlegen(client, test_db)
    r = await client.post("/api/vorlesen/probe", json={"stimme": SERENA}, headers=f.kopf["ada"])
    assert r.status_code == 200 and r.json()["text"] == proben.text("leser") and r.json()["url"].startswith("/api/vorlesen/probe/ton/")
    assert len(vertonung.koerper(TON)) == 1
    assert (await client.post("/api/vorlesen/probe", json={"stimme": SERENA}, headers=f.kopf["bert"])).json() == r.json()
    assert len(vertonung.koerper(TON)) == 1, "abgelegt, nicht noch einmal gesprochen"
    ton = await client.get(r.json()["url"], headers=f.kopf["ada"])
    assert ton.status_code == 200 and ton.headers["content-type"] == "audio/wav" and "immutable" in ton.headers["cache-control"]
    assert (await client.get(r.json()["url"], headers={**f.kopf["ada"], "if-none-match": ton.headers["etag"]})).status_code == 304
    ab_werk = (await client.post("/api/vorlesen/probe", json={"stimme": ""}, headers=f.kopf["ada"])).json()
    assert ab_werk["url"] and "stimme" not in vertonung.koerper(TON)[-1], "die Stimme ab Werk der Vertonung"
    geraet = (await client.post("/api/vorlesen/probe", json={"stimme": "geraet:Probestimme des Browsers"}, headers=f.kopf["ada"])).json()
    assert geraet == {"text": proben.text("leser"), "url": None}
    assert (await client.get("/api/vorlesen/probe/ton/serena-00000000/leser-0123456789abcdef.wav", headers=f.kopf["ada"])).status_code == 404
    assert (await client.get("/api/vorlesen/probe/ton/..%2Fx/leser-0123456789abcdef.wav", headers=f.kopf["ada"])).status_code in (404, 422)


async def test_werte_des_profils_geben_eine_eigene_probe(client, test_db, vertonung):
    f = await familie_anlegen(client, test_db)
    ohne = (await client.post("/api/vorlesen/probe", json={"stimme": SERENA}, headers=f.kopf["ada"])).json()["url"]
    await client.patch("/api/familie/ich/vorlesen", json={"werte": {"tempo": 1.2}}, headers=f.kopf["ada"])
    mit = (await client.post("/api/vorlesen/probe", json={"stimme": SERENA}, headers=f.kopf["ada"])).json()["url"]
    assert mit != ohne and vertonung.koerper(TON)[-1]["tempo"] == 1.2


async def test_auftrag_vertont_jede_stimme_vorab(client, test_db, vertonung):
    f = await familie_anlegen(client, test_db)
    await client.patch("/api/familie/ich/vorlesen", json={"werte": {"tempo": 1.2}}, headers=f.kopf["ada"])
    await _alles_vertonen()
    stand = await stimmproben.stand()
    liste = await stimmen.liste()
    erwartet = (len(liste.stimmen) + 1) * 2 + len(liste.stimmen)       # je Stimme und ab Werk: ohne und mit Werten; dazu die Ansagen
    assert (stand.stand, stand.gesamt, stand.fertig) == ("fertig", erwartet, erwartet)
    assert len(vertonung.koerper(TON)) == erwartet and not proben.fehlen(await proben.bedarf())
    vorher = len(vertonung.koerper(TON))
    r = await client.post("/api/familie/ansagen/probe", json={"stimme": KLON}, headers=f.kopf["ada"])
    assert r.status_code == 200 and r.json()["url"] and len(vertonung.koerper(TON)) == vorher, "die Probe der Ansagen lag schon bereit"
    await _alles_vertonen()
    assert len(vertonung.koerper(TON)) == vorher, "nichts fehlt, nichts wird gesprochen"


async def test_ohne_vertonung_ruht_er_und_geht_spaeter_weiter(client, test_db, vertonung):
    await familie_anlegen(client, test_db)
    alle = await proben.bedarf()
    vertonung.ablehnen = (503, "Die Vertonung schläft")
    await stimmproben.beginnen(fehlen=[p.model_dump() for p in alle])
    await stimmproben.warten()
    stand = await stimmproben.stand()
    assert stand.stand == "pause" and stand.grund and stand.fertig == 0 and stand.gesamt == len(alle)
    vertonung.ablehnen = None
    await _alles_vertonen()
    assert (await stimmproben.stand()).stand == "fertig" and not proben.fehlen(await proben.bedarf())


async def test_von_hand_angehalten_bleibt_angehalten(client, test_db, vertonung):
    await familie_anlegen(client, test_db)
    await stimmproben.beginnen(fehlen=[p.model_dump() for p in await proben.bedarf()])
    await stimmproben.pause()
    await stimmproben.warten()
    gesprochen = len(vertonung.koerper(TON))
    await _alles_vertonen()
    assert (await stimmproben.stand()).stand == "pause" and len(vertonung.koerper(TON)) == gesprochen


async def test_alte_proben_fallen_weg(client, test_db, vertonung):
    f = await familie_anlegen(client, test_db)
    await client.patch("/api/familie/ich/vorlesen", json={"werte": {"tempo": 1.2}}, headers=f.kopf["ada"])
    await _alles_vertonen()
    alt = proben.pfad(SERENA, "leser", {"tempo": 1.2})
    await client.patch("/api/familie/ich/vorlesen", json={"werte": {"tempo": 0.8}}, headers=f.kopf["ada"])
    await _alles_vertonen()
    assert not alt.exists() and proben.pfad(SERENA, "leser", {"tempo": 0.8}).exists() and proben.pfad(SERENA, "leser").exists()
