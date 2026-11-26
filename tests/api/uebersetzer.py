"""Für die Tests der Übersetzung (BF-71): das Probebuch im Bestand und die Leitstelle als nachgestellter Übersetzer, der nach
der Art der Anfrage antwortet (Name der Antwortform: begriffe, uebersetzung, nacharbeit, pruefung)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from backend.app.core.config import settings
from backend.app.core.database import Database
from backend.app.services.storage import get_storage_path
from tests.api.conftest import buch_erstellen
from tests.uebersetzung_probe import probe_epub

#: Vorlage -> Übersetzung für jeden Block des Probebuchs
DEUTSCH = {
    "Getting Started": "Erste Schritte",
    "A small machine can water <t1>16,000</t1> plants in 1.5 hours, which is about 3\u00a0GB of logs.<x2/>":
        "Eine kleine Maschine kann <t1>16.000</t1> Pflanzen in 1,5 Stunden gießen, das sind etwa 3\u00a0GB Protokolle.<x2/>",
    "Call <x1/> before you start the <t2>pump</t2> &amp; check the <t3>next chapter</t3> for details.":
        "Rufe <x1/> auf, bevor du die <t2>Pumpe</t2> startest, &amp; lies im <t3>nächsten Kapitel</t3> die Einzelheiten.",
    "The garden\u2019s soil is <x1/> in our notes.": "Die Erde des Gartens heißt in unseren Notizen <x1/>.",
    "Fill the tank": "Fülle den Tank",
    "use clean water": "nimm sauberes Wasser",
    "before the first run": "vor dem ersten Lauf",
    "Check the <t1>filter <t2>twice</t2></t1> a week.": "Prüfe den <t1>Filter <t2>zweimal</t2></t1> pro Woche.",
    "Daily water needs": "Täglicher Wasserbedarf",
    "Plant": "Pflanze",
    "Litres": "Liter",
    "Tomato": "Tomate",
    "A garden at dawn.": "Ein Garten im Morgengrauen.",
    "Visit <x1/>": "Besuche <x1/>",
    "<x1/> Measured on a dry day.": "<x1/> Gemessen an einem trockenen Tag.",
    "Watering the Beds": "Die Beete gießen",
    "Water early, water deep.": "Früh gießen, tief gießen.",
    "Bed": "Beet",
    "A raised box of soil.": "Ein erhöhter Kasten mit Erde.",
    "Done.<x1/>Now rest.": "Fertig.<x1/>Jetzt ruhen.",
    "Contents": "Inhalt",
    "<t1>Getting Started</t1>": "<t1>Erste Schritte</t1>",
    "<t1>Watering the Beds</t1>": "<t1>Die Beete gießen</t1>",
}
VORSCHLAG = [{"englisch": "pump", "bleibt": False, "deutsch": "Pumpe", "grund": "Das deutsche Wort ist üblich"},
             {"englisch": "garbage collector", "bleibt": True, "deutsch": "", "grund": "Steht nicht im Buch"}]
IN_ORDNUNG = {"in_ordnung": True, "art": "", "grund": "", "stelle": ""}


def chat(inhalt: object) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(inhalt, ensure_ascii=False)}, "finish_reason": "stop"}],
                                     "model": "qwen/qwen3-next-80b"}, headers={"X-Leitstelle-Modell": "qwen/qwen3-next-80b"})


class Uebersetzer:
    """Antwortet je Art der Anfrage; was der Test einstellt, gilt jeweils einmal (Listen werden abgearbeitet)."""

    def __init__(self, leitstelle) -> None:
        self._modelle = leitstelle.antwort
        self.tabelle: dict[str, str] = dict(DEUTSCH)
        self.nacharbeit: dict[str, list[str]] = {}               # Vorlage -> je Nacharbeit eine Übersetzung
        self.maengel: dict[str, dict] = {}                       # Übersetzung -> ein Mangel des Prüfers (einmal)
        self.kaputt: set[str] = set()                            # Arten, deren nächste Antwort einen Text zu wenig hat
        self.vorschlag: object = {"begriffe": VORSCHLAG}
        self.unterbrechen: Callable[[str, dict], bool] = lambda art, daten: False   # True: Verbindung bricht ab
        self.beantwortet: list[tuple[str, dict]] = []
        self.modelle: list[tuple[str, str]] = []                 # (Art, Modell) je Anfrage
        leitstelle.antwort = self

    def __call__(self, r: httpx.Request) -> httpx.Response:
        if r.url.path == "/v1/models":
            return self._modelle(r)
        koerper = json.loads(r.content)
        art = koerper["response_format"]["json_schema"]["name"]
        daten = json.loads(koerper["messages"][1]["content"])
        self.modelle.append((art, koerper["model"]))
        if self.unterbrechen(art, daten):
            raise httpx.ConnectError("Verbindung abgebrochen")
        antwort = self._antwort(art, daten)
        self.beantwortet.append((art, daten))
        return chat(antwort)

    def _antwort(self, art: str, daten: dict) -> object:
        if art == "begriffe":
            return self.vorschlag
        if art == "pruefung":
            return {"urteile": [self.maengel.pop(p["deutsch"], IN_ORDNUNG) for p in daten["paare"]]}
        if art == "nacharbeit":
            [vorlage] = daten["bloecke"]
            liste = self.nacharbeit.get(vorlage)
            return {"bloecke": [liste.pop(0) if liste else self.tabelle.get(vorlage, vorlage)]}
        texte = [self.tabelle.get(v, v) for v in daten["bloecke"]]
        if art in self.kaputt and len(texte) > 1:
            self.kaputt.discard(art)
            texte = texte[:-1]
        return {"bloecke": texte}

    def gesendet(self, art: str = "uebersetzung") -> list[str]:
        """Die Vorlagen aller beantworteten Anfragen dieser Art, in ihrer Reihenfolge."""
        return [v for a, d in self.beantwortet if a == art for v in d.get("bloecke", [])]


@pytest.fixture
def orte(tmp_path, monkeypatch):
    for ort in ("storage_dir", "umschlaege_dir", "zwischen_dir"):
        monkeypatch.setattr(settings, ort, tmp_path / ort)
    return tmp_path


@pytest.fixture
def uebersetzer(leitstelle, orte, monkeypatch) -> Uebersetzer:  # noqa: F811 - leitstelle kommt aus tests.api.test_ausfuehren
    """Der Übersetzer; der Prüfer rechnet mit dem zweiten Modell, das die Attrappe anbietet."""
    monkeypatch.setattr(settings, "uebersetzen_pruefmodell", "qwen/qwen3-coder-next")
    return Uebersetzer(leitstelle)


async def probebuch(test_db: Database, epub: bytes | None = None, **spalten) -> int:
    """Das Probebuch als EPUB im lokalen Bestand (ohne Kellerwolke)."""
    daten = epub or probe_epub()
    h = hashlib.sha256(daten).hexdigest()
    ordner = get_storage_path(h)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "Garten.epub").write_bytes(daten)
    werte = {"hash": h, "title": "Gardening with Small Machines", "author": "Ada Example", "isbn": "", "language": "en",
             "file_format": "epub", "file_name": "Garten.epub", "storage_path": str(ordner), "page_count": 3} | spalten
    return await buch_erstellen(test_db, **werte)


def abgelegt(buch_hash: str) -> Path:
    return get_storage_path(buch_hash) / "Fassungen" / "de" / "Garten.epub"


async def warten_bis(bedingung: Callable[[], object], schritte: int = 200) -> None:
    for _ in range(schritte):
        if await bedingung():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Bedingung trat nicht ein")
