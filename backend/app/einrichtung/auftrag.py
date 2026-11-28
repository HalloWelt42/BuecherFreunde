"""Lange Vorgänge der Ersteinrichtung als sichtbare Aufträge (BF-82): Sicherung einspielen, Originale prüfen, Neuaufbau aus der
Kellerwolke, Originale kopieren. Jeder Auftrag arbeitet ein Stück nach dem anderen ab, mit Pause dazwischen (`EINRICHTUNG_ABSTAND_S`), lässt sich
anhalten und fortsetzen und geht nach einem Neustart am nächsten offenen Stück weiter. Wie weit er ist, zählt er aus seiner
eigenen Tabelle (eine Wahrheit); die Zeile in `einrichtung_auftrag` hält nur Stand, Grund, Zeiten und die Wahl beim Start.

Antwortet die Kellerwolke nicht, ruht der Auftrag mit Grund (`pause`) und setzt beim Fortsetzen an derselben Stelle fort."""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod

from backend.app.ablage.wolke import WolkeFehler
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.einrichtung.modelle import Auftragsstand, Teil
from backend.app.einrichtung.zustand import jetzt

logger = logging.getLogger("buecherfreunde.einrichtung.auftrag")
ANGEHALTEN = "Angehalten"                     # Grund einer Pause von Hand


class Ruhen(Exception):
    """Es geht gerade nicht weiter (Gegenstelle weg); der Auftrag ruht mit diesem Grund."""


class Auftrag(ABC):
    art: str
    was: str

    def __init__(self) -> None:
        self._aufgabe: asyncio.Task | None = None

    # -- was jeder Auftrag selbst weiß --------------------------------------------------------------------------------------
    @abstractmethod
    async def zaehlen(self) -> tuple[int, int, list[Teil]]:
        """Gesamt, fertig und die Teile mit eigenem Balken."""

    @abstractmethod
    async def naechstes(self) -> bool:
        """Ein Stück abarbeiten; False, wenn nichts mehr offen ist. Wirft `Ruhen`, wenn es gerade nicht geht."""

    async def vorbereiten(self) -> None:
        """Vor einem neuen Lauf: die Liste der Stücke anlegen."""

    async def danach(self) -> None:
        """Nach dem letzten Stück."""

    def abstand_s(self) -> float:
        """Pause zwischen zwei Stücken."""
        return settings.einrichtung_abstand_s

    # -- gemeinsam ----------------------------------------------------------------------------------------------------------
    async def zeile(self) -> dict | None:
        return await db.fetch_one("SELECT * FROM einrichtung_auftrag WHERE art = ?", (self.art,))

    async def angaben(self) -> dict:
        z = await self.zeile()
        return json.loads(z["angaben"]) if z else {}

    async def stand(self) -> Auftragsstand:
        z = await self.zeile()
        gesamt, fertig, teile = await self.zaehlen()
        return Auftragsstand(art=self.art, was=self.was, stand=z["stand"] if z else "", gesamt=gesamt, fertig=fertig, teile=teile,
                             grund=z["grund"] if z else "", begonnen=z["begonnen"] if z else None, geaendert=z["geaendert"] if z else None,
                             fertig_am=z["fertig_am"] if z else None)

    async def _setzen(self, stand: str, grund: str = "", fertig: bool = False) -> None:
        await db.execute("UPDATE einrichtung_auftrag SET stand = ?, grund = ?, geaendert = ?, fertig_am = ? WHERE art = ?",
                         (stand, grund, jetzt(), jetzt() if fertig else None, self.art))
        await db.commit()

    async def beginnen(self, **angaben) -> Auftragsstand:
        """Ein neuer Lauf von vorn; läuft schon einer, bleibt es bei ihm."""
        if self.laeuft:
            return await self.stand()
        await db.execute("INSERT INTO einrichtung_auftrag(art, stand, angaben, begonnen, geaendert) VALUES (?, 'wartet', ?, ?, ?) "
                         "ON CONFLICT(art) DO UPDATE SET stand = 'wartet', angaben = excluded.angaben, grund = '', begonnen = excluded.begonnen, "
                         "geaendert = excluded.geaendert, fertig_am = NULL", (self.art, json.dumps(angaben), jetzt(), jetzt()))
        await db.commit()
        await self.vorbereiten()
        self._starten()
        return await self.stand()

    async def pause(self) -> Auftragsstand:
        z = await self.zeile()
        if z and z["stand"] in ("wartet", "laeuft"):
            await self._setzen("pause", ANGEHALTEN)
        return await self.stand()

    async def fortsetzen(self) -> Auftragsstand:
        z = await self.zeile()
        if z and z["stand"] in ("pause", "fehler", "wartet"):
            await self._setzen("wartet")
            self._starten()
        return await self.stand()

    async def nach_neustart(self) -> None:
        z = await self.zeile()
        if z and z["stand"] in ("wartet", "laeuft"):
            self._starten()

    @property
    def laeuft(self) -> bool:
        return self._aufgabe is not None and not self._aufgabe.done()

    def _starten(self) -> None:
        if not self.laeuft:
            self._aufgabe = asyncio.create_task(self._laufen())

    async def warten(self) -> None:
        """Bis der laufende Lauf endet (für Tests und das Ende des Kopierens)."""
        if self._aufgabe is not None:
            await asyncio.gather(self._aufgabe, return_exceptions=True)

    async def stoppen(self) -> None:
        if self._aufgabe is not None:
            self._aufgabe.cancel()
            await asyncio.gather(self._aufgabe, return_exceptions=True)
            self._aufgabe = None

    async def _laufen(self) -> None:
        try:
            await self._setzen("laeuft")
            while True:
                z = await self.zeile()
                if z is None or z["stand"] == "pause":
                    return
                if not await self.naechstes():
                    break
                await asyncio.sleep(self.abstand_s())
            await self.danach()
            await self._setzen("fertig", fertig=True)
        except asyncio.CancelledError:
            raise
        except (Ruhen, WolkeFehler) as f:
            await self._setzen("pause", getattr(f, "meldung", None) or str(f))
        except Exception as f:                              # noqa: BLE001 - der Auftrag endet nie still
            logger.exception("Auftrag %s", self.was)
            await self._setzen("fehler", f"{type(f).__name__}: {f}")


def auftraege() -> dict[str, Auftrag]:
    from backend.app.einrichtung.kopieren import kopieren
    from backend.app.einrichtung.ligaturen import ligaturen
    from backend.app.einrichtung.neuaufbau import neuaufbau
    from backend.app.einrichtung.pruefung import pruefung
    from backend.app.einrichtung.wiederherstellen import einspielen
    from backend.app.texterkennung.auftrag import texterkennung
    from backend.app.texterkennung.nachbesserung import nachbesserung
    from backend.app.vorlesen.proben import stimmproben

    return {a.art: a for a in (einspielen, pruefung, neuaufbau, kopieren, ligaturen, stimmproben, texterkennung, nachbesserung)}


async def stand_von(art: str) -> Auftragsstand:
    return await auftraege()[art].stand()
