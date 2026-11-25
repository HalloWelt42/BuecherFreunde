"""Nachschlagen ohne Nachschlag: das öffentliche Lexikon im Netz über den gemeinsamen Abruf. Die Antworten sind im Aufbau echt,
die Texte eigene Sätze."""

import pytest

from backend.app.core.config import settings
from backend.app.services import nachschlagen
from tests.quellen_netz import antwort, feld

WIKI = "de.wikipedia.org"
BILDER = "thumb.wikimedia.org"

SUCHE = {"batchcomplete": True, "query": {
    "prefixsearch": [{"ns": 0, "title": "Baumhaus", "pageid": 1}, {"ns": 0, "title": "Baum", "pageid": 2}],
    "search": [{"ns": 0, "title": "Baum", "pageid": 2, "snippet": "Ein <span class=\"searchmatch\">Baum</span> ist eine Pflanze"},
               {"ns": 0, "title": "Wald", "pageid": 3, "snippet": "Viele <span class=\"searchmatch\">Bäume</span> zusammen"}]}}

ARTIKEL_HTML = (
    '<div class="mw-content-ltr mw-parser-output" lang="de" dir="ltr">'
    '<div class="hatnote">Hinweis zu gleichnamigen Begriffen.</div>'
    '<table class="infobox"><tr><td><span typeof="mw:File"><img src="//thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Baum_(Eiche).jpg/250px-Baum_(Eiche).jpg?utm_source=de.wikipedia.org&amp;utm_content=thumbnail"'
    ' width="250" height="180" class="mw-file-element"></span></td></tr></table>'
    '<p>Ein <b>Baum</b> wächst aus einem <a href="/wiki/Samen" title="Samen">Samen</a>'
    '<sup class="reference"><a href="#cite_note-1">[1]</a></sup> und braucht <a href="/wiki/Datei:Licht.png">Licht</a>.</p>'
    '<div class="mw-heading mw-heading2"><h2 id="Aufbau">Aufbau</h2><span class="mw-editsection">bearbeiten</span></div>'
    '<p>Stamm, Äste und <a href="/wiki/Laubblatt#Form">Blätter</a>. <a href="https://example.org">fremd</a></p>'
    '<div class="mw-heading mw-heading2"><h2 id="Literatur">Literatur</h2></div><ul><li>Ein Buch über Bäume</li></ul>'
    '<div class="mw-heading mw-heading2"><h2 id="Einzelnachweise">Einzelnachweise</h2></div><ol class="references"><li>Beleg</li></ol>'
    '<div class="navbox">Navigation</div></div>')
ARTIKEL = {"parse": {"title": "Baum", "pageid": 2, "text": ARTIKEL_HTML,
                     "sections": [{"toclevel": 1, "level": "2", "line": "Aufbau", "anchor": "Aufbau"},
                                  {"toclevel": 2, "level": "3", "line": "Wurzel", "anchor": "Wurzel"},
                                  {"toclevel": 1, "level": "2", "line": "Literatur", "anchor": "Literatur"}]}}


@pytest.fixture
def ohne_nachschlag(monkeypatch):
    monkeypatch.setattr(settings, "nachschlag_url", "")
    monkeypatch.setattr(settings, "wikipedia_enabled", True)


@pytest.mark.asyncio
async def test_titel_und_text_in_einer_anfrage(client, auth_headers, netz, ohne_nachschlag):
    netz.setze(WIKI, antwort(SUCHE))
    schnell = (await client.get("/api/nachschlag/suche", params={"q": "Baum", "nur_titel": True}, headers=auth_headers)).json()
    alle = (await client.get("/api/nachschlag/suche", params={"q": "Baum"}, headers=auth_headers)).json()
    assert schnell == alle and [t["titel"] for t in alle] == ["Baum", "Baumhaus", "Wald"]
    assert alle[0] == {"buch": "wikipedia_de", "buchtitel": "Wikipedia (Deutsch)", "pfad": "Baum", "titel": "Baum", "auszug": "Ein Baum ist eine Pflanze", "anker": "", "bild": ""}
    assert netz.zahl(WIKI) == 1                       # der zweite Blick kommt aus dem Vorrat
    assert feld(netz.anfragen[0], "list") == "prefixsearch|search" and feld(netz.anfragen[0], "srsearch") == "Baum"


@pytest.mark.asyncio
async def test_artikel_ohne_anhang_und_fremdes(client, auth_headers, netz, ohne_nachschlag):
    netz.setze(WIKI, antwort(ARTIKEL))
    a = (await client.get("/api/nachschlag/artikel", params={"buch": "wikipedia_de", "pfad": "Baum", "q": "Baum", "anker": "Aufbau"}, headers=auth_headers)).json()
    assert a["adresse"] == "https://de.wikipedia.org/wiki/Baum#Aufbau"
    assert a["abschnitte"] == [{"anker": "Aufbau", "titel": "Aufbau"}]
    assert a["bild"] == "/api/nachschlag/bild/wikipedia_de/thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Baum_(Eiche).jpg/250px-Baum_(Eiche).jpg"
    html = a["html"]
    assert '<a data-pfad="Samen" href="#">Samen</a>' in html and '<a data-pfad="Laubblatt" href="#">Blätter</a>' in html
    assert '<h2 id="ns-Aufbau">Aufbau</h2>' in html and "Hinweis zu gleichnamigen" in html
    for weg in ("[1]", "bearbeiten", "Literatur", "Ein Buch über Bäume", "Beleg", "Navigation", "example.org", "Datei:", "<img", "<table"):
        assert weg not in html, weg
    assert "Licht" in html and "fremd" in html                 # der Text bleibt, nur der Verweis fällt weg


@pytest.mark.asyncio
async def test_fehlender_artikel_ist_nichts_gefunden(client, auth_headers, netz, ohne_nachschlag):
    netz.setze(WIKI, antwort({"error": {"code": "missingtitle", "info": "The page you specified doesn't exist."}}))
    r = await client.get("/api/nachschlag/artikel", params={"buch": "wikipedia_de", "pfad": "Gibtsnicht"}, headers=auth_headers)
    assert r.status_code == 404 and r.json()["detail"] == "Diesen Artikel gibt es im Lexikon nicht"


@pytest.mark.asyncio
async def test_ueberlast_wird_zur_meldung(client, auth_headers, netz, ohne_nachschlag):
    netz.setze(WIKI, antwort(b"", 503, retry_after="120"))
    r = await client.get("/api/nachschlag/suche", params={"q": "Baum"}, headers=auth_headers)
    assert r.status_code == 503 and r.json()["detail"]


@pytest.mark.asyncio
async def test_bild_nur_vom_bildrechner_und_nur_raster(client, auth_headers, netz, ohne_nachschlag):
    netz.setze(BILDER, antwort(b"\xff\xd8\xff\xe0" + b"0" * 2000), antwort(b"<svg onload=alert(1)>"))
    weg = "/api/nachschlag/bild/wikipedia_de/thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Baum_(Eiche).jpg/250px-Baum_(Eiche).jpg"
    r = await client.get(weg, headers=auth_headers)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert netz.anfragen[0].adresse == "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Baum_(Eiche).jpg/250px-Baum_(Eiche).jpg"
    assert (await client.get(weg.replace("250px", "300px"), headers=auth_headers)).status_code == 404
    assert (await client.get("/api/nachschlag/bild/wikipedia_de/..%2F..%2Fetc/passwd", headers=auth_headers)).status_code == 404
    assert (await client.get("/api/nachschlag/bild/anderes/thumb.wikimedia.org/wikipedia/x.jpg", headers=auth_headers)).status_code == 404
    assert (await client.get("/api/nachschlag/bild/wikipedia_de/example.org/wikipedia/x.jpg", headers=auth_headers)).status_code == 404


@pytest.mark.asyncio
async def test_hausdienst_geht_vor_und_abgeschaltet_fehlt_es(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "nachschlag_url", "https://nachschlag.test")
    assert nachschlagen.lexikon().art == "nachschlag"
    monkeypatch.setattr(settings, "nachschlag_url", "")
    assert nachschlagen.lexikon().art == "netz"
    monkeypatch.setattr(settings, "wikipedia_enabled", False)
    assert nachschlagen.lexikon() is None
    o = (await client.get("/api/config/oberflaeche", headers=auth_headers)).json()["anschluesse"]
    assert (o["nachschlag"], o["nachschlag_art"]) == ("", "")
