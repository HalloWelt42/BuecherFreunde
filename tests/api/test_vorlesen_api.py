"""Vorlesen über den Sprechdienst der Leitstelle (BF-14): Stimmen aus dem Katalog, Sätze, Strom und klare Meldungen; gegen
eine Attrappe der Leitstelle, ohne Netz."""

import base64
import json
from urllib.parse import unquote

import httpx

from backend.app.core.config import settings
from backend.app.services import vorlesen
from tests.api.test_ausfuehren import LEITSTELLE, leitstelle  # noqa: F401 - Attrappe der Leitstelle

DIENST = f"/v1/dienste/{settings.sprechdienst}"
WAV = b"RIFF0000WAVEfmt "


def sprechdienst(r: httpx.Request) -> httpx.Response:
    if r.url.path == f"{DIENST}/tts/voices":
        return httpx.Response(200, json={"speakers": ["Thorsten", "Kerstin"]})
    if r.url.path == f"{DIENST}/v1/audio/speech":
        return httpx.Response(200, content=WAV, headers={"content-type": "audio/wav"})
    return httpx.Response(404, json={"detail": "unbekannt"})


def test_saetze_wie_im_text_und_lange_geteilt():
    text = "Erster Satz hier. Zweiter Satz dort!\n\n- \nDritter: ein " + "langes Wort, " * 60 + "Ende."
    teile = vorlesen.saetze(text, 120)
    assert teile[:2] == ["Erster Satz hier.", "Zweiter Satz dort!"] and all(len(t) <= 120 for t in teile)
    assert all(t in text for t in teile) and "-" not in teile                   # jeder Satz steht so im Text, Striche fallen weg


async def test_ohne_leitstelle_die_stimmen_des_geraets(client, monkeypatch):
    monkeypatch.setattr(settings, "leitstelle_adresse", "")
    assert (await client.get("/api/vorlesen/stimmen")).json() == {"da": False, "stimmen": [], "hinweis": ""}
    r = await client.post("/api/vorlesen", json={"text": "Hallo"})
    assert r.status_code == 503 and "Sprechdienst" in r.json()["detail"]
    assert (await client.get("/api/config/oberflaeche")).json()["anschluesse"]["vorlesen"] is False


async def test_stimmen_aus_dem_katalog(client, leitstelle, monkeypatch):  # noqa: F811
    monkeypatch.setattr(vorlesen, "_katalog", None)
    leitstelle.antwort = sprechdienst
    s = (await client.get("/api/vorlesen/stimmen")).json()
    assert s == {"da": True, "hinweis": "", "stimmen": [{"id": "katalog:Kerstin", "name": "Kerstin", "gruppe": "eingebaut"},
                                                        {"id": "katalog:Thorsten", "name": "Thorsten", "gruppe": "eingebaut"}]}
    assert (await client.get("/api/config/oberflaeche")).json()["anschluesse"]["vorlesen"] is True


async def test_strom_satz_fuer_satz_ueber_die_leitstelle(client, leitstelle):  # noqa: F811
    leitstelle.antwort = sprechdienst
    r = await client.post("/api/vorlesen", json={"text": "Erster Satz hier. Zweiter Satz dort.", "stimme": "katalog:Kerstin"})
    zeilen = [json.loads(z) for z in r.text.splitlines()]
    assert [(z["art"], z.get("nr"), z.get("text")) for z in zeilen] == [("satz", 0, "Erster Satz hier."), ("satz", 1, "Zweiter Satz dort."),
                                                                         ("ende", None, None)]
    assert base64.b64decode(zeilen[0]["ton"]) == WAV
    sprechen = [a for a in leitstelle.anfragen if a.url.path.endswith("/v1/audio/speech")]
    assert [json.loads(a.content) for a in sprechen] == [{"input": "Erster Satz hier.", "response_format": "wav", "voice": "Kerstin"},
                                                        {"input": "Zweiter Satz dort.", "response_format": "wav", "voice": "Kerstin"}]
    kopf = sprechen[0].headers
    assert sprechen[0].url == httpx.URL(f"{LEITSTELLE}{DIENST}/v1/audio/speech") and kopf["Authorization"] == "Bearer ls_app_test"
    assert unquote(kopf["X-Leitstelle-Titel"]) == "BücherFreunde: Vorlesen" and kopf["X-Leitstelle-Arbeit"].startswith("bf-vorlesen-")
    assert sprechen[1].headers["X-Leitstelle-Arbeit"] == kopf["X-Leitstelle-Arbeit"]  # eine Vorlesung ist eine Arbeit


async def test_vorgabe_des_dienstes_ohne_stimme(client, leitstelle):  # noqa: F811
    leitstelle.antwort = sprechdienst
    await client.post("/api/vorlesen", json={"text": "Nur ein Satz."})
    assert "voice" not in json.loads(leitstelle.anfragen[-1].content)


async def test_fehler_vor_dem_ersten_satz_ist_eine_antwort(client, leitstelle):  # noqa: F811
    leitstelle.antwort = lambda r: httpx.Response(403, json={"error": {"code": "faehigkeit_nicht_erlaubt", "message": "Fähigkeit stimme fehlt"}})
    r = await client.post("/api/vorlesen", json={"text": "Hallo."})
    assert r.status_code == 403 and "nicht frei" in r.json()["detail"] and "stimme fehlt" in r.json()["detail"]
    r = await client.post("/api/vorlesen", json={"text": "Hallo.", "stimme": "a1b2c3"})               # frühere eigene Stimme
    assert r.status_code == 400 and "aus der Liste" in r.json()["detail"]


async def test_fehler_nach_dem_ersten_satz_ist_eine_zeile(client, leitstelle):  # noqa: F811
    gesprochen = []

    def antwort(r: httpx.Request) -> httpx.Response:
        gesprochen.append(r)
        if len(gesprochen) == 1:
            return sprechdienst(r)
        return httpx.Response(503, json={"error": {"code": "halt", "message": "Hauptregler auf Halt"}})

    leitstelle.antwort = antwort
    r = await client.post("/api/vorlesen", json={"text": "Eins. Zwei. Drei."})
    zeilen = [json.loads(z) for z in r.text.splitlines()]
    assert zeilen[0]["art"] == "satz" and zeilen[-1] == {"art": "fehler", "meldung": "Vorlesen gerade nicht möglich: Hauptregler auf Halt"}
