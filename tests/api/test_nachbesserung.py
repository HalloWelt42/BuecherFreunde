"""Der Auftrag "Texte nachbessern" (BF-118) in einer laufenden Probeinstallation: ein Scan wird klassisch erkannt (Attrappe des
Programms), dann bittet der Leser für eine Seite um die Nachbesserung; das Bildmodell der Leitstelle ist nachgebaut. Danach gilt
die nachgebesserte Fassung (Tabelle als Baustein, Volltext neu), je Seite lässt sich die klassische wieder wählen. Alle Bücher,
Seiten und Texte sind erfunden."""

from __future__ import annotations

import pytest

from backend.app.core.config import settings
from backend.app.services.ki import Ki, KiFehler, ki
from backend.app.services.storage import load_fulltext
from backend.app.texterkennung import werkzeug
from backend.app.texterkennung.auftrag import erkennungswache, texterkennung
from backend.app.texterkennung.nachbesserung import nachbesserung
from tests.api.einrichtung_hilfen import laufend, orte  # noqa: F401 - Fixtures
from tests.api.test_texterkennung import _buch
from tests.texterkennung_hilfen import Probezeile, attrappe_anlegen, scan_pdf

pytestmark = pytest.mark.asyncio
KLASSISCH = [Probezeile("Ausleihe im Uberblick", 72, 110, 18, block=1),
             Probezeile("| Nummer | Titel | Tage | 1 | Das Haus am | Kanal 14 | 2 | Wolken uber dem | 21", 72, 140, block=2)]
NACHGEBESSERT = """## Ausleihe im Überblick

| Nummer | Titel | Tage |
|---|---|---|
| 1 | Das Haus am Kanal | 14 |
| 2 | Wolken über dem Deich | 21 |
"""


@pytest.fixture(autouse=True)
async def sauber(monkeypatch):
    monkeypatch.setattr(settings, "texterkennung_abstand_s", 0)
    monkeypatch.setattr(settings, "texterkennung_vorrang_seiten", 1)
    monkeypatch.setattr(settings, "texterkennung_ki_seiten", 2)
    werkzeug.vergessen()
    yield
    await texterkennung.stoppen()
    await nachbesserung.stoppen()
    werkzeug.vergessen()


@pytest.fixture
def programm(orte, monkeypatch):  # noqa: F811
    a = attrappe_anlegen(orte / "programm", monkeypatch)
    a.liefert(KLASSISCH)
    return a


@pytest.fixture
def bildmodell(monkeypatch):
    """Die Leitstelle mit einem Bildmodell, nachgebaut: je Seite die Antwort aus `antworten`, eine Ausnahme scheitert."""
    from backend.app.codestellen.dienst import codestellen

    monkeypatch.setattr(codestellen, "vormerken", lambda buch, vorrang=False: None)
    monkeypatch.setattr(Ki, "bereit", property(lambda self: True))
    gefragt: list[str] = []
    antworten: list[str | Exception] = []

    async def bildantwort(anweisung, bild, *, modell, titel, **art):
        gefragt.append(modell)
        a = antworten.pop(0) if antworten else NACHGEBESSERT
        if isinstance(a, Exception):
            raise a
        return a, "Qwen3.8 27B"

    async def faehigkeiten(modell):
        return ["bild_beschreiben", "text"]

    monkeypatch.setattr(ki, "bildantwort", bildantwort)
    monkeypatch.setattr(ki, "faehigkeiten", faehigkeiten)
    return gefragt, antworten


async def _erkannt(test_db, kennung: str) -> int:
    buch = await _buch(test_db, kennung, scan_pdf, ["", "", ""])
    await erkennungswache.runde()
    await texterkennung.warten()
    return buch


async def _seiten(client, buch: int) -> list[dict]:
    return (await client.get(f"/api/books/{buch}/textseiten", params={"ab": 1, "anzahl": 3})).json()["seiten"]


async def test_nachbessern_umschalten_und_volltext(laufend, test_db, client, programm, bildmodell):  # noqa: F811
    gefragt, antworten = bildmodell
    buch = await _erkannt(test_db, "nachbessern00a")
    vorher = await _seiten(client, buch)
    assert [(s["schicht"], s["fassung"], s["andere_fassung"], s["nachbesserung"]) for s in vorher] == [("erkannt", "klassisch", False, "")] * 3

    antworten.append(KiFehler("Die Leitstelle antwortet nicht", "weg"))     # die zweite Seite scheitert erst einmal
    r = await client.post(f"/api/books/{buch}/texterkennung/nachbessern", json={"seite": 2})
    assert r.status_code == 200, r.text
    assert r.json() == {"bereit": True, "grund": "", "seiten": [2, 3]}
    await nachbesserung.warten()
    assert gefragt == [settings.texterkennung_ki_modell] * 2

    s = await _seiten(client, buch)
    assert (s[1]["fassung"], s[1]["nachbesserung"], s[1]["nachbesserung_grund"]) == ("klassisch", "fehler", "Die Leitstelle antwortet nicht")
    assert (s[2]["fassung"], s[2]["andere_fassung"], s[2]["nachbesserung"]) == ("ki", True, "")
    assert [b["art"] for b in s[2]["bausteine"]] == ["ueberschrift", "tabelle"]
    assert s[2]["bausteine"][1]["tabelle"] == {"kopf": ["Nummer", "Titel", "Tage"], "reihen": [["1", "Das Haus am Kanal", "14"],
                                               ["2", "Wolken über dem Deich", "21"]], "zahlen": [True, False, True]}
    assert "Wolken über dem Deich" in load_fulltext("nachbessern00a").split("\f")[2]       # Volltext und Suche ziehen nach

    r = await client.post(f"/api/books/{buch}/texterkennung/nachbessern", json={"seite": 2})   # erneut: nur, was noch fehlt
    assert r.json()["seiten"] == [2]
    await nachbesserung.warten()
    assert len(gefragt) == 3 and (await _seiten(client, buch))[1]["fassung"] == "ki"

    r = await client.post(f"/api/books/{buch}/texterkennung/fassung", json={"seite": 3, "gilt": "klassisch"})
    assert r.status_code == 204, r.text
    await nachbesserung.nachgezogen()
    seiten = load_fulltext("nachbessern00a").split("\f")
    assert "Wolken über dem Deich" in seiten[1] and "Wolken über dem Deich" not in seiten[2]    # die Wahl gilt auch für Volltext und Suche
    s = await _seiten(client, buch)
    assert (s[2]["fassung"], s[2]["andere_fassung"]) == ("klassisch", True) and [b["art"] for b in s[2]["bausteine"]] != ["ueberschrift", "tabelle"]
    r = await client.post(f"/api/books/{buch}/texterkennung/fassung", json={"seite": 1, "gilt": "ki"})
    assert r.status_code == 404                                          # Seite 1 hat keine Nachbesserung


async def test_ohne_leitstelle_mit_grund(laufend, test_db, client, programm, monkeypatch):  # noqa: F811
    buch = await _erkannt(test_db, "nachbessern00b")
    monkeypatch.setattr(Ki, "bereit", property(lambda self: False))
    r = await client.post(f"/api/books/{buch}/texterkennung/nachbessern", json={"seite": 1})
    assert r.json() == {"bereit": False, "grund": "Keine Leitstelle eingetragen: ohne sie gibt es keine Nachbesserung", "seiten": []}


async def test_nachbessern_nur_mit_ki_recht_die_fassung_waehlt_jeder(laufend, test_db, client, programm, bildmodell, monkeypatch):  # noqa: F811
    from backend.app.familie import rechte

    buch = await _erkannt(test_db, "nachbessern00c")
    darf = rechte.darf
    monkeypatch.setattr(rechte, "darf", lambda p, f: f != "ki" and darf(p, f))
    r = await client.post(f"/api/books/{buch}/texterkennung/nachbessern", json={"seite": 1})
    assert r.status_code == 403
    r = await client.post(f"/api/books/{buch}/texterkennung/fassung", json={"seite": 1, "gilt": "klassisch"})
    assert r.status_code == 204                                          # schon klassisch: nichts zu tun, aber erlaubt
