"""Nachschlagen und Gespräch: fremdes HTML kommt nie durch, Verweise führen an die Stelle, ohne Anschluss sagt es die App."""

import json

import httpx
import pytest

from backend.app.core.config import settings
from backend.app.services import gespraech, nachschlagen

BUCH = "lexikon_de_2026"


def anschliessen(monkeypatch, modul, einstellung: str, antwort) -> None:
    monkeypatch.setattr(settings, einstellung, "https://dienst.test")
    monkeypatch.setattr(modul.dienst, "_client", httpx.AsyncClient(base_url="https://dienst.test", transport=httpx.MockTransport(antwort)))
    monkeypatch.setattr(nachschlagen, "_buecher", {BUCH: "Lexikon"})


def test_artikel_wird_auf_text_gekuerzt():
    html = ('<div onclick="x()"><p>Das <b>Dateisystem</b> <a href="/lesen/lexikon_de_2026/Datentr%C3%A4ger#Arten" class="wl">Datenträger</a> '
            '<a href="javascript:alert(1)">böse</a><script>alert(1)</script><img src=x onerror=alert(1)></p><h2 id="Arten" style="x">Arten</h2>'
            '<!-- geheim --><table><tr><td>weg</td></tr></table><ul><li>eins</li></ul></div>')
    aus = nachschlagen.zum_lesen(html, BUCH)
    assert aus == ('<p>Das <b>Dateisystem</b> <a data-pfad="Datenträger" href="#">Datenträger</a> böse</p><h2 id="ns-Arten">Arten</h2><ul><li>eins</li></ul>')


@pytest.mark.asyncio
async def test_suche_stellt_den_genauen_titel_voran(client, auth_headers, monkeypatch):
    def antwort(r: httpx.Request) -> httpx.Response:
        if r.url.path.endswith("/vorschlaege"):
            return httpx.Response(200, json=[{"buch": BUCH, "pfad": "Baumhaus", "titel": "Baumhaus", "weiterleitung": "", "kurztext": "", "bild": ""},
                                             {"buch": BUCH, "pfad": "B", "titel": "Baum", "weiterleitung": "Baum_(Pflanze)#Wuchs", "kurztext": "", "bild": ""}])
        return httpx.Response(200, json={"treffer": [{"buch": BUCH, "pfad": "Baum_(Pflanze)", "titel": "Baum (Pflanze)", "ausschnitt": "Ein <em>Baum</em> ist", "anker": "", "bild": "/api/v1/inhalt/medien/lexikon_de_2026/b.jpg"}]})

    anschliessen(monkeypatch, nachschlagen, "nachschlag_url", antwort)
    t = (await client.get("/api/nachschlag/suche", params={"q": "Baum"}, headers=auth_headers)).json()
    assert [x["titel"] for x in t] == ["Baum", "Baumhaus"]
    assert t[0] == {"buch": BUCH, "buchtitel": "Lexikon", "pfad": "Baum_(Pflanze)", "titel": "Baum", "auszug": "Ein Baum ist", "anker": "Wuchs", "bild": ""}


@pytest.mark.asyncio
async def test_artikel_nennt_die_stelle_in_der_anwendung(client, auth_headers, monkeypatch):
    daten = {"buch": BUCH, "pfad": "Baum (Pflanze)", "titel": "Baum", "html": "<p>Text</p>", "einleitung": "", "abschnitte": [{"anker": "Wuchs", "titel": "Wuchs", "ebene": 2}, {"anker": "x", "titel": "x", "ebene": 3}], "bild": ""}
    anschliessen(monkeypatch, nachschlagen, "nachschlag_url", lambda r: httpx.Response(200, json=daten))
    a = (await client.get("/api/nachschlag/artikel", params={"buch": BUCH, "pfad": "Baum (Pflanze)", "q": "Baum", "anker": "Wuchs"}, headers=auth_headers)).json()
    assert a["adresse"] == "https://dienst.test/lesen/lexikon_de_2026/Baum%20%28Pflanze%29?frage=Baum&anker=Wuchs"
    assert a["abschnitte"] == [{"anker": "Wuchs", "titel": "Wuchs"}]


@pytest.mark.asyncio
async def test_bild_nur_als_bild(client, auth_headers, monkeypatch):
    anschliessen(monkeypatch, nachschlagen, "nachschlag_url", lambda r: httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"}))
    assert (await client.get("/api/nachschlag/bild/x/y.jpg", headers=auth_headers)).status_code == 404


def test_wortlaut_nennt_buch_seite_und_stelle():
    s = gespraech.Stelle(buch=1, seite=19, text="Zeile eins\nZeile zwei")
    assert gespraech.wortlaut("Was heißt das?", s, "Grundstein", "HalloWelt42", "https://x/book/1/read?page=19") == (
        'Aus dem Buch "Grundstein" von HalloWelt42, Seite 19 (https://x/book/1/read?page=19):\n> Zeile eins\n> Zeile zwei\n\nWas heißt das?')
    assert gespraech.wortlaut("", gespraech.Stelle(text="abc"), "", "", "").endswith("Erkläre mir diese Stelle.")


@pytest.mark.asyncio
async def test_frage_legt_einen_chat_an_und_folgt_ihm(client, auth_headers, monkeypatch):
    rufe = []

    def antwort(r: httpx.Request) -> httpx.Response:
        rufe.append((r.method, r.url.path, json.loads(r.content or b"{}"), r.headers.get("x-kellerwolke-sitzung")))
        return httpx.Response(201, json={"id": "c1"} if r.url.path.endswith("/chats") else {"id": "z1"})

    anschliessen(monkeypatch, gespraech, "assistent_url", antwort)
    kopf = {**auth_headers, "X-Kellerwolke-Sitzung": "test-sitzung"}
    r = await client.post("/api/gespraech", json={"frage": "Was ist das?", "stelle": {"text": "Ein Satz"}}, headers=kopf)
    assert r.status_code == 201 and r.json() == {"chat": "c1", "zug": "z1", "adresse": "https://dienst.test/chats/c1"}
    r = await client.post("/api/gespraech", json={"frage": "Und weiter?", "chat": "c1"}, headers=kopf)
    assert [(m, p) for m, p, *_ in rufe] == [("POST", "/api/v1/chats"), ("POST", "/api/v1/chats/c1/zuege"), ("POST", "/api/v1/chats/c1/zuege")]
    assert rufe[-1][2]["text"] == "Und weiter?" and {x[3] for x in rufe} == {"test-sitzung"}


@pytest.mark.asyncio
async def test_antwort_als_strom(client, auth_headers, monkeypatch):
    zug = {"id": "z1", "antwort": "Hallo Welt", "zustand": "fertig", "belege": [{"nummer": "1", "titel": "T", "seite": "3", "gedruckt": "", "verweis": "https://q"}]}
    strom = ("event: verbunden\ndata: {}\n\nevent: text\ndata: " + json.dumps({"zug": "z1", "text": "Hallo", "ab": 0}) +
             "\n\nevent: text\ndata: " + json.dumps({"zug": "anderer", "text": "nein", "ab": 0}) + "\n\nevent: zug\ndata: " + json.dumps({"zug": zug}) + "\n\n")

    def antwort(r: httpx.Request) -> httpx.Response:
        if r.url.path.endswith("/ereignisse"):
            return httpx.Response(200, text=strom)
        return httpx.Response(200, json={"zuege": [{**zug, "antwort": "", "zustand": "laeuft", "belege": []}]})

    anschliessen(monkeypatch, gespraech, "assistent_url", antwort)
    zeilen = [json.loads(z) for z in (await client.get("/api/gespraech/c1/z1", headers=auth_headers)).text.splitlines()]
    assert [(z["art"], z.get("text") or z.get("antwort"), z.get("zustand")) for z in zeilen] == [("stand", "", "laeuft"), ("text", "Hallo", None), ("stand", "Hallo Welt", "fertig")]
    assert zeilen[-1]["belege"] == [{"nummer": "1", "titel": "T", "seite": "3", "verweis": "https://q"}]


@pytest.mark.asyncio
async def test_ohne_anschluss_sagt_es_die_app(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "nachschlag_url", "")
    monkeypatch.setattr(settings, "assistent_url", "")
    monkeypatch.setattr(nachschlagen.dienst, "_client", None)
    monkeypatch.setattr(gespraech.dienst, "_client", None)
    monkeypatch.setattr(nachschlagen, "_buecher", {})
    assert (await client.get("/api/nachschlag/suche", params={"q": "x"}, headers=auth_headers)).status_code == 503
    assert "nicht angeschlossen" in (await client.post("/api/gespraech", json={"frage": "x"}, headers=auth_headers)).json()["detail"]
