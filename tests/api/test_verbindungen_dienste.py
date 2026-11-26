"""Assistent und Nachschlag unter den Verbindungen (BF-92): eine echte, kurze Prüfung statt einer fest grauen Lampe, gegen
Attrappen der Dienste; das öffentliche Lexikon im Netz wird dafür nur gefragt, solange es noch nie gefragt wurde."""

import httpx
import pytest

from backend.app.core.config import settings
from backend.app.services import gespraech, lexikon_nachschlag
from tests.quellen_netz import antwort, mitschnitt

ASSISTENT = "https://assistent.test"
NACHSCHLAG = "https://nachschlag.test"
ANDERE = ("kellerwolke_url", "fundus_url", "codeschmiede_url", "leitstelle_adresse")


@pytest.fixture
def nur_dienste(monkeypatch):
    """Nur Assistent und Nachschlag eingetragen; was sie antworten, legt der Test fest (`antworten[weg]`)."""
    for name in ANDERE:
        monkeypatch.setattr(settings, name, "")
    monkeypatch.setattr(settings, "assistent_url", ASSISTENT)
    monkeypatch.setattr(settings, "nachschlag_url", NACHSCHLAG)
    antworten: dict[str, httpx.Response | Exception] = {}

    def senden(r: httpx.Request) -> httpx.Response:
        a = antworten[f"{r.url.host}{r.url.path}"]
        if isinstance(a, Exception):
            raise a
        return a

    for dienst, adresse in ((gespraech.dienst, ASSISTENT), (lexikon_nachschlag.dienst, NACHSCHLAG)):
        dienst._client = httpx.AsyncClient(base_url=adresse, transport=httpx.MockTransport(senden))
    yield antworten
    for dienst in (gespraech.dienst, lexikon_nachschlag.dienst):
        dienst._client = None


async def _verbindungen(client, auth_headers) -> dict[str, dict]:
    return {v["kennung"]: v for v in (await client.get("/api/verbindungen", headers=auth_headers)).json()}


async def test_beide_antworten(client, auth_headers, nur_dienste):
    nur_dienste["assistent.test/api/v1/ich"] = httpx.Response(200, json={"id": "x", "name": "BücherFreunde", "app": "buecherfreunde"})
    nur_dienste["nachschlag.test/api/v1/buecher"] = httpx.Response(200, json={"buecher": [{"kennung": "a", "titel": "A"}, {"kennung": "b", "titel": "B"}]})
    v = await _verbindungen(client, auth_headers)
    assert v["assistent"] == {"kennung": "assistent", "name": "Assistent", "stand": "gut", "text": "Chat für alle Fragen, auch zu Stellen im Buch"}
    assert v["nachschlag"] == {"kennung": "nachschlag", "name": "Nachschlag", "stand": "gut", "text": "2 Lexika und Handbücher zum Nachschlagen beim Lesen"}


async def test_ausfall_mit_grund(client, auth_headers, nur_dienste):
    nur_dienste["assistent.test/api/v1/ich"] = httpx.ConnectError("weg")
    nur_dienste["nachschlag.test/api/v1/buecher"] = httpx.Response(500, json={"detail": "Index wird gebaut"})
    v = await _verbindungen(client, auth_headers)
    assert v["assistent"]["stand"] == "schlecht" and v["assistent"]["text"] == "Der Assistent antwortet nicht"
    assert v["nachschlag"]["stand"] == "schlecht" and v["nachschlag"]["text"] == "Nachschlag: Index wird gebaut"


async def test_assistent_ohne_app_zugang_warnt(client, auth_headers, nur_dienste):
    nur_dienste["assistent.test/api/v1/ich"] = httpx.Response(200, json={"id": "x", "name": "jemand", "app": ""})
    nur_dienste["nachschlag.test/api/v1/buecher"] = httpx.Response(200, json={"buecher": []})
    v = await _verbindungen(client, auth_headers)
    assert v["assistent"]["stand"] == "warn" and "nicht als App" in v["assistent"]["text"]


async def test_lexikon_im_netz_nur_aus_dem_gemerkten(client, auth_headers, netz, monkeypatch):
    """Die Verbindungen fragen das öffentliche Lexikon nie selbst; sie zeigen, was beim Nachschlagen oder "Neu prüfen" kam."""
    for name in (*ANDERE, "assistent_url", "nachschlag_url"):
        monkeypatch.setattr(settings, name, "")
    monkeypatch.setattr(settings, "wikipedia_enabled", True)
    v = await _verbindungen(client, auth_headers)
    assert v["nachschlag"] == {"kennung": "nachschlag", "name": "Lexikon im Netz", "stand": "aus", "text": "Öffentliches Lexikon im Netz: Noch nicht gefragt"}
    assert netz.anfragen == []
    netz.setze("www.wikidata.org", antwort(mitschnitt("wikidata_ausgabe.json")))
    assert (await client.post("/api/metadata/quellen/wikipedia/pruefen", headers=auth_headers)).json()["stand"] == "gut"
    v = await _verbindungen(client, auth_headers)
    assert v["nachschlag"]["stand"] == "gut" and v["nachschlag"]["text"].startswith("Öffentliches Lexikon im Netz: Zuletzt gut")


async def test_haengender_dienst_haelt_die_liste_nicht_auf(client, auth_headers, nur_dienste, monkeypatch):
    import asyncio

    from backend.app.api import neubau

    async def haengt(*_a, **_k):
        await asyncio.sleep(60)

    monkeypatch.setattr(neubau, "FRIST_S", 0.05)
    monkeypatch.setattr(gespraech, "stand", haengt)
    nur_dienste["nachschlag.test/api/v1/buecher"] = httpx.Response(200, json={"buecher": []})
    v = await _verbindungen(client, auth_headers)
    assert v["assistent"] == {"kennung": "assistent", "name": "Assistent", "stand": "schlecht", "text": "antwortet nicht binnen 0 Sekunden"}
    assert v["nachschlag"]["stand"] == "gut"


async def test_fundus_eine_lampe_ohne_geraetenamen(client, auth_headers, nur_dienste, monkeypatch):
    """Ob der Fundus gerade nach Bedeutung suchen kann, steht in seiner eigenen Lampe; eine Lampe für einen Rechner gibt es
    nicht (welcher rechnet, entscheiden Fundus und Leitstelle)."""
    from backend.app.services import bedeutung

    monkeypatch.setattr(settings, "fundus_url", "https://fundus.test")
    monkeypatch.setattr(settings, "fundus_sammlung", "buecher")
    antwort_suche: list[dict] = [{"nur_woertlich": True, "treffer": []}]

    def fundus(r: httpx.Request) -> httpx.Response:
        if r.url.path == "/api/v1/sammlungen":
            return httpx.Response(200, json=[{"name": "buecher", "kennung": "k1"}])
        return httpx.Response(200, json=antwort_suche[0])

    monkeypatch.setattr(bedeutung, "_client", httpx.AsyncClient(base_url="https://fundus.test", transport=httpx.MockTransport(fundus)))
    monkeypatch.setattr(bedeutung, "_sammlung", ("", 0.0))
    nur_dienste["assistent.test/api/v1/ich"] = httpx.Response(200, json={"app": "buecherfreunde"})
    nur_dienste["nachschlag.test/api/v1/buecher"] = httpx.Response(200, json={"buecher": []})
    v = await _verbindungen(client, auth_headers)
    assert "rechner" not in v and not any(x["name"] == "MacBook" for x in v.values())
    assert v["fundus"] == {"kennung": "fundus", "name": "Fundus", "stand": "warn", "text": "Der Rechner für die Bedeutung schläft"}
    antwort_suche[0] = {"treffer": []}
    v = await _verbindungen(client, auth_headers)
    assert v["fundus"] == {"kennung": "fundus", "name": "Fundus", "stand": "gut", "text": "Bücher nach Bedeutung durchsuchbar"}
