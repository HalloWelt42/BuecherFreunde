"""Umschläge prüfen (BF-59): ist der Umschlag eines Buchs schlicht (fast weiß, ohne Farbe, `deckblatt.schlicht`), zeigt die
Oberfläche ein gestaltetes Deckblatt. Ein Buch ohne Umschlagdatei gilt ebenfalls als schlicht.

Geprüft wird jedes Buch, dessen Befund fehlt oder zu einem anderen Stand des Umschlags gehört (`umschlag_geprueft` gegen
`storage.umschlag_stand`). So braucht kein Ort, der einen Umschlag speichert, etwas davon zu wissen: ein neuer Umschlag hat
einen neuen Stand und kommt in der nächsten Runde dran. Die Prüfung läuft beim Start und dann im Takt der Einstellung
(`UMSCHLAEGE_PRUEFEN_TAKT_S`), schonend in Teilen mit kurzen Pausen und mit der Bildarbeit in einem eigenen Faden, damit
die App flüssig bleibt. Wer nach einer Runde mit schlichten Umschlägen Bescheid haben will, trägt sich in `nach_runde` ein."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence

from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services import deckblatt
from backend.app.services.storage import get_sidecar_path, umschlag_stand

logger = logging.getLogger("buecherfreunde.umschlagpruefung")
TEIL = 25                                  # so viele Umschläge je Teil, danach eine Pause
PAUSE_S = 0.2


class Offen(BaseModel):
    """Ein Buch, dessen Umschlag zu prüfen ist."""

    id: int
    hash: str


class Befund(BaseModel):
    id: int
    schlicht: bool
    stand: int                             # der Stand des Umschlags, zu dem der Befund gehört


def offene(zeilen: Sequence[dict]) -> list[Offen]:
    """Die Bücher ohne Befund oder mit einem Befund zu einem älteren Umschlag (liest nur den Stand der Dateien)."""
    return [Offen(id=z["id"], hash=z["hash"]) for z in zeilen
            if z["umschlag_schlicht"] is None or z["umschlag_geprueft"] != umschlag_stand(z["hash"])]


def befund(buch: Offen) -> Befund:
    """Der Befund zum jetzigen Umschlag. Der Stand wird vor dem Lesen bestimmt: wird der Umschlag währenddessen neu
    geschrieben, gehört der Befund zum alten Stand, und die nächste Runde prüft ihn wieder."""
    stand = umschlag_stand(buch.hash)
    try:
        daten = get_sidecar_path(buch.hash, "cover.jpg").read_bytes()
    except OSError:
        return Befund(id=buch.id, schlicht=True, stand=stand)           # ohne Umschlagdatei: ein gestaltetes Blatt
    return Befund(id=buch.id, schlicht=deckblatt.schlicht(daten), stand=stand)


def befunde(teil: Sequence[Offen]) -> list[Befund]:
    return [befund(b) for b in teil]


class Umschlagpruefung:
    def __init__(self) -> None:
        self._lauf: asyncio.Task | None = None
        self.nach_runde: list[Callable[[], None]] = []      # wer nach einer Runde mit schlichten Umschlägen Bescheid bekommt

    def starten(self) -> None:
        self._lauf = asyncio.create_task(self._arbeiten())

    async def stoppen(self) -> None:
        if self._lauf is not None:
            self._lauf.cancel()
            self._lauf = None

    async def _arbeiten(self) -> None:
        while True:
            try:
                await self.runde()
            except asyncio.CancelledError:
                raise
            except Exception:                              # noqa: BLE001 - die Prüfung darf nie still enden
                logger.exception("Umschlagprüfung")
            await asyncio.sleep(settings.umschlaege_pruefen_takt_s)

    async def runde(self) -> int:
        """Alle offenen Umschläge, Teil für Teil; gibt zurück, wie viele geprüft wurden."""
        zeilen = await db.fetch_all("SELECT id, hash, umschlag_schlicht, umschlag_geprueft FROM books")
        offen = await asyncio.to_thread(offene, zeilen)
        schlichte = 0
        for anfang in range(0, len(offen), TEIL):
            teil = await asyncio.to_thread(befunde, offen[anfang:anfang + TEIL])
            await self._merken(teil)
            schlichte += sum(b.schlicht for b in teil)
            await asyncio.sleep(PAUSE_S)
        if offen:
            logger.info("Umschläge geprüft: %d, davon schlicht %d", len(offen), schlichte)
        if schlichte:
            for melden in self.nach_runde:
                melden()
        return len(offen)

    @staticmethod
    async def _merken(teil: Sequence[Befund]) -> None:
        async with db.einheit():
            await db.execute_many("UPDATE books SET umschlag_schlicht = ?, umschlag_geprueft = ? WHERE id = ?",
                                  [(int(b.schlicht), b.stand, b.id) for b in teil])


umschlagpruefung = Umschlagpruefung()
