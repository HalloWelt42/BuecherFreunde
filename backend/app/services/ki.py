"""Der eine Weg zur KI: die Leitstelle (Stufe 1, Fassade; Stand und Rückbau in docs/LEITSTELLE.md).

Adresse und Schlüssel kommen aus der Einrichtung (`LEITSTELLE_ADRESSE`, `LEITSTELLE_SCHLUESSEL_DATEI`), das Modell wählt
die App (`KI_MODELL`); die Leitstelle wählt nur Rechner und Zeitpunkt. Den Zugang selbst bringt der Appkern mit
(`appkern.leitstelle`): keine Lese-Zeitgrenze für Arbeit, Gesundheit nur über die Modellliste, kein Wiederholen von selbst.
Hier steht, was BücherFreunde daraus macht: Gründe in Worten statt Fehlern, und ob es später wieder gehen kann (`weg`), ein
Mensch gefragt ist (`abgelehnt`, nie in einer Schleife wiederholt) oder nur diese eine Anfrage nicht ging (`einzeln`).
Ohne Adresse oder Schlüssel ist `bereit` falsch, und die App arbeitet ohne KI."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Literal

import httpx
from appkern.leitstelle import (
    Abgebrochen, DienstFehler, Gesperrt, KeinModell, Leitstelle, LeitstellenFehler, Nachricht, NichtErlaubt, NichtErreichbar,
    Prioritaet, SchluesselUngueltig, Ungueltig, geduldig,
)
from pydantic import BaseModel, Field

from backend.app.ablage.wolke import _pruefung
from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.ki")
APP = "BücherFreunde"
ARBEIT = httpx.Timeout(10.0, read=None, write=None, pool=None)    # Verbindungsaufbau begrenzt, laufende Arbeit nie

Art = Literal["weg", "abgelehnt", "einzeln"]


class KiFehler(Exception):
    def __init__(self, grund: str, art: Art) -> None:
        super().__init__(grund)
        self.grund, self.art = grund, art


class KiStand(BaseModel):
    bereit: bool                                      # eingerichtet (Adresse und Schlüssel)
    erreichbar: bool = False
    modell: str = ""
    modelle: list[str] = Field(default_factory=list)
    grund: str = ""


def fehler(f: LeitstellenFehler, modell: str) -> KiFehler:
    """Fehler der Leitstelle als Grund in Worten, mit dem, was daraus folgt."""
    if isinstance(f, SchluesselUngueltig):
        return KiFehler("Die Leitstelle kennt den Schlüssel von BücherFreunde nicht", "abgelehnt")
    if isinstance(f, NichtErlaubt):
        return KiFehler(f"Die Leitstelle erlaubt das BücherFreunde nicht: {f.meldung}", "abgelehnt")
    if isinstance(f, KeinModell):
        return KiFehler(f"Die Leitstelle kennt das Modell {modell} nicht (KI_MODELL)", "abgelehnt")
    if isinstance(f, Gesperrt):
        return KiFehler(f"Die Leitstelle hat BücherFreunde gesperrt: {f.meldung}", "abgelehnt")
    if isinstance(f, (Abgebrochen, Ungueltig, DienstFehler)):
        return KiFehler(f"Leitstelle: {f.meldung}", "einzeln")
    if isinstance(f, NichtErreichbar):
        return KiFehler("Die Leitstelle ist gerade nicht erreichbar", "weg")
    return KiFehler(f"Leitstelle: {f.meldung}", "weg")             # Halt, Dienst weg, Rechner schläft


def json_aus(text: str) -> Any:
    """Die JSON-Antwort eines Modells, auch wenn Text oder ein Codezaun darum steht."""
    try:
        return json.loads(text)
    except ValueError:
        treffer = re.search(r"[\[{].*[\]}]", text, re.S)
        if treffer:
            try:
                return json.loads(treffer.group(0))
            except ValueError:
                pass
    raise KiFehler("Die Antwort der KI ist kein JSON", "einzeln")


class Ki:
    def __init__(self) -> None:
        self._zugang: tuple[tuple[str, str], Leitstelle, httpx.AsyncClient] | None = None

    @staticmethod
    def _schluessel() -> str:
        datei = settings.leitstelle_schluessel_datei
        if not datei:
            return ""
        try:
            return Path(datei).read_text(encoding="utf-8").strip()
        except OSError as f:
            logger.warning("Schlüssel der Leitstelle nicht lesbar: %s", f)
            return ""

    @property
    def bereit(self) -> bool:
        return bool(settings.leitstelle_adresse.strip() and self._schluessel())

    @property
    def adresse(self) -> str:
        return settings.leitstelle_adresse.strip().rstrip("/")

    def modell(self) -> str:
        return settings.ki_modell

    def leitstelle(self) -> Leitstelle:
        schluessel = self._schluessel()
        if not (self.adresse and schluessel):
            raise KiFehler("Keine Leitstelle eingetragen (LEITSTELLE_ADRESSE, LEITSTELLE_SCHLUESSEL_DATEI)", "abgelehnt")
        merkmal = (self.adresse, schluessel)
        if self._zugang is None or self._zugang[0] != merkmal:
            client = httpx.AsyncClient(verify=_pruefung(), timeout=ARBEIT)
            self._zugang = (merkmal, Leitstelle(self.adresse, schluessel, APP, client=client), client)
        return self._zugang[1]

    async def schliessen(self) -> None:
        if self._zugang is not None:
            await self._zugang[2].aclose()
            self._zugang = None

    async def stand(self) -> KiStand:
        """Nur die Modellliste der Leitstelle; lädt nie ein Modell."""
        if not self.bereit:
            return KiStand(bereit=False, grund="Keine Leitstelle eingetragen")
        modell = self.modell()
        try:
            modelle = [m.id for m in await self.leitstelle().modelle()]
        except LeitstellenFehler as f:
            return KiStand(bereit=True, modell=modell, grund=fehler(f, modell).grund)
        grund = "" if modell in modelle else f"Die Leitstelle bietet das Modell {modell} nicht an"
        return KiStand(bereit=True, erreichbar=True, modell=modell, modelle=modelle, grund=grund)

    async def antwort(self, system: str, nutzer: str, *, titel: str, prioritaet: Prioritaet | None = None,
                      geduld: bool = False, pruefen: Callable[[], Awaitable[None]] | None = None, **optionen: Any) -> str:
        """Eine Antwort am Stück. `geduld`: warten, solange die Leitstelle sagt, dass es gerade nicht geht (Halt, Dienst
        weg, Rechner schläft); `pruefen` darf das Warten abbrechen. Ein in der Leitstelle abgebrochener Auftrag liefert
        seinen Teiltext nicht als Antwort, sondern als Grund."""
        modell = self.modell()
        nachrichten = [Nachricht(rolle="system", inhalt=system), Nachricht(rolle="user", inhalt=nutzer)]

        async def fragen() -> str:
            a = await self.leitstelle().chat(nachrichten, modell=modell, titel=titel, prioritaet=prioritaet, **optionen)
            if a.abgebrochen:
                raise KiFehler("In der Leitstelle abgebrochen" + (f"; bis dahin: {a.text[:200]}" if a.text else ""), "einzeln")
            return a.text

        try:
            if geduld:
                return await geduldig(fragen, was=f"{APP}: {titel}", pruefen=pruefen)
            return await fragen()
        except LeitstellenFehler as f:
            raise fehler(f, modell) from f

    async def json_antwort(self, system: str, nutzer: str, schema_name: str, schema: dict[str, Any], **art: Any) -> Any:
        """Eine Antwort in fester Form (JSON-Schema; die Leitstelle stuft ab, wenn ein Modell das nicht kann)."""
        format_ = {"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}}
        return json_aus(await self.antwort(system, nutzer, response_format=format_, **art))


ki = Ki()
