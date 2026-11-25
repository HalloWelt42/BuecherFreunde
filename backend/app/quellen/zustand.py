"""Der gemerkte Stand je Quelle: letzter Erfolg, letzter Fehler, Pausen, Anfragen heute. Er übersteht einen Neustart, und aus
ihm antworten die Einstellungen, ohne die Quelle zu fragen."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel

from backend.app.core.database import db
from backend.app.quellen.fehler import Pausiert, Tagesgrenze
from backend.app.quellen.regeln import Regel
from backend.app.quellen.vorrang import Vorrang

RUECKZUG_S = 30.0               # erste Pause nach 429/503 ohne Angabe, verdoppelt sich
ABGEWIESEN_S = 3600.0           # erste Pause nach 403
SICHERUNG_AB = 4                # so viele Ausfälle hintereinander, dann fragt niemand mehr
SICHERUNG_S = 600.0             # erste Pause der Sicherung, verdoppelt sich
PAUSE_HOECHSTENS_S = 6 * 3600.0
VORGABE_HOECHSTENS_S = 24 * 3600.0


class Quellenzustand(BaseModel):
    quelle: str
    erfolg_am: float | None = None
    fehler_am: float | None = None
    fehler: str = ""
    ausfaelle: int = 0                 # hintereinander
    stufe: int = 0                     # wie oft hintereinander schon pausiert wurde
    pause_bis: float | None = None
    pause_grund: str = ""
    geprueft_am: float | None = None
    tag: str = ""
    anfragen: int = 0                  # heute insgesamt
    hintergrund: int = 0               # heute in Hintergrundläufen


SPALTEN = tuple(Quellenzustand.model_fields)


def uhrzeit(zeit: float, jetzt: float) -> str:
    z, j = datetime.fromtimestamp(zeit), datetime.fromtimestamp(jetzt)
    return f"{z:%H:%M}" if z.date() == j.date() else f"{z:%d.%m. %H:%M}"


class Zustaende:
    def __init__(self, uhr: Callable[[], float] = time.time) -> None:
        self._uhr = uhr
        self._da: dict[str, Quellenzustand] = {}

    async def von(self, quelle: str) -> Quellenzustand:
        if quelle not in self._da:
            z = await db.fetch_one("SELECT * FROM quelle_stand WHERE quelle = ?", (quelle,))
            self._da.setdefault(quelle, Quellenzustand(**z) if z else Quellenzustand(quelle=quelle))
        return self._heutig(self._da[quelle])

    def _heutig(self, z: Quellenzustand) -> Quellenzustand:
        tag = f"{datetime.fromtimestamp(self._uhr()):%Y-%m-%d}"
        if z.tag != tag:
            z.tag, z.anfragen, z.hintergrund = tag, 0, 0
        return z

    async def _sichern(self, z: Quellenzustand) -> None:
        await db.execute(f"INSERT OR REPLACE INTO quelle_stand({', '.join(SPALTEN)}) VALUES ({', '.join('?' * len(SPALTEN))})", tuple(z.model_dump().values()))
        await db.commit()

    async def darf(self, regel: Regel, vorrang: Vorrang, probe: bool = False) -> None:
        """Wirft, wenn gerade nicht gefragt werden darf. Eine Probe von Hand darf an der Sicherung vorbei, an einer
        Bitte der Quelle um Ruhe nicht."""
        z = await self.von(regel.kennung)
        jetzt = self._uhr()
        sicherung = z.ausfaelle >= SICHERUNG_AB
        if z.pause_bis and z.pause_bis > jetzt and not (probe and sicherung):
            raise Pausiert(f"{regel.name} macht Pause bis {uhrzeit(z.pause_bis, jetzt)}: {z.pause_grund}", z.pause_bis)
        if vorrang is Vorrang.HINTERGRUND and z.hintergrund >= regel.tagesgrenze:
            raise Tagesgrenze(f"{regel.name}: für heute genug gefragt ({regel.tagesgrenze}), morgen geht es weiter")

    async def gefragt(self, regel: Regel, vorrang: Vorrang, probe: bool = False) -> None:
        z = await self.von(regel.kennung)
        z.anfragen += 1
        z.hintergrund += int(vorrang is Vorrang.HINTERGRUND)
        if probe:
            z.geprueft_am = self._uhr()
        await self._sichern(z)

    async def erfolg(self, regel: Regel) -> None:
        z = await self.von(regel.kennung)
        z.erfolg_am, z.ausfaelle, z.stufe, z.pause_bis, z.pause_grund = self._uhr(), 0, 0, None, ""
        await self._sichern(z)

    async def bitte_warten(self, regel: Regel, grund: str, vorgabe_s: float | None, erste_s: float = RUECKZUG_S) -> Pausiert:
        """Die Quelle bat um Ruhe (429, 503, 403): mindestens so lange wie verlangt, mit jedem Mal länger."""
        z = await self.von(regel.kennung)
        pause = max(min(vorgabe_s or 0.0, VORGABE_HOECHSTENS_S), min(erste_s * 2 ** z.stufe, PAUSE_HOECHSTENS_S))
        return await self._pausieren(regel, z, pause, grund)

    async def ausfall(self, regel: Regel, grund: str) -> Pausiert | None:
        """Ein Ausfall; nach mehreren hintereinander greift die Sicherung."""
        z = await self.von(regel.kennung)
        z.ausfaelle += 1
        if z.ausfaelle >= SICHERUNG_AB:
            return await self._pausieren(regel, z, min(SICHERUNG_S * 2 ** z.stufe, PAUSE_HOECHSTENS_S), f"mehrmals ausgefallen, zuletzt: {grund}")
        z.fehler_am, z.fehler = self._uhr(), grund
        await self._sichern(z)
        return None

    async def _pausieren(self, regel: Regel, z: Quellenzustand, pause_s: float, grund: str) -> Pausiert:
        jetzt = self._uhr()
        z.stufe += 1
        z.fehler_am, z.fehler, z.pause_bis, z.pause_grund = jetzt, grund, jetzt + pause_s, grund
        await self._sichern(z)
        return Pausiert(f"{regel.name} macht Pause bis {uhrzeit(z.pause_bis, jetzt)}: {grund}", z.pause_bis)
