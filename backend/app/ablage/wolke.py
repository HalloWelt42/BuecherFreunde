"""Anschluss an die Kellerwolke für Dateien: lesen (auch in Ausschnitten), fortsetzbar hochladen, Begleiter schreiben.
Einzige Stelle mit den Wegen der Ablage; alles andere spricht über diese Klasse. Ohne Adresse oder Schlüssel ist sie
`bereit == False`, dann gilt nur, was auf dem Gerät liegt (Entwicklung, Tests)."""

from __future__ import annotations

import logging
import ssl
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.wolke")
ZEIT = httpx.Timeout(300.0, connect=5.0)


class WolkeFehler(Exception):
    """Die Kellerwolke antwortet nicht oder lehnt ab; `meldung` für Menschen, `status` wie von ihr (0: nicht erreichbar)."""

    def __init__(self, meldung: str, status: int = 0, daten: Any = None) -> None:
        super().__init__(meldung)
        self.meldung, self.status, self.daten = meldung, status, daten


def _pruefung() -> ssl.SSLContext | bool:
    return ssl.create_default_context(cafile=settings.kellerwolke_ca) if settings.kellerwolke_ca else True


def _schluessel() -> str:
    try:
        return Path(settings.kellerwolke_schluessel_datei).read_text(encoding="utf-8").strip() if settings.kellerwolke_schluessel_datei else ""
    except OSError as f:
        logger.warning("App-Zugang der Kellerwolke nicht lesbar: %s", f)
        return ""


class Wolke:
    def __init__(self) -> None:
        self._async: httpx.AsyncClient | None = None
        self._sync: httpx.Client | None = None

    @property
    def bereit(self) -> bool:
        return bool(settings.kellerwolke_url and _schluessel())

    def _auf(self, art: type) -> Any:
        return art(base_url=settings.kellerwolke_url.rstrip("/"), verify=_pruefung(), timeout=ZEIT,
                   headers={"Authorization": "Bearer " + _schluessel()})

    @property
    def client(self) -> httpx.AsyncClient:
        if self._async is None:
            self._async = self._auf(httpx.AsyncClient)
        return self._async

    @property
    def faden(self) -> httpx.Client:
        """Für Arbeit in Fäden und Prozessen (Auswertung), nie in der Ereignisschleife."""
        if self._sync is None:
            self._sync = self._auf(httpx.Client)
        return self._sync

    async def schliessen(self) -> None:
        if self._async is not None:
            await self._async.aclose()
            self._async = None
        if self._sync is not None:
            self._sync.close()
            self._sync = None

    async def rufe(self, art: str, weg: str, **weiter: Any) -> Any:
        try:
            r = await self.client.request(art, weg, **weiter)
        except httpx.HTTPError as f:
            raise WolkeFehler(f"Die Kellerwolke antwortet nicht ({type(f).__name__})") from f
        daten = r.json() if r.content and "json" in r.headers.get("content-type", "") else None
        if r.status_code >= 400:
            raise WolkeFehler(str((daten or {}).get("detail") or f"Die Kellerwolke meldet {r.status_code}"), r.status_code, daten)
        return daten

    # -- lesen ---------------------------------------------------------------------------------------------------------
    def holen(self, knoten: str, ziel: Path) -> None:
        """Eine Datei ganz nach `ziel` (im Faden)."""
        try:
            with self.faden.stream("GET", f"/api/v1/ablage/knoten/{knoten}/inhalt") as r:
                if r.status_code >= 400:
                    raise WolkeFehler(f"Die Datei fehlt in der Kellerwolke ({r.status_code})", r.status_code)
                with ziel.open("wb") as f:
                    for stueck in r.iter_bytes(1 << 20):
                        f.write(stueck)
        except httpx.HTTPError as f:
            raise WolkeFehler(f"Die Kellerwolke antwortet nicht ({type(f).__name__})") from f

    async def strom(self, knoten: str, bereich: str | None) -> httpx.Response:
        """Antwort der Kellerwolke zum Durchreichen (mit Bereich für Leser); der Rufer schließt sie."""
        kopf = {"Range": bereich} if bereich else {}
        try:
            return await self.client.send(self.client.build_request("GET", f"/api/v1/ablage/knoten/{knoten}/inhalt", headers=kopf), stream=True)
        except httpx.HTTPError as f:
            raise WolkeFehler(f"Die Kellerwolke antwortet nicht ({type(f).__name__})") from f

    async def knoten(self, kennung: str) -> dict:
        return await self.rufe("GET", f"/api/v1/ablage/knoten/{kennung}")

    async def gibt_es(self, sha256: str) -> list[dict]:
        return await self.rufe("GET", f"/api/v1/ablage/pruefsumme/{sha256}")

    async def speicher(self) -> dict:
        return await self.rufe("GET", "/api/v1/ablage/speicher")

    # -- schreiben -----------------------------------------------------------------------------------------------------
    async def ordner(self, pfad: str) -> dict:
        return await self.rufe("POST", "/api/v1/ablage/ordner", json={"pfad": pfad})

    async def datei_schreiben(self, pfad: str, quelle: Path) -> dict:
        """Eine Datei vom Gerät an einen Ort in der Kellerwolke, nur neu."""
        async def stuecke() -> AsyncIterator[bytes]:
            with quelle.open("rb") as f:
                while s := f.read(1 << 20):
                    yield s
        return await self.rufe("PUT", "/api/v1/ablage/datei", params={"pfad": pfad}, content=stuecke(),
                               headers={"If-None-Match": "*", "Content-Length": str(quelle.stat().st_size), "Content-Type": "application/octet-stream"})

    async def upload_anlegen(self, name: str, ordner: str, groesse: int, sha256: str) -> dict:
        return await self.rufe("POST", "/api/v1/uploads", json={"name": name, "parent_id": ordner, "groesse": groesse, "pruefsumme": sha256, "nur_neu": True})

    async def upload_stand(self, kennung: str) -> dict:
        return await self.rufe("GET", f"/api/v1/uploads/{kennung}")

    async def upload_teil(self, kennung: str, versatz: int, strom: AsyncIterator[bytes], laenge: int) -> dict:
        return await self.rufe("PATCH", f"/api/v1/uploads/{kennung}", content=strom,
                               headers={"Upload-Offset": str(versatz), "Content-Length": str(laenge), "Content-Type": "application/octet-stream"})

    async def upload_abbrechen(self, kennung: str) -> None:
        await self.rufe("DELETE", f"/api/v1/uploads/{kennung}")

    async def umziehen(self, knoten: str, ordner: str, name: str) -> dict:
        return await self.rufe("POST", f"/api/v1/ablage/knoten/{knoten}/ort", json={"ordner_id": ordner, "name": name})

    async def felder(self, knoten: str, felder: dict) -> None:
        await self.rufe("PATCH", f"/api/v1/ablage/knoten/{knoten}/felder", json={"felder": felder})

    async def begleiter(self, knoten: str) -> list[dict]:
        return await self.rufe("GET", f"/api/v1/ablage/knoten/{knoten}/begleiter")

    async def auszug_schreiben(self, knoten: str, inhalt: bytes) -> str:
        """Der Begleiter "auszug" (Umschlag, Volltext, Angaben) neben dem Original; vorhandener bekommt eine neue Version."""
        alt = next((b for b in await self.begleiter(knoten) if b["rolle"] == "auszug"), None)
        kopf = {"Content-Type": "application/zip", **({"If-Match": f'"{alt["etag"]}"'} if alt else {"If-None-Match": "*"})}
        d = await self.rufe("PUT", f"/api/v1/ablage/knoten/{knoten}/begleiter/auszug", params={"zusatz": ".auszug.zip"}, content=inhalt, headers=kopf)
        return d["id"]


wolke = Wolke()
