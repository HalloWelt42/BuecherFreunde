"""Läufe des Katalogs im Hintergrund (BF-69): Einordnen (katalog/einordnen.py) und Entwurf aus dem Bestand
(katalog/bestandslauf.py). Ihr Stand steht in `katalog_lauf` und übersteht einen Neustart: ein laufender Lauf geht danach
am letzten fertigen Stapel weiter (`nach_neustart`).

Die KI fragt ein Lauf nur über die Leitstelle (services/ki.py), im Hintergrund und mit Geduld, mit einer Pause zwischen
zwei Anfragen (`KATALOG_ABSTAND_S`). Pausieren hält ihn sofort an, auch mitten in einer Anfrage; was der angefangene
Stapel bis dahin gefunden hat, verfällt und wird beim Fortsetzen neu gesucht."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, ClassVar

from appkern.leitstelle.arbeit import LAUFENDE_ARBEIT
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.katalog.modelle import Laufart, Laufstand, Laufzustand
from backend.app.services.anhalten import Anhalter
from backend.app.services.ki import Ki

logger = logging.getLogger("buecherfreunde.katalog")
JETZT = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
ZAEHLER = frozenset({"stapel", "regeln", "ki", "ohne_vorschlag"})
FELDER = ZAEHLER | {"stapel_gesamt", "stapel_groesse", "nach_buch", "schritt", "grund"}


class Laufzeile(BaseModel):
    id: int
    art: Laufart
    stand: Laufzustand
    stapel: int
    stapel_gesamt: int
    stapel_groesse: int
    nach_buch: int
    regeln: int
    ki: int
    ohne_vorschlag: int
    schritt: str
    grund: str

    def laufstand(self) -> Laufstand:
        return Laufstand(laeuft=self.stand == "laeuft", pause=self.stand == "pause", stand=self.stand, stapel=self.stapel,
                         stapel_gesamt=self.stapel_gesamt, stapel_groesse=self.stapel_groesse, regeln=self.regeln, ki=self.ki,
                         ohne_vorschlag=self.ohne_vorschlag, schritt=self.schritt if self.stand == "laeuft" else "", grund=self.grund)


async def anlegen(art: Laufart, stapel_groesse: int = 0) -> int:
    c = await db.execute("INSERT INTO katalog_lauf (art, stand, stapel_groesse) VALUES (?, 'laeuft', ?)", (art, stapel_groesse))
    return c.lastrowid


async def lesen(nr: int) -> Laufzeile:
    z = await db.fetch_one("SELECT * FROM katalog_lauf WHERE id = ?", (nr,))
    if z is None:
        raise LookupError(f"Lauf {nr} fehlt")
    return Laufzeile(**z)


async def juengster(art: Laufart) -> Laufzeile | None:
    z = await db.fetch_one("SELECT * FROM katalog_lauf WHERE art = ? ORDER BY id DESC LIMIT 1", (art,))
    return Laufzeile(**z) if z else None


async def setzen(nr: int, **werte: Any) -> None:
    """Felder setzen; die Namen kommen nur aus dem Code (`FELDER`)."""
    assert set(werte) <= FELDER, set(werte) - FELDER
    if werte:
        await db.execute(f"UPDATE katalog_lauf SET {', '.join(f'{k} = ?' for k in werte)}, geaendert = {JETZT} WHERE id = ?",
                         (*werte.values(), nr))


async def zaehlen(nr: int, **dazu: int) -> None:
    """Zähler um so viel erhöhen."""
    assert set(dazu) <= ZAEHLER, set(dazu) - ZAEHLER
    await db.execute(f"UPDATE katalog_lauf SET {', '.join(f'{k} = {k} + ?' for k in dazu)}, geaendert = {JETZT} WHERE id = ?",
                     (*dazu.values(), nr))


async def wechseln(nr: int, stand: Laufzustand, grund: str | None = None, *, aus: tuple[Laufzustand, ...]) -> bool:
    """In einen anderen Zustand, nur aus einem der genannten; ob es gelang. Ohne `grund` bleibt der bisherige."""
    neu = "" if grund is None else ", grund = ?"
    c = await db.execute(f"UPDATE katalog_lauf SET stand = ?{neu}, geaendert = {JETZT} WHERE id = ? AND stand IN ({','.join('?' * len(aus))})",
                         (stand, *(() if grund is None else (grund,)), nr, *aus))
    return c.rowcount > 0


class Angehalten(Exception):
    pass


class Hintergrundlauf:
    """Ein Lauf als Aufgabe im Hintergrund; was er tut, steht in `arbeiten`."""

    art: ClassVar[Laufart]
    kennung: ClassVar[str]                                 # Vorsilbe der Arbeit in der Leitstelle

    def __init__(self, ki: Ki) -> None:
        self.ki = ki
        self._anhalter = Anhalter()
        self._aufgabe: asyncio.Task | None = None
        self._gefragt = 0

    # -- Leben -----------------------------------------------------------------------------------------------------------
    async def stand(self) -> Laufstand:
        z = await juengster(self.art)
        return z.laufstand() if z else Laufstand()

    async def nach_neustart(self) -> None:
        """Ein Lauf, der beim Beenden lief, geht weiter."""
        z = await juengster(self.art)
        if z is not None and z.stand == "laeuft":
            logger.info("Katalog: Lauf %d (%s) geht nach dem Neustart weiter", z.id, self.art)
            await self._starten(z.id)

    async def stoppen(self) -> None:
        """Beim Beenden der App: anhalten, der Stand bleibt (ein laufender Lauf geht nach dem Neustart weiter)."""
        self._anhalter.halte()
        if self._aufgabe is not None:
            self._aufgabe.cancel()
            await asyncio.wait({self._aufgabe})
            self._aufgabe = None

    async def warten(self) -> None:
        """Bis die laufende Aufgabe zu Ende ist."""
        if self._aufgabe is not None:
            await asyncio.wait({self._aufgabe})

    async def _starten(self, nr: int) -> None:
        if self._aufgabe is not None and not self._aufgabe.done():
            self._anhalter.halte()
            await asyncio.wait({self._aufgabe})
        self._anhalter.beginne()
        self._gefragt = 0
        self._aufgabe = asyncio.create_task(self._im_hintergrund(nr))

    def _halten(self) -> None:
        self._anhalter.halte()

    async def _im_hintergrund(self, nr: int) -> None:
        marke = LAUFENDE_ARBEIT.set(f"{self.kennung}-{uuid.uuid4().hex[:12]}")
        try:
            await self.arbeiten(nr)
        except Angehalten:
            pass
        except asyncio.CancelledError:
            raise
        except Exception:                                  # noqa: BLE001 - ein Fehler endet den Lauf mit Grund, nie still
            logger.exception("Katalog: Lauf %d", nr)
            await wechseln(nr, "fehler", "Der Lauf ist mit einem Fehler abgebrochen", aus=("laeuft",))
        finally:
            LAUFENDE_ARBEIT.reset(marke)

    async def arbeiten(self, nr: int) -> None:
        raise NotImplementedError

    # -- Hilfen für die Arbeit -------------------------------------------------------------------------------------------
    def weiter_oder_halt(self) -> None:
        if self._anhalter.gehalten:
            raise Angehalten

    async def frage(self, system: str, nutzer: str, schema_name: str, schema: dict, *, titel: str, max_tokens: int) -> object:
        """Eine Anfrage an die KI; vor jeder außer der ersten eine Pause. Wirft KiFehler, oder Angehalten beim Pausieren."""
        if self._gefragt:
            await self._anhalter.bis(asyncio.sleep(settings.katalog_abstand_s))
            self.weiter_oder_halt()
        self._gefragt += 1
        roh = await self._anhalter.bis(self.ki.json_antwort(system, nutzer, schema_name, schema, titel=titel, prioritaet="hintergrund",
                                                            geduld=True, pruefen=self._pruefen, temperature=0.1, max_tokens=max_tokens))
        self.weiter_oder_halt()
        return roh

    async def _pruefen(self) -> None:
        self.weiter_oder_halt()
