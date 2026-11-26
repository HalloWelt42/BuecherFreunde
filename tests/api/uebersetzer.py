"""Für die Tests der Übersetzung (BF-71): das Probebuch im Bestand (als EPUB und als PDF) und die Leitstelle als nachgestellter
Übersetzer, der nach der Art der Anfrage antwortet (Name der Antwortform: begriffe, uebersetzung, nacharbeit, pruefung,
bestaetigung)."""

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
from tests.uebersetzung_probe_pdf import probe_pdf

#: Vorlage, wie das Modell sie sieht (Text als Zeichen), -> seine Übersetzung für jeden Block des Probebuchs
DEUTSCH = {
    "Getting Started": "Erste Schritte",
    "A small machine can water <t1>16,000</t1> plants in 1.5 hours, which is about 3\u00a0GB of logs.<x2/>":
        "Eine kleine Maschine kann <t1>16.000</t1> Pflanzen in 1,5 Stunden gießen, das sind etwa 3\u00a0GB Protokolle.<x2/>",
    "Call <x1/> before you start the <t2>pump</t2> & check the <t3>next chapter</t3> for details.":
        "Rufe <x1/> auf, bevor du die <t2>Pumpe</t2> startest, & lies im <t3>nächsten Kapitel</t3> die Einzelheiten.",
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
#: dasselbe für das Probe-PDF (tests/uebersetzung_probe_pdf.py): jeder Block mit einer Übersetzung, die die festen
#: Prüfungen besteht
DEUTSCH_PDF = {
    "1 Getting Started": "1 Erste Schritte",
    "A small garden robot can water <t1>sixteen</t1> beds in one hour. It needs only a <t2>charged battery</t2> and a full tank.<x3/> Most owners start with one machine and add more later.":
        "Ein kleiner Gartenroboter kann in einer Stunde <t1>sechzehn</t1> Beete gießen. Er braucht nur einen <t2>geladenen Akku</t2> und einen vollen Tank.<x3/> Die meisten Besitzer beginnen mit einer Maschine und kaufen später weitere dazu.",
    "1.1 The First Machine": "1.1 Die erste Maschine",
    "The first machine should be small and quiet. A heavy robot presses the soil and leaves deep tracks between the rows, which makes the next round of watering for all the small young plants less effective. Choose wide wheels and a light frame.":
        "Die erste Maschine sollte klein und leise sein. Ein schwerer Roboter drückt den Boden zusammen und hinterlässt tiefe Spuren zwischen den Reihen, wodurch die nächste Runde des Gießens für alle kleinen jungen Pflanzen weniger wirksam wird. Wähle breite Räder und einen leichten Rahmen.",
    "<x1/> Check the wheels before every run.": "<x1/> Prüfe die Räder vor jeder Fahrt.",
    "<x1/> Clean the filter once a week, even when the water looks clear and the tank shows no dirt at all after the last round.":
        "<x1/> Reinige den Filter einmal pro Woche, auch wenn das Wasser klar aussieht und der Tank nach der letzten Runde gar keinen Schmutz zeigt.",
    "<x1/> Keep a spare battery in a dry place.": "<x1/> Bewahre einen Ersatzakku an einem trockenen Ort auf.",
    "After a few days the robot knows the garden. It stores a map of every bed and returns to its station when the battery runs low.":
        "Nach ein paar Tagen kennt der Roboter den Garten. Er speichert eine Karte jedes Beets und kehrt zu seiner Station zurück, wenn der Akku schwach wird.",
    "<x1/> Measured on a dry morning in early summer.": "<x1/> Gemessen an einem trockenen Morgen im Frühsommer.",
    "1.1.1 Soil and Water": "1.1.1 Boden und Wasser",
    "Sandy soil drains fast and needs short, frequent rounds. Heavy clay holds water for a long time, so the robot waits longer between two rounds.":
        "Sandiger Boden lässt Wasser schnell durch und braucht kurze, häufige Runden. Schwerer Lehm hält das Wasser lange, deshalb wartet der Roboter zwischen zwei Runden länger.",
    "Table 1: Daily water needs": "Tabelle 1: Täglicher Wasserbedarf",
    "Plant": "Pflanze", "Litres": "Liter", "Rounds": "Runden", "Tomato": "Tomate", "Morning": "Morgens", "Lettuce": "Salat",
    "Evening": "Abends",
    "Water that runs off the surface is lost for the plants. A slow drip close to the roots is better than a strong jet from above, and it also keeps the leaves and the stems quite dry for long hours. Good irrigation<x1/> saves water, time and power for the next round.":
        "Wasser, das an der Oberfläche abläuft, geht den Pflanzen verloren. Ein langsames Tropfen nahe an den Wurzeln ist besser als ein kräftiger Strahl von oben, und es hält auch die Blätter und die Stiele für lange Stunden recht trocken. Gute Bewässerung<x1/> spart Wasser, Zeit und Strom für die nächste Runde.",
    "Figure 1: The pump and its hose.": "Abbildung 1: Die Pumpe und ihr Schlauch.",
    "Start the pump from the command line:": "Starte die Pumpe über die Kommandozeile:",
    "Listing 1: Starting the pump": "Listing 1: Die Pumpe starten",
    "The pump stops by itself when the tank is empty. The status light then turns red.":
        "Die Pumpe hält von selbst an, wenn der Tank leer ist. Die Statusleuchte wird dann rot.",
    "1.2 Two Columns": "1.2 Zwei Spalten",
    "Many gardens have two kinds of beds. Raised beds dry out quickly in the sun, while low beds near the fence stay wet for days. The robot learns both kinds and plans its rounds so that no bed is forgotten and none gets too much water. On hot days it adds a second round for the raised beds.":
        "Viele Gärten haben zwei Arten von Beeten. Hochbeete trocknen in der Sonne schnell aus, während niedrige Beete am Zaun tagelang nass bleiben. Der Roboter lernt beide Arten kennen und plant seine Runden so, dass kein Beet vergessen wird und keines zu viel Wasser bekommt. An heißen Tagen fügt er für die Hochbeete eine zweite Runde hinzu.",
    "In winter the robot rests in its station and charges slowly.": "Im Winter ruht der Roboter in seiner Station und lädt langsam.",
    "Both columns end here, and this paragraph runs across the whole width of the page again.":
        "Beide Spalten enden hier, und dieser Absatz läuft wieder über die ganze Breite der Seite.",
    "2 Watering the Beds": "2 Die Beete gießen",
    "Every bed has its own plan. The robot reads the plan in the morning and starts with the driest bed.":
        "Jedes Beet hat seinen eigenen Plan. Der Roboter liest den Plan am Morgen und beginnt mit dem trockensten Beet.",
    "2.1 Morning Rounds": "2.1 Runden am Morgen",
    "Early rounds lose less water to the sun. Most plants also like a cool drink before the day gets warm.":
        "Frühe Runden verlieren weniger Wasser an die Sonne. Die meisten Pflanzen mögen auch einen kühlen Schluck, bevor der Tag warm wird.",
    "Figure 2: A bed at sunrise.": "Abbildung 2: Ein Beet bei Sonnenaufgang.",
    "The next chapter shows how the robot finds its way back in the dark.":
        "Das nächste Kapitel zeigt, wie der Roboter im Dunkeln den Weg zurück findet.",
    "Contents": "Inhalt",
    "<t1>1 Getting Started</t1>": "<t1>1 Erste Schritte</t1>",
    "<t1>1.1 The First Machine</t1>": "<t1>1.1 Die erste Maschine</t1>",
    "<t1>1.1.1 Soil and Water</t1>": "<t1>1.1.1 Boden und Wasser</t1>",
    "<t1>1.2 Two Columns</t1>": "<t1>1.2 Zwei Spalten</t1>",
    "<t1>2 Watering the Beds</t1>": "<t1>2 Die Beete gießen</t1>",
    "<t1>2.1 Morning Rounds</t1>": "<t1>2.1 Runden am Morgen</t1>",
}
VORSCHLAG = [{"englisch": "pump", "bleibt": False, "deutsch": "Pumpe", "nur_deutsch": False, "grund": "Das deutsche Wort ist üblich"},
             {"englisch": "garbage collector", "bleibt": True, "deutsch": "", "nur_deutsch": False, "grund": "Steht nicht im Buch"}]
IN_ORDNUNG = {"in_ordnung": True, "art": "", "grund": "", "stelle": ""}


def chat(inhalt: object) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(inhalt, ensure_ascii=False)}, "finish_reason": "stop"}],
                                     "model": "qwen/qwen3-next-80b"}, headers={"X-Leitstelle-Modell": "qwen/qwen3-next-80b"})


class Uebersetzer:
    """Antwortet je Art der Anfrage; was der Test einstellt, gilt jeweils einmal (Listen werden abgearbeitet)."""

    def __init__(self, leitstelle) -> None:
        self._modelle = leitstelle.antwort
        self.tabelle: dict[str, str] = DEUTSCH | DEUTSCH_PDF
        self.nacharbeit: dict[str, list[str]] = {}               # Vorlage -> je Nacharbeit eine Übersetzung
        self.maengel: dict[str, dict] = {}                       # Übersetzung -> ein Mangel des Prüfers (einmal)
        self.unbestaetigt: set[str] = set()                      # Übersetzungen, deren Einwand die zweite Prüfung verwirft
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
        if art == "bestaetigung":
            return {"entscheidungen": [{"grund": "Die Stelle sagt etwas anderes als das Original",
                                        "berechtigt": f["deutsch"] not in self.unbestaetigt} for f in daten["faelle"]]}
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


async def probebuch_pdf(test_db: Database, pdf: bytes | None = None, **spalten) -> int:
    """Das Probebuch als PDF im lokalen Bestand (ohne Kellerwolke)."""
    daten = pdf or probe_pdf()
    h = hashlib.sha256(daten).hexdigest()
    ordner = get_storage_path(h)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "Garten.pdf").write_bytes(daten)
    werte = {"hash": h, "title": "Gardening with Small Machines", "author": "Ada Example", "isbn": "", "language": "en",
             "file_format": "pdf", "file_name": "Garten.pdf", "storage_path": str(ordner), "page_count": 5} | spalten
    return await buch_erstellen(test_db, **werte)


def abgelegt(buch_hash: str) -> Path:
    return get_storage_path(buch_hash) / "Fassungen" / "de" / "Garten.epub"


async def warten_bis(bedingung: Callable[[], object], schritte: int = 200) -> None:
    for _ in range(schritte):
        if await bedingung():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Bedingung trat nicht ein")
