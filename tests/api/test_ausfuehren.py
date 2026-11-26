"""Ausführen und Vorprüfung (BF-29) gegen Attrappen von Codeschmiede und Leitstelle; kein echtes Netz."""

import asyncio
import json
from urllib.parse import unquote

import httpx
import pytest
from appkern.leitstelle import Leitstelle

from backend.app.codestellen.dienst import codestellen
from backend.app.codestellen.erkennung import erkennen
from backend.app.codestellen.vorpruefung import Vorpruefer, fehlerzeile
from backend.app.core.config import settings
from backend.app.services import ausfuehren
from backend.app.services.ausfuehren import Reihe, sandbox
from backend.app.services.ki import APP, ki
from tests.api.conftest import buch_erstellen
from tests.backend.test_codestellen import probebuch

CODESCHMIEDE, LEITSTELLE = "https://code.test", "https://leitstelle.test"


class Attrappe:
    """Ein Dienst zum Zuschauen: merkt sich jede Anfrage und antwortet mit dem, was `antwort` daraus macht."""

    def __init__(self, antwort) -> None:
        self.antwort, self.anfragen = antwort, []

    def __call__(self, r: httpx.Request) -> httpx.Response:
        self.anfragen.append(r)
        return self.antwort(r)

    def wege(self) -> list[str]:
        return [r.url.path for r in self.anfragen]


def sandbox_antwort(sprachen=("python", "javascript", "php"), aufzeichnen=("python", "javascript")):
    def antwort(r: httpx.Request) -> httpx.Response:
        if r.url.path == "/api/v1/sandbox/sprachen":
            return httpx.Response(200, json=[{"sprache": s, "fassungen": ["8.4", "8.3"] if s == "php" else [],
                                              "aufzeichnen": s in aufzeichnen} for s in sprachen])
        koerper = json.loads(r.content)
        if r.url.path == "/api/v1/sandbox/aufzeichnen":
            return httpx.Response(200, json={"art": koerper["sprache"], "ausgabe": "6\n", "schritte": [{"zeile": 1, "rahmen": [], "ausgabe": ""}]})
        if "zahlen.reduce" in koerper["code"]:
            return httpx.Response(200, json={"art": "javascript", "fehler": "/tmp/beispiel.js:3\nReferenceError: summe is not defined\n    at x",
                                             "fehlerzeile": 3})
        return httpx.Response(200, json={"art": koerper["sprache"], "ausgabe": "6\n"})
    return antwort


@pytest.fixture
def codeschmiede(monkeypatch):
    """Die Sandbox der Codeschmiede als Attrappe; `einsetzen` tauscht die Antworten."""
    monkeypatch.setattr(settings, "codeschmiede_url", CODESCHMIEDE)
    attrappe = Attrappe(sandbox_antwort())

    def einsetzen(antwort) -> Attrappe:
        attrappe.antwort = antwort
        sandbox._angebot = None
        return attrappe

    sandbox._angebot = None
    sandbox.dienst._client = httpx.AsyncClient(base_url=CODESCHMIEDE, transport=httpx.MockTransport(attrappe))
    attrappe.einsetzen = einsetzen
    yield attrappe
    sandbox.dienst._client = None
    sandbox._angebot = None


def chat_antwort(inhalt: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": inhalt}, "finish_reason": "stop"}], "model": "qwen/qwen3-next-80b"},
                          headers={"X-Leitstelle-Modell": "qwen/qwen3-next-80b"})


@pytest.fixture
def leitstelle(monkeypatch, tmp_path):
    datei = tmp_path / "leitstelle.schluessel"
    datei.write_text("ls_app_test\n")
    monkeypatch.setattr(settings, "leitstelle_adresse", LEITSTELLE)
    monkeypatch.setattr(settings, "leitstelle_schluessel_datei", str(datei))

    def antwort(r: httpx.Request) -> httpx.Response:
        if r.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "qwen/qwen3-next-80b", "x-leitstelle": {"geladen": True}}]})
        return chat_antwort(json.dumps({"grund": "Die Funktion summe kommt aus einem früheren Beispiel.", "fehlt": ["funktion", "erfunden"]}))

    attrappe = Attrappe(antwort)
    client = httpx.AsyncClient(transport=httpx.MockTransport(attrappe))
    ki._zugang = ((LEITSTELLE, "ls_app_test"), Leitstelle(LEITSTELLE, "ls_app_test", APP, client=client), client)
    yield attrappe
    ki._zugang = None


@pytest.fixture
async def buch(test_db, tmp_path, monkeypatch):
    """Ein Buch mit dem Probe-PDF im Speicher; erkannt wird im Test ohne eigenen Prozess."""
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "speicher")
    monkeypatch.setattr(settings, "vorpruefung_abstand_s", 0)

    async def lesen(pfad, fmt):
        return await asyncio.to_thread(erkennen, pfad, fmt)

    monkeypatch.setattr(codestellen, "lesen", lesen)
    monkeypatch.setattr(codestellen, "_vorrang", [])
    monkeypatch.setattr(codestellen, "_reihe", [])
    nr = await buch_erstellen(test_db, hash="codehash1", file_format="pdf", page_count=2)
    ordner = settings.storage_dir / "co" / "de" / "codehash1"
    ordner.mkdir(parents=True)
    probebuch(ordner / "probe.pdf")
    return nr


# -- Sandbox ---------------------------------------------------------------------------------------------------------------

async def test_ohne_codeschmiede_fehlt_die_faehigkeit(client, monkeypatch):
    monkeypatch.setattr(settings, "codeschmiede_url", "")
    s = (await client.get("/api/ausfuehren")).json()
    assert s == {"bereit": False, "sprachen": [], "grund": ausfuehren.KEINE_ADRESSE}
    assert (await client.post("/api/ausfuehren", json={"code": "print(1)", "sprache": "python"})).json() == {"aufzeichnung": None, "grund": ausfuehren.KEINE_ADRESSE}
    assert (await client.get("/api/ausfuehren/funktionen/php")).json() == {}
    assert (await client.get("/api/config/oberflaeche")).json()["anschluesse"]["ausfuehren"] is False


async def test_lauf_mit_aufzeichnung(client, codeschmiede):
    s = (await client.get("/api/ausfuehren")).json()
    assert s["bereit"] and [a["sprache"] for a in s["sprachen"]] == ["python", "javascript", "php"]
    lauf = (await client.post("/api/ausfuehren", json={"code": "print(6)", "sprache": "python", "eingabe": ["a"]})).json()
    assert lauf["grund"] == "" and lauf["aufzeichnung"]["ausgabe"] == "6\n" and lauf["aufzeichnung"]["schritte"][0]["zeile"] == 1
    gesendet = json.loads(codeschmiede.anfragen[-1].content)
    assert codeschmiede.wege()[-1] == "/api/v1/sandbox/aufzeichnen" and gesendet == {"code": "print(6)", "sprache": "python", "eingabe": ["a"]}
    assert (await client.get("/api/config/oberflaeche")).json()["anschluesse"]["ausfuehren"] is True


async def test_php_ohne_marke_und_ohne_aufzeichnung(client, codeschmiede):
    lauf = (await client.post("/api/ausfuehren", json={"code": "echo 6;", "sprache": "php", "fassung": "8.3"})).json()
    gesendet = json.loads(codeschmiede.anfragen[-1].content)
    assert codeschmiede.wege()[-1] == "/api/v1/sandbox/ausfuehren"
    assert gesendet == {"code": "<?php echo 6;", "sprache": "php", "fassung": "8.3"} and lauf["aufzeichnung"]["schritte"] == []
    assert ausfuehren.mit_php_marke("<?php echo 1;", "php") == "<?php echo 1;"
    assert (await client.post("/api/ausfuehren", json={"code": "x" * 20_001, "sprache": "php"})).status_code == 422


@pytest.mark.parametrize("antwort, grund", [
    (lambda r: httpx.Response(403, json={"detail": "Diese App darf die Sandbox nicht nutzen (Einstellung Sandbox für Apps)"}), ausfuehren.NICHT_ZUGELASSEN),
    (lambda r: httpx.Response(429, json={"detail": "Es läuft schon ein Lauf dieser App"}), ausfuehren.BESETZT),
])
async def test_gruende_statt_fehler(client, codeschmiede, antwort, grund):
    def gemischt(r):
        return sandbox_antwort()(r) if r.url.path.endswith("/sprachen") else antwort(r)
    codeschmiede.einsetzen(gemischt)
    lauf = (await client.post("/api/ausfuehren", json={"code": "print(1)", "sprache": "python"})).json()
    assert lauf == {"aufzeichnung": None, "grund": grund}


async def test_nicht_erreichbar(client, codeschmiede):
    def weg(r):
        raise httpx.ConnectError("weg", request=r)
    codeschmiede.einsetzen(weg)
    s = (await client.get("/api/ausfuehren")).json()
    assert s["bereit"] is False and s["grund"] == ausfuehren.NICHT_ERREICHBAR
    v = {x["kennung"]: x for x in (await client.get("/api/verbindungen")).json()}
    assert v["codeschmiede"]["stand"] == "warn" and v["codeschmiede"]["text"] == ausfuehren.NICHT_ERREICHBAR


async def test_reihe_menschen_vor_hintergrund():
    reihe, folge = Reihe(), []
    tor = asyncio.Event()

    async def lauf(name, vorrang, warten=None):
        async with reihe.platz(vorrang):
            folge.append(name)
            if warten:
                await warten.wait()

    erster = asyncio.create_task(lauf("hintergrund 1", False, tor))
    await asyncio.sleep(0)
    andere = [asyncio.create_task(lauf("hintergrund 2", False)), asyncio.create_task(lauf("mensch", True))]
    await asyncio.sleep(0)
    tor.set()
    await asyncio.gather(erster, *andere)
    assert folge == ["hintergrund 1", "mensch", "hintergrund 2"]


# -- Codestellen eines Buchs ------------------------------------------------------------------------------------------------

async def test_codestellen_erst_ausstehend_dann_erkannt(client, buch, codeschmiede):
    r = (await client.get(f"/api/books/{buch}/codestellen")).json()
    assert r["stand"] == "ausstehend" and codestellen._vorrang == [buch]
    await codestellen.erkennen(codestellen._vorrang.pop(0))
    r = (await client.get(f"/api/books/{buch}/codestellen")).json()
    assert r["stand"] == "erkannt" and r["format"] == "pdf" and r["anzahl"] == 3
    python, js, ausgabe = r["stellen"]
    assert python["ausfuehrbar"] and python["vorpruefung"]["stand"] == "offen" and [t["seite"] for t in python["teile"]] == [1, 2]
    assert js["ausfuehrbar"] and not ausgabe["ausfuehrbar"] and ausgabe["vorpruefung"] is None
    seite2 = (await client.get(f"/api/books/{buch}/codestellen", params={"von": 2, "bis": 2})).json()
    assert len(seite2["stellen"]) == 3                       # die Kette von Seite 1 reicht hinein
    seite1 = (await client.get(f"/api/books/{buch}/codestellen", params={"von": 1, "bis": 1})).json()
    assert [s["sprache"] for s in seite1["stellen"]] == ["python"]
    assert (await client.get("/api/books/9999/codestellen")).status_code == 404


async def test_ohne_sandbox_keine_taste(client, buch, monkeypatch):
    monkeypatch.setattr(settings, "codeschmiede_url", "")
    await codestellen.erkennen(buch)
    r = (await client.get(f"/api/books/{buch}/codestellen")).json()
    assert r["stand"] == "erkannt" and not any(s["ausfuehrbar"] for s in r["stellen"])


async def test_nachlauf_nur_buecher_ohne_erkennung(test_db, buch):
    assert await codestellen.nachlauf(5) == 1 and codestellen._reihe == [buch]
    await codestellen.erkennen(codestellen._reihe.pop(0))
    assert await codestellen.nachlauf(5) == 0


# -- Vorprüfung ---------------------------------------------------------------------------------------------------------------

async def test_vorpruefung_lauf_und_ki(client, buch, codeschmiede, leitstelle):
    await codestellen.erkennen(buch)
    pruefer = Vorpruefer(sandbox, ki)
    assert await pruefer.runde() == 2
    r = (await client.get(f"/api/books/{buch}/codestellen")).json()
    python, js, _ = r["stellen"]
    assert python["vorpruefung"]["stand"] == "laeuft" and python["vorpruefung"]["ausgabe"] == "6\n"
    assert js["vorpruefung"] | {"geprueft_am": ""} == {"stand": "auszug", "quelle": "ki", "ausgabe": "", "fehler": "ReferenceError: summe is not defined",
                                                       "grund": "Die Funktion summe kommt aus einem früheren Beispiel.", "fehlt": ["funktion"], "geprueft_am": ""}
    anfrage = leitstelle.anfragen[-1]
    koerper = json.loads(anfrage.content)
    assert koerper["model"] == settings.ki_modell and koerper["response_format"]["type"] == "json_schema"
    assert anfrage.headers["Authorization"] == "Bearer ls_app_test" and anfrage.headers["X-Leitstelle-Prioritaet"] == "hintergrund"
    assert anfrage.headers["X-Leitstelle-Arbeit"].startswith("bf-vorpruefung-")
    assert unquote(anfrage.headers["X-Leitstelle-Titel"]).startswith("BücherFreunde: Vorprüfung")
    vorher = len(codeschmiede.anfragen)
    assert await pruefer.runde() == 0 and len(codeschmiede.anfragen) == vorher           # gemerkt, bis der Code sich ändert


async def test_vorpruefung_ohne_leitstelle_nennt_den_fehler(client, buch, codeschmiede, monkeypatch):
    monkeypatch.setattr(settings, "leitstelle_adresse", "")
    await codestellen.erkennen(buch)
    await Vorpruefer(sandbox, ki).runde()
    js = (await client.get(f"/api/books/{buch}/codestellen")).json()["stellen"][1]
    assert js["vorpruefung"]["quelle"] == "lauf" and js["vorpruefung"]["grund"] == "ReferenceError: summe is not defined"


async def test_vorpruefung_haelt_bei_ablehnung_der_leitstelle(buch, codeschmiede, leitstelle):
    leitstelle.antwort = lambda r: httpx.Response(403, json={"error": {"code": "faehigkeit_nicht_erlaubt", "message": "Fähigkeit text fehlt"}})
    await codestellen.erkennen(buch)
    pruefer = Vorpruefer(sandbox, ki)
    await pruefer.runde()
    assert pruefer.angehalten and "Fähigkeit text fehlt" in pruefer.grund
    assert len(leitstelle.anfragen) == 1                                                  # nie in einer Schleife
    stand = await pruefer.stand()
    assert stand.angehalten and stand.offen == 1 and stand.geprueft == 1
    pruefer.fortsetzen()
    assert not pruefer.angehalten and pruefer.grund == ""


async def test_vorpruefung_haelt_bei_ablehnung_der_sandbox(buch, codeschmiede):
    codeschmiede.einsetzen(lambda r: sandbox_antwort()(r) if r.url.path.endswith("/sprachen") else
                           httpx.Response(403, json={"detail": "Diese App darf die Sandbox nicht nutzen"}))
    await codestellen.erkennen(buch)
    pruefer = Vorpruefer(sandbox, ki)
    assert await pruefer.runde() == 0
    assert pruefer.angehalten and pruefer.grund == ausfuehren.NICHT_ZUGELASSEN


async def test_vorpruefung_wartet_bei_halt_und_laesst_sich_anhalten(buch, codeschmiede, leitstelle, monkeypatch):
    leitstelle.antwort = lambda r: httpx.Response(503, json={"error": {"code": "halt", "message": "Hauptregler auf Halt"}}, headers={"Retry-After": "1"})
    await codestellen.erkennen(buch)
    pruefer = Vorpruefer(sandbox, ki)
    lauf = asyncio.create_task(pruefer.runde())
    while len(leitstelle.anfragen) < 2:                                                   # wartet geduldig und fragt erneut
        await asyncio.sleep(0.05)
    pruefer.anhalten()
    assert await asyncio.wait_for(lauf, 5) == 1 and pruefer.angehalten                    # die laufende Python-Stelle war schon fertig


async def test_verbindungen_und_stand(client, buch, codeschmiede, leitstelle):
    v = {x["kennung"]: x for x in (await client.get("/api/verbindungen")).json()}
    assert v["codeschmiede"] == {"kennung": "codeschmiede", "name": "Codeschmiede", "stand": "gut", "text": "Sandbox für python, javascript, php"}
    assert v["leitstelle"]["stand"] == "gut" and "qwen/qwen3-next-80b" in v["leitstelle"]["text"]
    s = (await client.get("/api/ausfuehren/vorpruefung")).json()
    assert s["bereit"] and s["ki"] and not s["angehalten"]
    assert (await client.post("/api/ausfuehren/vorpruefung/anhalten")).json()["angehalten"]
    assert not (await client.post("/api/ausfuehren/vorpruefung/fortsetzen")).json()["angehalten"]


def test_fehlerzeile():
    assert fehlerzeile("Traceback (most recent call last):\n  File \"x\", line 1\nNameError: name 'np' is not defined\n") == "NameError: name 'np' is not defined"
    assert fehlerzeile("PHP Fatal error:  Uncaught Error: Call to undefined function f() in /tmp/beispiel.php:3") .startswith("PHP Fatal error")
    assert fehlerzeile("") == ""
