"""Hinweise sprechen und Tasten ansagen (BF-78): Vorgabe je Stufe, von den Eltern änderbar, und der Weg für kurze Ansagen mit
Zwischenspeicher, gegen eine Attrappe der Leitstelle ohne Netz. Alles erfunden."""

from __future__ import annotations

import json

from backend.app.core.config import settings
from backend.app.services import ansage
from tests.api.familie_hilfen import familie_anlegen
from tests.api.test_ausfuehren import leitstelle  # noqa: F401 - Attrappe der Leitstelle
from tests.api.test_vorlesen_api import WAV, sprechdienst

WEG = "/api/vorlesen/ansage"


def _gesprochen(attrappe) -> list[dict]:
    return [json.loads(a.content) for a in attrappe.anfragen if a.url.path.endswith("/v1/audio/speech")]


async def test_vorgabe_je_stufe_und_von_den_eltern_aenderbar(client, test_db):
    f = await familie_anlegen(client, test_db)
    for kind, an in (("clara", True), ("dora", False), ("emil", False)):
        hilfen = (await client.get("/api/familie/ich", headers=f.kopf[kind])).json()["lesehilfen"]
        assert (hilfen["hinweise_sprechen"], hilfen["tasten_ansagen"]) == (an, an), kind
    stufen = {s["schluessel"]: s["vorgaben"]["lesehilfen"]["tasten_ansagen"] for s in (await client.get("/api/familie/stufen")).json()["stufen"]}
    assert stufen == {"vorlesen": True, "erstes_lesen": True, "lesen_lernen": True, "schule": False, "jugend": False}
    wahl = {"mitlesen": True, "tempo": 1.0, "silben": False, "lesezeile": False, "schrift": "mittel", "hinweise_sprechen": False,
            "tasten_ansagen": True, "stimme": "katalog:Kerstin"}
    r = await client.patch(f"/api/familie/profile/{f.ids['clara']}", json={"einstellungen": {"lesehilfen": wahl}}, headers=f.kopf["ada"])
    assert r.status_code == 200 and r.json()["einstellungen"]["lesehilfen"]["hinweise_sprechen"] is False
    hilfen = (await client.get("/api/familie/ich", headers=f.kopf["clara"])).json()["lesehilfen"]
    assert (hilfen["hinweise_sprechen"], hilfen["tasten_ansagen"], hilfen["stimme"]) == (False, True, "katalog:Kerstin")


async def test_ohne_sprechdienst_503_mit_grund(client, test_db, monkeypatch):
    monkeypatch.setattr(settings, "leitstelle_adresse", "")
    r = await client.post(WEG, json={"text": "Weiter."})
    assert r.status_code == 503 and "Sprechdienst" in r.json()["detail"]


async def test_ansage_gemerkt_und_sofort_wieder_da(client, test_db, leitstelle, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "zwischen_dir", tmp_path / "zwischen")
    leitstelle.antwort = sprechdienst
    f = await familie_anlegen(client, test_db)
    r = await client.post(WEG, json={"text": "Weiter."}, headers=f.kopf["clara"])           # Kinder dürfen
    assert r.status_code == 200 and r.content == WAV and r.headers["content-type"] == "audio/wav" and r.headers["x-ansage"] == "neu"
    r = await client.post(WEG, json={"text": "Weiter."}, headers=f.kopf["dora"])
    assert r.content == WAV and r.headers["x-ansage"] == "gemerkt"
    assert len(_gesprochen(leitstelle)) == 1
    assert len(list((tmp_path / "zwischen" / ansage.ORDNER).glob("*.wav"))) == 1
    await client.post(WEG, json={"text": "Weiter.", "stimme": "katalog:Thorsten"}, headers=f.kopf["dora"])
    assert _gesprochen(leitstelle)[-1] == {"input": "Weiter.", "response_format": "wav", "voice": "Thorsten"}     # andere Stimme, neu


async def test_die_stimme_des_profils_geht_vor(client, test_db, leitstelle, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "zwischen_dir", tmp_path / "zwischen")
    leitstelle.antwort = sprechdienst
    f = await familie_anlegen(client, test_db)
    await client.patch(f"/api/familie/profile/{f.ids['clara']}", json={"einstellungen": {"lesehilfen": {"stimme": "katalog:Kerstin"}}},
                       headers=f.kopf["ada"])
    await client.post(WEG, json={"text": "Zurück zum Regal.", "stimme": "katalog:Thorsten"}, headers=f.kopf["clara"])
    assert _gesprochen(leitstelle)[-1]["voice"] == "Kerstin"


async def test_nur_ein_kurzer_satz(client, test_db):
    assert (await client.post(WEG, json={"text": "Erster Satz. Zweiter Satz."})).status_code == 422
    assert (await client.post(WEG, json={"text": "x" * 301})).status_code == 422
    assert (await client.post(WEG, json={"text": " - "})).status_code == 422


async def test_der_speicher_begrenzt_sich_selbst(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "zwischen_dir", tmp_path)
    monkeypatch.setattr(settings, "ansagen_mb", 1)
    gesprochen = []

    async def satz(text, stimme):
        gesprochen.append(text)
        return b"w" * 400_000

    monkeypatch.setattr(ansage.vorlesen, "satz", satz)
    for text in ("Eins.", "Zwei.", "Drei."):
        await ansage.sprechen(text, "")
    assert (await ansage.sprechen("Eins.", "")).gemerkt is False                       # die älteste ging
    assert (await ansage.sprechen("Drei.", "")).gemerkt is True
    assert sum(d.stat().st_size for d in (tmp_path / ansage.ORDNER).glob("*.wav")) <= 1024 * 1024
