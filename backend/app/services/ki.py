"""Der eine Weg zur KI: die Leitstelle (Stufe 1, Fassade; Stand und Rückbau in docs/LEITSTELLE.md).

Adresse und Schlüssel kommen aus der Einrichtung (`LEITSTELLE_ADRESSE`, `LEITSTELLE_SCHLUESSEL_DATEI`), das Modell wählt
die App (`KI_MODELL`); die Leitstelle wählt nur Rechner und Zeitpunkt. Den Zugang selbst bringt der Appkern mit
(`appkern.leitstelle`): keine Lese-Zeitgrenze für Arbeit, Gesundheit nur über die Modellliste, kein Wiederholen von selbst.
Hier steht, was BücherFreunde daraus macht: Gründe in Worten statt Fehlern, und ob es später wieder gehen kann (`weg`), ein
Mensch gefragt ist (`abgelehnt`, nie in einer Schleife wiederholt) oder nur diese eine Anfrage nicht ging (`einzeln`).
Ohne Adresse oder Schlüssel ist `bereit` falsch, und die App arbeitet ohne KI.

Welches Modell gilt: die Wahl aus den Einstellungen, solange die Leitstelle sie anbietet, sonst die Vorgabe `KI_MODELL`;
warum, steht im Grund des Stands (`/api/ai/status`, Verbindungen). Gelöscht wird dabei keine Wahl."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Literal

import httpx
from appkern.leitstelle import (
    Abgebrochen, DienstFehler, Gesperrt, KeinModell, Leitstelle, LeitstellenFehler, Modell, Nachricht, NichtErlaubt, NichtErreichbar,
    Prioritaet, SchluesselUngueltig, Ungueltig, geduldig,
)
from pydantic import BaseModel, Field

from backend.app.ablage.wolke import _pruefung
from backend.app.core.config import settings
from backend.app.core.database import db

logger = logging.getLogger("buecherfreunde.ki")
APP = "BücherFreunde"
WAHL = "ki_modell"                                                 # Schlüssel der Modellwahl in app_settings
ANGEBOT_GILT_S = 600                                               # so lange gilt die geholte Modellliste
ARBEIT = httpx.Timeout(10.0, read=None, write=None, pool=None)    # Verbindungsaufbau begrenzt, laufende Arbeit nie

Art = Literal["weg", "abgelehnt", "einzeln"]


class KiFehler(Exception):
    def __init__(self, grund: str, art: Art) -> None:
        super().__init__(grund)
        self.grund, self.art = grund, art


class KiStand(BaseModel):
    bereit: bool                                      # eingerichtet (Adresse und Schlüssel)
    erreichbar: bool = False                          # die Leitstelle antwortet
    nutzbar: bool = False                             # und bietet das Modell an, das gilt
    modell: str = ""                                  # das Modell, das gilt: die Wahl, wenn angeboten, sonst KI_MODELL
    gewaehlt: str = ""                                # die Wahl aus den Einstellungen (leer: keine)
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


def bietet(modelle: list[Modell], name: str) -> bool:
    """Ob die Leitstelle das Modell anbietet: Kennung, Name ohne Anbieter oder Anzeigename, wie sie selbst Namen auflöst.
    Zweitnamen, die nur die Leitstelle kennt, sieht die App nicht; ein solcher Name gilt hier als nicht angeboten."""
    klein = name.strip().lower()
    return bool(klein) and any(klein in (m.id.lower(), m.id.lower().split("/")[-1], (m.name or "").lower()) for m in modelle)


class Ki:
    def __init__(self) -> None:
        self._zugang: tuple[tuple[str, str], Leitstelle, httpx.AsyncClient] | None = None
        self._wahl: str | None = None                                  # aus den Einstellungen; None: noch nicht gelesen
        self._angebot: tuple[float, list[Modell]] | None = None
        self._gilt = ""                                                # zuletzt bestimmtes Modell, das gilt

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
        """Das Modell, das zuletzt galt (ohne die Leitstelle zu fragen); vor der ersten Prüfung die Vorgabe."""
        return self._gilt or settings.ki_modell

    async def wahl_laden(self) -> None:
        """Die Wahl aus den Einstellungen; ob sie gilt, entscheidet erst das Angebot der Leitstelle (`gilt`)."""
        z = await db.fetch_one("SELECT value FROM app_settings WHERE key = ?", (WAHL,))
        self._wahl = (z["value"] or "").strip() if z else ""

    async def waehlen(self, modell: str) -> None:
        """Ein anderes Modell, gemerkt über einen Neustart."""
        await db.execute("INSERT INTO app_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                         (WAHL, modell))
        await db.commit()
        self._wahl = modell

    async def angebot(self, frisch: bool = False) -> list[Modell]:
        """Was die Leitstelle der App anbietet (`GET /v1/models`, lädt nie ein Modell), eine Weile gemerkt."""
        if frisch or self._angebot is None or time.monotonic() - self._angebot[0] > ANGEBOT_GILT_S:
            self._angebot = (time.monotonic(), await self.leitstelle().modelle())
        return self._angebot[1]

    async def _fruehere_wahl(self, modelle: list[Modell]) -> str:
        """Die Modellwahl der früheren direkten Anbindung (`lm_studio_model`) gilt als Wahl, aber nur, wenn die Leitstelle
        den Namen anbietet; dann wird sie übernommen. Der alte Wert bleibt stehen."""
        z = await db.fetch_one("SELECT value FROM app_settings WHERE key = 'lm_studio_model'")
        alt = (z["value"] or "").strip() if z else ""
        if not alt or not bietet(modelle, alt):
            return ""
        await db.execute("INSERT OR IGNORE INTO app_settings(key, value) VALUES (?, ?)", (WAHL, alt))
        await db.commit()
        self._wahl = alt
        return alt

    async def gilt(self, frisch: bool = False) -> tuple[str, str]:
        """Das Modell, das gilt, und warum es nicht das gewählte ist: die Wahl, wenn die Leitstelle sie anbietet, sonst die
        Vorgabe `KI_MODELL`. Fragt die Leitstelle (wirft LeitstellenFehler)."""
        modelle = await self.angebot(frisch)
        if self._wahl is None:
            await self.wahl_laden()
        wahl = self._wahl or await self._fruehere_wahl(modelle)
        vorgabe, gruende = settings.ki_modell, []
        if wahl and bietet(modelle, wahl):
            self._gilt = wahl
            return wahl, ""
        if wahl:
            gruende.append(f"Das gewählte Modell {wahl} bietet die Leitstelle nicht an; es gilt die Vorgabe {vorgabe}")
        if not bietet(modelle, vorgabe):
            gruende.append(f"Die Leitstelle bietet das Modell {vorgabe} nicht an (KI_MODELL)")
        self._gilt = vorgabe
        return vorgabe, "; ".join(gruende)

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
        try:
            modell, grund = await self.gilt(frisch=True)
        except LeitstellenFehler as f:
            return KiStand(bereit=True, modell=self.modell(), gewaehlt=self._wahl or "", grund=fehler(f, self.modell()).grund)
        modelle = await self.angebot()
        return KiStand(bereit=True, erreichbar=True, nutzbar=bietet(modelle, modell), modell=modell, gewaehlt=self._wahl or "",
                       modelle=[m.id for m in modelle], grund=grund)

    async def antwort(self, system: str, nutzer: str, *, titel: str, prioritaet: Prioritaet | None = None,
                      geduld: bool = False, pruefen: Callable[[], Awaitable[None]] | None = None, **optionen: Any) -> str:
        """Eine Antwort am Stück. `geduld`: warten, solange die Leitstelle sagt, dass es gerade nicht geht (Halt, Dienst
        weg, Rechner schläft); `pruefen` darf das Warten abbrechen. Ein in der Leitstelle abgebrochener Auftrag liefert
        seinen Teiltext nicht als Antwort, sondern als Grund."""
        nachrichten = [Nachricht(rolle="system", inhalt=system), Nachricht(rolle="user", inhalt=nutzer)]

        async def fragen() -> str:
            modell, _ = await self.gilt()
            a = await self.leitstelle().chat(nachrichten, modell=modell, titel=titel, prioritaet=prioritaet, **optionen)
            if a.abgebrochen:
                raise KiFehler("In der Leitstelle abgebrochen" + (f"; bis dahin: {a.text[:200]}" if a.text else ""), "einzeln")
            return a.text

        try:
            if geduld:
                return await geduldig(fragen, was=f"{APP}: {titel}", pruefen=pruefen)
            return await fragen()
        except LeitstellenFehler as f:
            raise fehler(f, self.modell()) from f

    async def json_antwort(self, system: str, nutzer: str, schema_name: str, schema: dict[str, Any], **art: Any) -> Any:
        """Eine Antwort in fester Form (JSON-Schema; die Leitstelle stuft ab, wenn ein Modell das nicht kann)."""
        format_ = {"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}}
        return json_aus(await self.antwort(system, nutzer, response_format=format_, **art))


ki = Ki()
