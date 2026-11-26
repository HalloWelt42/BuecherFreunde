"""Aufruf anderer Dienste im Haus mit dem App-Zugang der Kellerwolke, auf Wunsch im Auftrag des angemeldeten Menschen."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

import httpx

from backend.app.ablage.wolke import _pruefung, app_kopf


Guete = Literal["gut", "warn", "schlecht"]
PROBE = httpx.Timeout(5.0, connect=4.0)        # eine Prüfung wartet nie lange, auch wenn der Dienst sonst Zeit braucht


class DienstFehler(Exception):
    """Der Dienst ist nicht angeschlossen, nicht erreichbar oder lehnt ab; `meldung` für Menschen, `status` für die eigene
    Antwort, `antwort` der Status, den der Dienst selbst nannte (None: keine Antwort), damit etwa 403 und 429 einen eigenen
    Grund bekommen."""

    def __init__(self, meldung: str, status: int = 503, antwort: int | None = None) -> None:
        super().__init__(meldung)
        self.meldung, self.status, self.antwort = meldung, status, antwort


class Hausdienst:
    def __init__(self, name: str, adresse: Callable[[], str], zeit_s: float = 30.0) -> None:
        self.name, self._adresse, self._zeit = name, adresse, zeit_s
        self._client: httpx.AsyncClient | None = None

    @property
    def adresse(self) -> str:
        return self._adresse().rstrip("/")

    @property
    def client(self) -> httpx.AsyncClient:
        if not self.adresse:
            raise DienstFehler(f"{self.name} ist nicht angeschlossen")
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.adresse, verify=_pruefung(), timeout=httpx.Timeout(self._zeit, connect=4.0),
                                             headers=app_kopf())
        return self._client

    async def schliessen(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def im_auftrag(sitzung: str) -> dict[str, str]:
        return {"X-Kellerwolke-Sitzung": sitzung} if sitzung else {}

    async def hole(self, art: str, weg: str, sitzung: str = "", **weiter) -> httpx.Response:
        try:
            r = await self.client.request(art, weg, headers=self.im_auftrag(sitzung), **weiter)
        except httpx.HTTPError as f:
            raise DienstFehler(f"{self.name} antwortet nicht") from f
        if r.status_code >= 400:
            raise DienstFehler(self._grund(r), 404 if r.status_code == 404 else 502, r.status_code)
        return r

    async def probe(self, weg: str) -> Any:
        """Eine kleine Abfrage zur Prüfung, ohne Auftrag eines Menschen und mit kurzer Zeitgrenze; die Antwort als JSON.
        Wirft DienstFehler mit dem Grund in Worten."""
        try:
            return (await self.hole("GET", weg, timeout=PROBE)).json()
        except ValueError as f:
            raise DienstFehler(f"{self.name} antwortet, aber nicht wie erwartet") from f

    def _grund(self, r: httpx.Response) -> str:
        try:
            grund = r.json().get("detail")
        except (ValueError, AttributeError):
            grund = None
        return f"{self.name}: {grund}" if isinstance(grund, str) else f"{self.name} meldet {r.status_code}"
