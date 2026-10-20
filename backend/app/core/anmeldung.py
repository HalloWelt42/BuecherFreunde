"""Anmeldung mit dem Konto der Kellerwolke über den Baustein des Appkern (`appkern.anmeldung`), wie in den anderen
eigenen Apps: Passwort oder Gerät mit Code koppeln, Sitzungen prüft die Kellerwolke, Abmelden beendet sie.

BücherFreunde hat dafür einen eigenen App-Zugang der Kellerwolke (Datei `KELLERWOLKE_SCHLUESSEL_DATEI`, Modus 0600,
angelegt auf dem Rechner der Kellerwolke mit `tools/app_zugang.py --app BücherFreunde`). Über ihn kennt die App
ihren Namen in der Kellerwolke (Anmeldungen gelten dann nur für sie) und das Konto, dem sie gehört: dieses Konto darf
sie nutzen, dazu die Konten aus `ANMELDUNG_KONTEN`. Andere Apps melden sich mit ihrem App-Schlüssel an (Konto mit
`app`); sie dürfen nur die Wege `fundus/*`, und nur die Apps aus `FUNDUS_APPS`.
"""

from __future__ import annotations

import logging
import ssl
from pathlib import Path

import httpx
from appkern.anmeldung import Anmeldung

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.anmeldung")


class EigenerZugang:
    """Name der App und Besitzer laut Kellerwolke, einmal erfragt mit dem eigenen App-Schlüssel."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self.name: str | None = None
        self.besitzer: str | None = None

    def _schluessel(self) -> str:
        datei = settings.kellerwolke_schluessel_datei
        if not datei:
            return ""
        try:
            return Path(datei).read_text(encoding="utf-8").strip()
        except OSError as f:
            logger.warning("App-Zugang der Kellerwolke nicht lesbar: %s", f)
            return ""

    async def erfragen(self) -> str | None:
        if self.name:
            return self.name
        schluessel = self._schluessel()
        if not schluessel or not settings.kellerwolke_url:
            return None
        try:
            r = await self._client.get(f"{settings.kellerwolke_url.rstrip('/')}/api/v1/ablage/ich",
                                       headers={"Authorization": f"Bearer {schluessel}"})
        except httpx.HTTPError as f:
            logger.warning("Kellerwolke für den eigenen Zugang nicht erreichbar: %s", type(f).__name__)
            return None
        if r.status_code >= 400:
            logger.warning("Eigener App-Zugang abgewiesen: HTTP %s", r.status_code)
            return None
        ich = r.json()
        self.name, self.besitzer = str(ich.get("app") or "") or None, str(ich.get("konto") or "") or None
        return self.name


def _pruefung() -> ssl.SSLContext | bool:
    return ssl.create_default_context(cafile=settings.kellerwolke_ca) if settings.kellerwolke_ca else True


client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0), verify=_pruefung())
eigener_zugang = EigenerZugang(client)


def erlaubte_konten() -> set[str]:
    weitere = {k.strip() for k in settings.anmeldung_konten.split(",") if k.strip()}
    return weitere | ({eigener_zugang.besitzer} if eigener_zugang.besitzer else set())


def erlaubte_apps() -> set[str]:
    return {a.strip().lower() for a in settings.fundus_apps.split(",") if a.strip()}


anmeldung = Anmeldung(settings.kellerwolke_url, erlaubte_konten, client=client, app_name=eigener_zugang.erfragen)


async def schliessen() -> None:
    await anmeldung.schliessen()
    await client.aclose()
