"""Vorlesen über den Sprechdienst: Stimmen, Teilen langer Texte, Strom und klare Meldungen."""

import json

import httpx
import pytest

from backend.app.core.config import settings
from backend.app.services import vorlesen


def dienst(monkeypatch, antwort) -> None:
    monkeypatch.setattr(settings, "vorlesen_url", "https://sprechen.test")
    monkeypatch.setattr(vorlesen, "_client", httpx.AsyncClient(base_url="https://sprechen.test", transport=httpx.MockTransport(antwort)))


def test_teile_schneiden_an_saetzen_und_behalten_allen_text():
    text = " ".join(f"Satz Nummer {n} mit etwas Inhalt." for n in range(60))
    stuecke = vorlesen.teile(text, 200)
    assert all(len(s) <= 200 for s in stuecke) and all(s.endswith(".") for s in stuecke)
    assert " ".join(stuecke) == text
    assert "".join(vorlesen.teile("x" * 950, 200)) == "x" * 950


@pytest.mark.asyncio
async def test_ohne_sprechdienst_sagt_es_die_app(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "vorlesen_url", "")
    assert (await client.get("/api/vorlesen/stimmen", headers=auth_headers)).json() == {"da": False, "stimmen": [], "hinweis": ""}
    r = await client.post("/api/vorlesen", headers=auth_headers, json={"text": "Hallo"})
    assert r.status_code == 503 and "Sprechdienst" in r.json()["detail"]


@pytest.mark.asyncio
async def test_stimmen_ohne_freigabe_der_eigenen(client, auth_headers, monkeypatch):
    def antwort(r: httpx.Request) -> httpx.Response:
        if r.url.params["bereich"] == "privat":
            return httpx.Response(403, json={"detail": "nein"})
        return httpx.Response(200, json=[{"id": f"katalog:{r.url.params['bereich']}", "name": "Stimme"}])

    dienst(monkeypatch, antwort)
    s = (await client.get("/api/vorlesen/stimmen", headers=auth_headers)).json()
    assert s["da"] and [x["gruppe"] for x in s["stimmen"]] == ["weitere", "eingebaut"] and "Eigene Stimmen" in s["hinweis"]


@pytest.mark.asyncio
async def test_strom_zaehlt_saetze_durch_und_schickt_die_stimme(client, auth_headers, monkeypatch):
    gesehen = []

    def antwort(r: httpx.Request) -> httpx.Response:
        gesehen.append(json.loads(r.content))
        return httpx.Response(200, text='{"art":"satz","nr":0,"text":"a","ton":"QQ=="}\n{"art":"ende"}\n')

    dienst(monkeypatch, antwort)
    monkeypatch.setattr(vorlesen, "TEIL", 20)
    monkeypatch.setattr(vorlesen.teile, "__defaults__", (20,))
    r = await client.post("/api/vorlesen", headers=auth_headers, json={"text": "Erster Satz hier. Zweiter Satz dort.", "stimme": "katalog:anna"})
    zeilen = [json.loads(z) for z in r.text.splitlines()]
    assert [z.get("nr") for z in zeilen] == [0, 1, None] and zeilen[-1]["art"] == "ende"
    assert gesehen[0]["stimme"] == {"art": "katalog", "name": "anna"}


@pytest.mark.asyncio
async def test_fehler_vor_dem_ersten_satz_ist_eine_antwort(client, auth_headers, monkeypatch):
    dienst(monkeypatch, lambda r: httpx.Response(422, json={"detail": "Diese Stimme gibt es nicht"}))
    r = await client.post("/api/vorlesen", headers=auth_headers, json={"text": "Hallo", "stimme": "x"})
    assert r.status_code == 400 and r.json()["detail"] == "Diese Stimme gibt es nicht"
