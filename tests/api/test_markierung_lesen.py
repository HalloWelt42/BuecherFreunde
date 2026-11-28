"""Markierungen über ein Rechteck gescannter Seiten (BF-123) in einer laufenden Probeinstallation: ein Scan wird klassisch erkannt
(Attrappe des Programms), dann zieht jemand ein Rechteck. Gelesen wird über die nachgebaute Leitstelle mit einem Textmodell; die
Lesung beginnt vor der Markierung (Menü), hängt danach an ihr, scheitert mit Notbehelf und lässt sich erneut lesen. Alle Bücher,
Seiten und Texte sind erfunden."""

from __future__ import annotations

import pytest

from backend.app.core.config import settings
from backend.app.markierungen.lesen import markierungslesen
from backend.app.markierungen.stelle import bereich_aus, stelle_von
from backend.app.services.ki import Ki, KiFehler, ki
from backend.app.texterkennung import werkzeug
from backend.app.texterkennung.ausschnitt import OHNE_TEXT, Bereich
from backend.app.texterkennung.auftrag import texterkennung
from tests.api.einrichtung_hilfen import laufend, orte  # noqa: F401 - Fixtures
from tests.api.test_nachbesserung import KLASSISCH, _erkannt
from tests.texterkennung_hilfen import attrappe_anlegen

pytestmark = pytest.mark.asyncio
# Die zweite Zeile der Probe (Grundlinie bei 140 Punkten, Seite 595 x 842): ohne die Überschrift darüber
ZEILE_2 = stelle_von(1, Bereich(x0=0.1, y0=0.148, x1=0.95, y1=0.178))
LEER = stelle_von(1, Bereich(x0=0.1, y0=0.8, x1=0.9, y1=0.9))
GELESEN = "| Nummer | Titel | Tage |\n|---|---|---|\n| 1 | Das Haus am Kanal | 14 |\n| 2 | Wolken über dem Deich | 21 |"


@pytest.fixture(autouse=True)
async def sauber(monkeypatch):
    monkeypatch.setattr(settings, "texterkennung_abstand_s", 0)
    monkeypatch.setattr(settings, "texterkennung_vorrang_seiten", 1)
    werkzeug.vergessen()
    yield
    await texterkennung.stoppen()
    await markierungslesen.stoppen()
    werkzeug.vergessen()


@pytest.fixture
def programm(orte, monkeypatch):  # noqa: F811
    a = attrappe_anlegen(orte / "programm", monkeypatch)
    a.liefert(KLASSISCH)
    return a


@pytest.fixture
def textmodell(monkeypatch):
    """Die Leitstelle mit einem Textmodell, nachgebaut: je Frage die Antwort aus `antworten`, eine Ausnahme scheitert."""
    from backend.app.codestellen.dienst import codestellen

    monkeypatch.setattr(codestellen, "vormerken", lambda buch, vorrang=False: None)
    monkeypatch.setattr(Ki, "bereit", property(lambda self: True))
    eingaben: list[str] = []
    antworten: list[str | Exception] = []

    async def antwort(anweisung, eingabe, *, titel, modell, **art):
        eingaben.append(eingabe)
        a = antworten.pop(0) if antworten else GELESEN
        if isinstance(a, Exception):
            raise a
        return a

    async def faehigkeiten(modell):
        return ["text"]

    monkeypatch.setattr(ki, "antwort", antwort)
    monkeypatch.setattr(ki, "faehigkeiten", faehigkeiten)
    return eingaben, antworten


async def _markierungen(client, buch: int) -> list[dict]:
    return (await client.get(f"/api/books/{buch}/highlights")).json()


async def test_stelle_hin_und_zurueck():
    seite, b = bereich_aus("page:12:bereich:0.1000,0.2000,0.5000,0.3500")
    assert (seite, b) == (12, Bereich(x0=0.1, y0=0.2, x1=0.5, y1=0.35))
    assert stelle_von(seite, b) == "page:12:bereich:0.1000,0.2000,0.5000,0.3500"
    assert bereich_aus("page:12") is None and bereich_aus("page:3:bereich:0.5,0.2,0.4,0.3") is None   # verkehrt herum
    assert bereich_aus("page:0:bereich:0.1,0.1,0.2,0.2") is None and bereich_aus("page:2:bereich:1.5,0.1,1.7,0.2") is None


async def test_menue_liest_dann_markieren(laufend, test_db, client, programm, textmodell):  # noqa: F811
    eingaben, _ = textmodell
    buch = await _erkannt(test_db, "bereich00a")
    r = await client.post(f"/api/books/{buch}/lesen", json={"stelle": ZEILE_2})
    assert r.status_code == 200, r.text
    lesung = r.json()["id"]
    await markierungslesen.warten()
    stand = (await client.get(f"/api/lesen/{lesung}")).json()
    assert stand["stand"] == "fertig" and "2 Wolken über dem Deich 21" in stand["text"]   # schlichter Text, Zeile für Zeile
    assert "Nummer" in eingaben[0] and "Ausleihe" not in eingaben[0]      # nur die Wörter im Rechteck gehen an das Modell

    r = await client.post(f"/api/books/{buch}/highlights", json={"cfi_range": ZEILE_2, "color": "#FFEE58", "lesung": lesung})
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["text_snippet"] == stand["text"] and m["lesen"] == {"stand": "fertig", "grund": ""}
    assert len(eingaben) == 1                                             # die Lesung aus dem Menü gilt, kein zweites Mal
    [liste] = await _markierungen(client, buch)
    assert liste["lesen"] == {"stand": "fertig", "grund": ""} and liste["text_snippet"] == stand["text"]


async def test_scheitert_mit_notbehelf_und_erneut(laufend, test_db, client, programm, textmodell):  # noqa: F811
    _, antworten = textmodell
    buch = await _erkannt(test_db, "bereich00b")
    antworten.append(KiFehler("Die Leitstelle antwortet nicht", "weg"))
    m = (await client.post(f"/api/books/{buch}/highlights", json={"cfi_range": ZEILE_2, "color": "#81C784"})).json()
    assert m["lesen"]["stand"] == "offen"                                 # Markierstift: ohne Menü liest die Markierung selbst
    await markierungslesen.warten()
    [liste] = await _markierungen(client, buch)
    assert liste["lesen"] == {"stand": "fehler", "grund": "Die Leitstelle antwortet nicht"}
    assert "Wolken uber dem" in liste["text_snippet"]                     # Notbehelf: der Text der klassischen Erkennung

    r = await client.post(f"/api/highlights/{m['id']}/lesen")
    assert r.status_code == 200 and r.json()["stand"] == "offen"
    await markierungslesen.warten()
    [liste] = await _markierungen(client, buch)
    assert liste["lesen"]["stand"] == "fertig" and "Wolken über dem Deich" in liste["text_snippet"]


async def test_ohne_text_und_falsche_stelle(laufend, test_db, client, programm, textmodell):  # noqa: F811
    eingaben, _ = textmodell
    buch = await _erkannt(test_db, "bereich00c")
    lesung = (await client.post(f"/api/books/{buch}/lesen", json={"stelle": LEER})).json()["id"]
    await markierungslesen.warten()
    assert (await client.get(f"/api/lesen/{lesung}")).json() == {"id": lesung, "stand": "fertig", "text": "", "grund": OHNE_TEXT}
    assert eingaben == []                                                 # nichts im Rechteck: kein Modell gefragt
    r = await client.post(f"/api/books/{buch}/lesen", json={"stelle": "page:1"})
    assert r.status_code == 422
    r = await client.post(f"/api/highlights/{(await client.post(f'/api/books/{buch}/highlights', json={'cfi_range': 'page:1', 'text_snippet': 'Wort'})).json()['id']}/lesen")
    assert r.status_code == 422                                           # eine Markierung im Text ist kein Rechteck
    assert (await client.get("/api/lesen/999999")).status_code == 404


async def test_suche_findet_den_text_der_markierungen(laufend, test_db, client, programm, textmodell):  # noqa: F811
    buch = await _erkannt(test_db, "bereich00d")
    await client.post(f"/api/books/{buch}/highlights", json={"cfi_range": ZEILE_2, "color": "#FFEE58"})
    await markierungslesen.warten()
    a = (await client.get("/api/search", params={"q": "Deich"})).json()
    [t] = a["markierungen"]
    assert (t["buch_id"], t["stelle"], t["seite"]) == (buch, ZEILE_2, 1)
    assert "<mark>Deich</mark>" in t["auszug"]
    assert (await client.get("/api/search", params={"q": "Deich Leuchtturm"})).json()["markierungen"] == []   # jedes Wort muss vorkommen
    assert (await client.get("/api/search", params={"q": "Deich", "offset": 20})).json()["markierungen"] == []  # nur auf der ersten Seite
