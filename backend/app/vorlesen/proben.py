"""Stimmproben (BF-114): ein fester Satz je Stimme, einmal von der Vertonung gesprochen und dauerhaft abgelegt, damit jede
Probe sofort spielt. Zwei Arten mit ihren Texten aus `proben.json`: `leser` (die Probe im Leser, mit den Werten des Profils)
und `ansage` (die Probe der Ansagen für die Eltern, ohne Werte wie die Ansagen selbst).

Abgelegt im Ort texte unter `stimmproben/<ordner der stimme>/<art>-<pruefsumme>.wav` (vorlesen/tonablage.py); die Prüfsumme
gehört zu Fassung, Text und Werten. Fehlt eine Probe beim Tippen, wird sie dann gesprochen und abgelegt.

Vorab spricht der Auftrag "Stimmproben vertonen" alle, die fehlen: jede Stimme, die die Vertonung anbietet, dazu ihre Stimme ab
Werk, je mit den Werten jedes Profils. Die Wache sieht beim Start und im Takt (`STIMMPROBEN_TAKT_S`) nach; antwortet die
Vertonung nicht, ruht der Auftrag mit Grund und geht beim nächsten Takt weiter. Von Hand angehalten bleibt er angehalten."""

from __future__ import annotations

import asyncio
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal, get_args

from appkern.vorlesen import VorlesenFehler
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.einrichtung.auftrag import ANGEHALTEN, Auftrag, Ruhen
from backend.app.einrichtung.modelle import Teil
from backend.app.familie import profile
from backend.app.vorlesen import sprechen, stimmen, tonablage, zugang
from backend.app.vorlesen.modelle import Sprechwert, vertont

logger = logging.getLogger("buecherfreunde.vorlesen.proben")
DATEI = Path(__file__).with_name("proben.json")
ORT = "stimmproben"
Art = Literal["leser", "ansage"]
Werte = dict[str, Sprechwert]
TEILE = (("fertig", "Vertont"), ("fehler", "Nicht vertont"))


class Probentexte(BaseModel):
    fassung: int
    leser: str
    ansage: str


class Stimmprobe(BaseModel):
    text: str
    url: str | None                           # leer: die Stimme des Geräts spricht den Text


@lru_cache(maxsize=1)
def texte() -> Probentexte:
    return Probentexte.model_validate(json.loads(DATEI.read_text(encoding="utf-8")))


def text(art: Art) -> str:
    return getattr(texte(), art)


def _werte_text(werte: Werte | None) -> str:
    return json.dumps(werte or {}, sort_keys=True, ensure_ascii=False)


def spricht_vertonung(stimme: str, art: Art) -> bool:
    """Spricht die Vertonung diese Probe? Im Leser auch ihre Stimme ab Werk (leer); die Ansagen kennen nur gewählte Stimmen."""
    return vertont(stimme) or (art == "leser" and stimme == "")


def datei(art: Art, werte: Werte | None = None) -> str:
    return tonablage.dateiname(art, str(texte().fassung), text(art), _werte_text(werte))


def pfad(stimme: str, art: Art, werte: Werte | None = None) -> Path:
    return settings.storage_dir / ORT / tonablage.ordner(stimme) / datei(art, werte)


def pfad_im_ordner(ordner: str, name: str) -> Path:
    """Die Datei einer Probe nach Ordner und Namen (beide vorher nach ihrer Form geprüft)."""
    return settings.storage_dir / ORT / ordner / name


def adresse(stimme: str, art: Art, werte: Werte | None = None) -> str:
    return f"/api/vorlesen/probe/ton/{tonablage.ordner(stimme)}/{datei(art, werte)}"


_sperren: dict[Path, asyncio.Lock] = {}


async def bereitstellen(stimme: str, art: Art, werte: Werte | None = None) -> Path:
    """Die Probe als Datei; fehlt sie, spricht die Vertonung sie jetzt. Wer dieselbe Probe zugleich will, wartet auf die eine."""
    ziel = pfad(stimme, art, werte)
    async with _sperren.setdefault(ziel, asyncio.Lock()):
        if not ziel.exists():
            ton = await sprechen.ton(text(art), stimme, werte)
            await asyncio.to_thread(tonablage.ablegen, ziel, ton)
    _sperren.pop(ziel, None)
    return ziel


async def holen(stimme: str, art: Art, werte: Werte | None = None) -> Stimmprobe:
    """Text und Adresse der Probe; die Stimme des Geräts bekommt nur den Text. Wirft `VorlesenFehler`, wenn die Vertonung eine
    fehlende Probe nicht sprechen kann."""
    if not spricht_vertonung(stimme, art):
        return Stimmprobe(text=text(art), url=None)
    await bereitstellen(stimme, art, werte)
    return Stimmprobe(text=text(art), url=adresse(stimme, art, werte))


# -- Bedarf -----------------------------------------------------------------------------------------------------------------------

class Probe(BaseModel):
    stimme: str
    art: Art
    werte: Werte = {}


async def bedarf() -> list[Probe]:
    """Jede Probe, die jemand hören kann: jede angebotene Stimme (im Leser auch die Stimme ab Werk), im Leser mit den Werten
    jedes Profils, für die Ansagen ohne Werte. Ohne Antwort der Vertonung leer."""
    liste = await stimmen.liste()
    if not liste.da:
        return []
    werte = {_werte_text(p.einstellungen.vorlesen.werte): p.einstellungen.vorlesen.werte for p in await profile.alle()}
    werte.setdefault(_werte_text({}), {})
    aus: list[Probe] = []
    for stimme in ["", *(s.id for s in liste.stimmen)]:
        aus += [Probe(stimme=stimme, art="leser", werte=w) for w in werte.values()]
        if spricht_vertonung(stimme, "ansage"):
            aus.append(Probe(stimme=stimme, art="ansage"))
    return aus


def fehlen(alle: list[Probe]) -> list[Probe]:
    return [p for p in alle if not pfad(p.stimme, p.art, p.werte).exists()]


def _aufraeumen(alle: list[Probe]) -> int:
    """In den Ordnern der angebotenen Stimmen fallen Proben weg, die niemand mehr hören kann (alte Werte, alter Text)."""
    behalten: dict[Path, set[str]] = {}
    for p in alle:
        ziel = pfad(p.stimme, p.art, p.werte)
        behalten.setdefault(ziel.parent, set()).add(ziel.name)
    weg = 0
    for ordner, namen in behalten.items():
        for d in ordner.glob("*.wav") if ordner.is_dir() else []:
            if d.name not in namen and d.name.split("-", 1)[0] in get_args(Art):
                d.unlink(missing_ok=True)
                weg += 1
    return weg


# -- Auftrag ----------------------------------------------------------------------------------------------------------------------

class Stimmproben(Auftrag):
    art = "stimmproben"
    was = "Stimmproben vertonen"

    def abstand_s(self) -> float:
        return settings.stimmproben_abstand_s

    async def zaehlen(self) -> tuple[int, int, list[Teil]]:
        je = {z["stand"]: z["n"] for z in await db.fetch_all("SELECT stand, COUNT(*) AS n FROM stimmprobe_vorrat GROUP BY stand")}
        gesamt = sum(je.values())
        return gesamt, gesamt - je.get("offen", 0), [Teil(schluessel=k, name=n, gesamt=gesamt, fertig=je.get(k, 0)) for k, n in TEILE]

    async def vorbereiten(self) -> None:
        """Je fehlender Probe ein offenes Stück (aus der Wahl beim Start); der Bericht des letzten Laufs fällt weg."""
        await db.execute("DELETE FROM stimmprobe_vorrat")
        for p in (await self.angaben()).get("fehlen", []):
            await db.execute("INSERT OR IGNORE INTO stimmprobe_vorrat(stimme, art, werte) VALUES (?, ?, ?)",
                             (p["stimme"], p["art"], _werte_text(p["werte"])))
        await db.commit()

    async def naechstes(self) -> bool:
        z = await db.fetch_one("SELECT rowid, stimme, art, werte FROM stimmprobe_vorrat WHERE stand = 'offen' ORDER BY rowid LIMIT 1")
        if z is None:
            return False
        if not zugang.bereit():
            raise Ruhen(zugang.NICHT_EINGERICHTET if not zugang.adresse() else zugang.OHNE_ZUGANG)
        try:
            await bereitstellen(z["stimme"], z["art"], json.loads(z["werte"]))
        except VorlesenFehler as f:
            if f.status >= 500:                              # die Vertonung ist weg oder überlastet: später weiter
                raise Ruhen(f.meldung) from f
            await self._vermerken(z["rowid"], "fehler", f.meldung)
            return True
        await self._vermerken(z["rowid"], "fertig")
        return True

    async def danach(self) -> None:
        try:
            weg = await asyncio.to_thread(_aufraeumen, await bedarf())
        except Exception:                                    # noqa: BLE001 - Aufräumen ist Pflege, nie ein Fehler des Auftrags
            logger.info("Stimmproben nicht aufgeräumt", exc_info=True)
            return
        if weg:
            logger.info("Stimmproben: %d alte Proben weggeräumt", weg)

    @staticmethod
    async def _vermerken(nr: int, stand: str, grund: str = "") -> None:
        await db.execute("UPDATE stimmprobe_vorrat SET stand = ?, grund = ? WHERE rowid = ?", (stand, grund, nr))
        await db.commit()


stimmproben = Stimmproben()


class Probenwache:
    """Sieht beim Start und im Takt nach, ob Proben fehlen, und stößt den Auftrag an; ein ruhender geht weiter."""

    def __init__(self) -> None:
        self._aufgabe: asyncio.Task | None = None

    def starten(self) -> None:
        if self._aufgabe is None or self._aufgabe.done():
            self._aufgabe = asyncio.create_task(self._schleife())

    async def stoppen(self) -> None:
        if self._aufgabe is not None:
            self._aufgabe.cancel()
            await asyncio.gather(self._aufgabe, return_exceptions=True)
            self._aufgabe = None

    async def _schleife(self) -> None:
        await asyncio.sleep(settings.stimmproben_erst_s)
        while True:
            try:
                await self.runde()
            except Exception:                                # noqa: BLE001 - die Wache darf nie still enden
                logger.exception("Stimmproben nachsehen")
            await asyncio.sleep(settings.stimmproben_takt_s)

    async def runde(self) -> None:
        if stimmproben.laeuft:
            return
        z = await stimmproben.zeile()
        if z is not None and z["stand"] == "pause" and z["grund"] == ANGEHALTEN:
            return                                           # von Hand angehalten: bleibt so
        if z is not None and z["stand"] in ("pause", "fehler", "wartet") and await db.fetch_one(
                "SELECT 1 FROM stimmprobe_vorrat WHERE stand = 'offen' LIMIT 1"):
            await stimmproben.fortsetzen()
            return
        offen = fehlen(await bedarf())
        if offen:
            logger.info("Stimmproben: %d fehlen", len(offen))
            await stimmproben.beginnen(fehlen=[p.model_dump() for p in offen])


probenwache = Probenwache()
