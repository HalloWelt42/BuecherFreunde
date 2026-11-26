"""Der Auftrag "Ansagen erstellen" (BF-78): spricht je eingebauter Stimme vorab, was fehlt (familie/ansagen.py, `bedarf`), mit
dem Sprechdienst über `services/vorlesen.satz` im Hintergrund (Vorrang "hintergrund"). Angestoßen nach der Wahl einer Stimme,
nach einer Freigabe, dem Namen der Katze, einem neuen Profil oder Titel; beim Start und im Takt (`ANSAGEN_TAKT_S`) sieht er
selbst nach. Was fertig ist, liegt als Datei; nach einem Neustart geht es mit dem weiter, was noch fehlt.

Der Stand je Stimme steht in `ansage_auftrag` (wartet, laeuft, fertig, fehler, mit Zahlen und Zeiten). Alte Töne einer Stimme
räumt er erst weg, wenn die neuen fertig sind; die Probe bleibt. Eine Stimme, die niemand mehr hört, verliert ihre Töne."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.familie import ansagen
from backend.app.familie.ansagen import Eintrag
from backend.app.familie.modelle import Ansagestand
from backend.app.services import vorlesen

logger = logging.getLogger("buecherfreunde.familie.ansagen")
JETZT = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
OHNE_DIENST = "Es ist kein Sprechdienst angeschlossen (Leitstelle)"


def ablegen(datei: Path, ton: bytes) -> None:
    """Erst fertig bekommt die Datei ihren Namen; eine halbe gibt es nie."""
    datei.parent.mkdir(parents=True, exist_ok=True)
    teil = datei.with_name(f".{datei.name}.teil")
    teil.write_bytes(ton)
    os.replace(teil, datei)


def _aufraeumen(ort: Path, behalten: set[str]) -> int:
    if not ort.is_dir():
        return 0
    weg = [d for d in ort.glob("*.wav") if d.name not in behalten] + list(ort.glob(".*.teil"))
    for d in weg:
        d.unlink(missing_ok=True)
    return len(weg)


async def staende(stimme: str | None = None) -> list[Ansagestand]:
    bedingung, werte = ("WHERE stimme = ?", (stimme,)) if stimme else ("", ())
    return [Ansagestand(**z) for z in await db.fetch_all(f"SELECT stimme, stand, gesamt, fertig, grund, begonnen, geaendert, fertig_am "
                                                         f"FROM ansage_auftrag {bedingung} ORDER BY stimme", werte)]


async def laeuft(stimme: str) -> bool:
    z = await db.fetch_one("SELECT stand FROM ansage_auftrag WHERE stimme = ?", (stimme,))
    return bool(z and z["stand"] == "laeuft")


async def _stand(stimme: str, stand: str, gesamt: int, fertig: int, grund: str = "") -> None:
    """Der Stand der Stimme. `begonnen` bleibt, solange gesprochen wird, auch über einen Fehler und einen Neustart hinweg;
    `fertig_am` setzt das Ende."""
    alt = next(iter(await staende(stimme)), None)
    weiter = alt is not None and alt.stand in ("laeuft", "fehler") and alt.begonnen
    begonnen = (alt.begonnen if weiter else None) if stand in ("laeuft", "fehler") else (alt.begonnen if alt else None)
    await db.execute(f"""INSERT INTO ansage_auftrag (stimme, stand, gesamt, fertig, grund, begonnen, geaendert, fertig_am)
                         VALUES (?, ?, ?, ?, ?, COALESCE(?, CASE WHEN ? = 'laeuft' THEN {JETZT} END), {JETZT},
                                 CASE WHEN ? = 'fertig' THEN {JETZT} ELSE ? END)
                         ON CONFLICT(stimme) DO UPDATE SET stand = excluded.stand, gesamt = excluded.gesamt, fertig = excluded.fertig,
                           grund = excluded.grund, begonnen = excluded.begonnen, geaendert = excluded.geaendert,
                           fertig_am = excluded.fertig_am""",
                     (stimme, stand, gesamt, fertig, grund, begonnen, stand, stand, alt.fertig_am if alt else None))


class Ansagelauf:
    def __init__(self) -> None:
        self._anstoss = asyncio.Event()
        self._aufgabe: asyncio.Task | None = None

    def starten(self) -> None:
        if self._aufgabe is None or self._aufgabe.done():
            self._aufgabe = asyncio.create_task(self._schleife())
        self._anstoss.set()

    def anstossen(self) -> None:
        self._anstoss.set()

    async def stoppen(self) -> None:
        if self._aufgabe is not None:
            self._aufgabe.cancel()
            await asyncio.gather(self._aufgabe, return_exceptions=True)
            self._aufgabe = None

    async def _schleife(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._anstoss.wait(), settings.ansagen_takt_s)
            except TimeoutError:
                pass
            self._anstoss.clear()
            try:
                await self.runde()
            except Exception:                                    # noqa: BLE001 - der Auftrag darf nie still enden
                logger.exception("Ansagen erstellen")

    async def runde(self) -> None:
        """Je Stimme, was fehlt; danach die Töne von Stimmen, die niemand mehr hört."""
        bedarf = await ansagen.bedarf()
        for stimme, eintraege in bedarf.items():
            await self._stimme(stimme, eintraege)
        for alt in await staende():
            if alt.stimme not in bedarf:
                _aufraeumen(ansagen.pfad(alt.stimme), {ansagen.probe().datei})
                await db.execute("DELETE FROM ansage_auftrag WHERE stimme = ?", (alt.stimme,))

    async def _stimme(self, stimme: str, eintraege: list[Eintrag]) -> None:
        ort = ansagen.pfad(stimme)
        fehlen = [e for e in eintraege if not (ort / e.datei).exists()]
        gesamt, fertig = len(eintraege), len(eintraege) - len(fehlen)
        if fehlen and not vorlesen.bereit():
            await _stand(stimme, "fehler", gesamt, fertig, OHNE_DIENST)
            return
        if fehlen:
            await _stand(stimme, "laeuft", gesamt, fertig)
            logger.info("Ansagen erstellen für %s: %d fehlen", stimme, len(fehlen))
        for e in fehlen:
            try:
                ton = await vorlesen.satz(e.text, stimme, prioritaet="hintergrund")
            except vorlesen.VorlesenFehler as f:
                await _stand(stimme, "fehler", gesamt, fertig, f.meldung)
                return
            await asyncio.to_thread(ablegen, ort / e.datei, ton)
            fertig += 1
            await _stand(stimme, "laeuft", gesamt, fertig)
        weg = await asyncio.to_thread(_aufraeumen, ort, {e.datei for e in eintraege} | {ansagen.probe().datei})
        alt = next(iter(await staende(stimme)), None)
        if fehlen or weg or alt is None or (alt.stand, alt.gesamt, alt.fertig) != ("fertig", gesamt, fertig):
            await _stand(stimme, "fertig", gesamt, fertig)


ansagelauf = Ansagelauf()
