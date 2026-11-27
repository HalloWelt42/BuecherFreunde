"""Eine Attrappe der Vertonung für die Tests (BF-14): Stimmen je Bereich, der Strom Satz für Satz, ein kurzer Text als Ton und das
Schema ihrer Schnittstelle. Sie hängt am Verbund der App (`vorlesen/zugang.verbund`), nichts geht hinaus. Nur Katalogstimmen und
eine erfundene fremde Klonstimme; private Stimmen gibt es hier keine echten, nur eine erfundene."""

import base64
import json
import re
from typing import Literal
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel, Field, create_model

from backend.app.core.config import settings
from backend.app.vorlesen import zugang

VERTONUNG = "https://vertonung.probe.test"
APP_ZUGANG = "kw_app_probe_vorlesen_0123456789"
KLON = "0f8c2b9e-1d2a-4c3b-9e8f-7a6b5c4d3e2f"            # eine erfundene fremde Klonstimme
PRIVAT = "5b1e7c3a-2f4d-4a6b-8c9d-0e1f2a3b4c5d"          # eine erfundene private Stimme
WAV = b"RIFF0000WAVEfmt "
SATZENDE = re.compile(r"(?<=[.!?])\s+")


def schema_der_vertonung(**weitere) -> dict:
    """Das Schema, wie die Vertonung es für ihren Strom zeigt: ein Nachbau ihres Vertrags (vertonung, modell/sprechen.py, Stand
    0.18.13), gebaut von FastAPI wie dort. `weitere` hängt Felder an (unbekannte Einstellungen). Ohne verschobene Auswertung der
    Typangaben in dieser Datei, sonst fände FastAPI das Modell der Anfrage nicht."""

    class StimmWahl(BaseModel):
        art: Literal["klon", "katalog"]
        knoten_id: UUID | None = None
        name: str | None = None

    felder = {"text": (str, Field(min_length=1, max_length=8000)), "stimme": (StimmWahl | None, None), "sprache": (str | None, None),
              "tempo": (float, Field(1.0, ge=0.5, le=2.0)), "ausschreiben": (bool, True), **weitere}
    StromAnfrage = create_model("StromAnfrage", **felder)
    app = FastAPI()

    @app.post("/api/v1/sprechen/strom")
    async def strom(a: StromAnfrage) -> dict:                                       # noqa: ARG001 - nur für das Schema
        return {}

    return app.openapi()


class Vertonung:
    """Antwortet wie die Vertonung und merkt sich jede Anfrage. `privat_frei`: steht BücherFreunde unter "Private Stimmen für"?"""

    def __init__(self) -> None:
        self.anfragen: list[httpx.Request] = []
        self.katalog = ["serena", "vivian"]
        self.fremd = [{"id": KLON, "name": "Probesprecher", "bereich": "fremd", "angaben": {"sprache": "de", "name": "Probesprecher"}}]
        self.privat = [{"id": PRIVAT, "name": "Probestimme privat", "bereich": "privat"}]
        self.privat_frei = False
        self.schema: dict | None = schema_der_vertonung()
        self.fehler_nach: int | None = None                  # so viele Sätze, dann eine Zeile fehler
        self.ablehnen: tuple[int, str] | None = None         # jede Anfrage so beantworten

    def koerper(self, weg: str) -> list[dict]:
        return [json.loads(r.content) for r in self.anfragen if r.url.path == weg]

    def __call__(self, r: httpx.Request) -> httpx.Response:
        self.anfragen.append(r)
        if r.headers.get("authorization") != f"Bearer {APP_ZUGANG}":
            return httpx.Response(401, json={"detail": "Anmeldung erforderlich"})
        if self.ablehnen:
            return httpx.Response(self.ablehnen[0], json={"detail": self.ablehnen[1]})
        weg = r.url.path
        if weg == "/api/v1/stimmen":
            return self._stimmen(r.url.params.get("bereich", "fremd"))
        if weg == "/api/v1/sprechen/strom":
            return self._strom(json.loads(r.content))
        if weg == "/api/v1/sprechen":
            return httpx.Response(200, content=WAV + json.loads(r.content)["text"].encode(), headers={"content-type": "audio/wav"})
        if weg == "/api/v1/schnittstelle":
            if self.schema is None:
                return httpx.Response(403, json={"detail": "Nur in der Oberfläche, nicht für andere Apps"})
            return httpx.Response(200, json=self.schema)
        return httpx.Response(404, json={"detail": "Nicht gefunden"})

    def _stimmen(self, bereich: str) -> httpx.Response:
        if bereich == "katalog":
            return httpx.Response(200, json=[{"id": f"katalog:{n}", "name": n, "bereich": "katalog"} for n in self.katalog])
        if bereich == "privat":
            if not self.privat_frei:
                return httpx.Response(403, json={"detail": "Private Stimmen sind dieser App nicht erlaubt"})
            return httpx.Response(200, json=self.privat)
        return httpx.Response(200, json=self.fremd)

    def _strom(self, a: dict) -> httpx.Response:
        saetze = [s for s in SATZENDE.split(a["text"]) if s.strip()]
        zeilen, ab = [], 0
        for nr, s in enumerate(saetze):
            if self.fehler_nach is not None and nr >= self.fehler_nach:
                zeilen.append({"art": "fehler", "meldung": "Sprechen gescheitert: der Mac schläft"})
                break
            von = a["text"].index(s, ab)
            ab = von + len(s)
            zeilen.append({"art": "satz", "nr": nr, "text": s, "gesprochen": s, "von_zeichen": von, "bis_zeichen": ab, "dauer_ms": 100,
                           "ton": base64.b64encode(WAV).decode("ascii")})
        else:
            zeilen.append({"art": "ende", "saetze": len(saetze), "dauer_ms": 100 * len(saetze)})
        inhalt = "".join(json.dumps(z, ensure_ascii=False) + "\n" for z in zeilen).encode()
        return httpx.Response(200, content=inhalt, headers={"content-type": "application/x-ndjson"})


@pytest.fixture
async def vertonung(monkeypatch, tmp_path) -> Vertonung:
    """Die Vertonung als Attrappe, eingetragen mit Adresse und App-Zugang der Kellerwolke (eigene Schlüsseldatei je Test)."""
    zugang_datei = tmp_path / "zugang" / "kellerwolke.schluessel"
    zugang_datei.parent.mkdir(parents=True, exist_ok=True)
    zugang_datei.write_text(APP_ZUGANG + "\n")
    monkeypatch.setattr(settings, "schluessel_datei", tmp_path / "zugang" / "schluessel.json")
    monkeypatch.setattr(settings, "kellerwolke_schluessel_datei", str(zugang_datei))
    monkeypatch.setattr(settings, "vertonung_url", VERTONUNG)
    v = Vertonung()
    await zugang.verbund.schliessen()
    monkeypatch.setattr(zugang.verbund, "transport", httpx.MockTransport(v))
    yield v
    await zugang.verbund.schliessen()
