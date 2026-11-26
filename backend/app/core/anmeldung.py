"""Anmeldung mit dem Konto der Kellerwolke über den Baustein des Appkern (`appkern.anmeldung`), wie in den anderen
eigenen Apps: Passwort oder Gerät mit Code koppeln, Sitzungen prüft die Kellerwolke, Abmelden beendet sie.

BücherFreunde hat dafür einen eigenen App-Zugang der Kellerwolke (Datei `KELLERWOLKE_SCHLUESSEL_DATEI`, Modus 0600,
angelegt auf dem Rechner der Kellerwolke mit `tools/app_zugang.py --app BücherFreunde`). Über ihn kennt die App
ihren Namen in der Kellerwolke (Anmeldungen gelten dann nur für sie) und das Konto, dem sie gehört: dieses Konto darf
sie nutzen, dazu die Konten aus `ANMELDUNG_KONTEN`. Andere Apps melden sich mit ihrem App-Schlüssel an (Konto mit
`app`); sie dürfen nur die Wege `fundus/*`, und nur die Apps aus `FUNDUS_APPS`.

Ohne Kellerwolke (`KELLERWOLKE_URL` leer) gelten eigene Konten der App (`eigene_anmeldung`), mit denselben Aufrufen. Welche
gilt, entscheidet die `Weiche` zur Laufzeit: Die Ersteinrichtung kann die Kellerwolke eintragen, ohne Neustart (BF-82). Den
App-Zugang liest der Schlüsselbund (`core/schluessel.py`).
"""

from __future__ import annotations

import logging
import ssl

import httpx
from appkern.anmeldung import Anmeldung, Konto

from backend.app.core.config import settings
from backend.app.core.schluessel import Art, lesen as schluessel_lesen
from backend.app.core.eigene_anmeldung import EigeneAnmeldung

logger = logging.getLogger("buecherfreunde.anmeldung")


class EigenerZugang:
    """Name der App und Besitzer laut Kellerwolke, einmal erfragt mit dem eigenen App-Schlüssel."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self.name: str | None = None
        self.besitzer: str | None = None

    def vergessen(self) -> None:
        """Nach einer neuen Adresse oder einem neuen Schlüssel (BF-82): beim nächsten Mal neu erfragen."""
        self.name = self.besitzer = None

    async def erfragen(self) -> str | None:
        if self.name:
            return self.name
        schluessel = schluessel_lesen(Art.KELLERWOLKE)
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


class Weiche:
    """Die Anmeldung, die gerade gilt (BF-82): mit Adresse der Kellerwolke ihr Baustein, ohne sie die eigenen Konten. Wer die
    Adresse ändert (Ersteinrichtung, Anschlüsse), ruft `umstellen`; die Wege der Anmeldung bleiben dieselben."""

    def __init__(self) -> None:
        self._eigene = EigeneAnmeldung()
        self._wolke: Anmeldung | None = None
        self.umstellen()

    def umstellen(self) -> None:
        adresse = settings.kellerwolke_url
        if adresse and self._wolke is None:
            self._wolke = Anmeldung(adresse, erlaubte_konten, client=client, app_name=eigener_zugang.erfragen)
        elif adresse and self._wolke is not None:
            self._wolke.verbinden(adresse, client)
        eigener_zugang.vergessen()

    @property
    def aktiv(self) -> Anmeldung | EigeneAnmeldung:
        return self._wolke if settings.kellerwolke_url and self._wolke is not None else self._eigene

    @property
    def eigene(self) -> EigeneAnmeldung | None:
        """Die eigenen Konten, wenn sie gelten; mit Kellerwolke None."""
        return self._eigene if self.aktiv is self._eigene else None

    async def pruefen(self, token: str) -> Konto | None:
        return await self.aktiv.pruefen(token)

    async def anmelden(self, kennung: str, passwort: str) -> tuple[str, Konto]:
        return await self.aktiv.anmelden(kennung, passwort)

    async def koppeln(self, code: str, name: str, art: str) -> tuple[str, Konto]:
        return await self.aktiv.koppeln(code, name, art)

    async def abmelden(self, token: str) -> None:
        await self.aktiv.abmelden(token)

    async def schliessen(self) -> None:
        await self._eigene.schliessen()
        if self._wolke is not None:
            await self._wolke.schliessen()


anmeldung = Weiche()


async def schliessen() -> None:
    await anmeldung.schliessen()
    await client.aclose()
