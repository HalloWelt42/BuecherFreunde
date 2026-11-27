"""Der Auftrag "Ansagen erstellen" (BF-78, BF-14): spricht je gewählter Stimme vorab, was fehlt (familie/ansagen.py, `bedarf`),
über die Vertonung (`vorlesen/sprechen.ton`), eine Ansage nach der anderen. Angestoßen nach der Wahl einer Stimme, nach einer
Freigabe, dem Namen der Katze, einem neuen Profil oder Titel; beim Start und im Takt (`ANSAGEN_TAKT_S`) sieht er selbst nach.
Was fertig ist, liegt als Datei; nach einem Neustart geht es mit dem weiter, was noch fehlt.

Der Stand je Stimme steht in `ansage_auftrag` (wartet, laeuft, fertig, fehler, mit Zahlen und Zeiten). Wechselt ein Hörer die
Stimme, entstehen seine Ansagen in der neuen neu; bis sie ganz sind, bleiben die Töne der bisherigen (`ansage_hoerer`) und gelten
weiter. Alte Töne räumt er erst weg, wenn niemand sie mehr braucht. Die Probe ist eine Stimmprobe (vorlesen/proben.py)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from appkern.vorlesen import VorlesenFehler

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.familie import ansagen
from backend.app.familie.ansagen import Eintrag
from backend.app.familie.modelle import Ansagestand
from backend.app.vorlesen import sprechen, tonablage, zugang
from backend.app.vorlesen.modelle import vertont

logger = logging.getLogger("buecherfreunde.familie.ansagen")
JETZT = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"


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
        """Je Stimme, was fehlt; dann merkt sich jeder Hörer, welche Stimme er ganz hat; zuletzt fallen Töne weg, die niemand
        mehr braucht."""
        hoerende = await ansagen.je_hoerer()
        bedarf = ansagen.bedarf(hoerende)
        for stimme, eintraege in bedarf.items():
            await self._stimme(stimme, eintraege)
        schutz = await _hoerer_nachfuehren(hoerende)
        for stimme, dateien in schutz.items():
            # erst, wenn eine Stimme ganz ist, gehen ihre alten Töne; die bisherige eines Hörers behält, was er noch hört
            if stimme not in bedarf or ansagen.ganz(stimme, bedarf[stimme]):
                await asyncio.to_thread(_aufraeumen, ansagen.pfad(stimme), dateien)
        for alt in await staende():
            if alt.stimme not in bedarf and alt.stimme not in schutz:
                await asyncio.to_thread(_aufraeumen, ansagen.pfad(alt.stimme), set())
                await db.execute("DELETE FROM ansage_auftrag WHERE stimme = ?", (alt.stimme,))

    async def _stimme(self, stimme: str, eintraege: list[Eintrag]) -> None:
        ort = ansagen.pfad(stimme)
        fehlen = [e for e in eintraege if not (ort / e.datei).exists()]
        gesamt, fertig = len(eintraege), len(eintraege) - len(fehlen)
        if fehlen and not zugang.bereit():
            await _stand(stimme, "fehler", gesamt, fertig, zugang.NICHT_EINGERICHTET if not zugang.adresse() else zugang.OHNE_ZUGANG)
            return
        if fehlen:
            await _stand(stimme, "laeuft", gesamt, fertig)
            logger.info("Ansagen erstellen für %s: %d fehlen", stimme, len(fehlen))
        for e in fehlen:
            try:
                ton = await sprechen.ton(e.text, stimme)
            except VorlesenFehler as f:
                await _stand(stimme, "fehler", gesamt, fertig, f.meldung)
                return
            await asyncio.to_thread(tonablage.ablegen, ort / e.datei, ton)
            fertig += 1
            await _stand(stimme, "laeuft", gesamt, fertig)
        alt = next(iter(await staende(stimme)), None)
        if fehlen or alt is None or (alt.stand, alt.gesamt, alt.fertig) != ("fertig", gesamt, fertig):
            await _stand(stimme, "fertig", gesamt, fertig)


async def _hoerer_nachfuehren(hoerende: dict[str, tuple[str, list[Eintrag]]]) -> dict[str, set[str]]:
    """Wer seine Stimme ganz hat, merkt sie sich; wer die Stimme gewechselt hat und die neue noch nicht ganz hat, behält die
    Töne der bisherigen. Antwort: je Stimme die Dateien, die bleiben müssen (alles, was ein Hörer gerade mit ihr hört)."""
    bisher = await ansagen.zuletzt_alle()
    schutz: dict[str, set[str]] = {}
    for wer, (stimme, eintraege) in hoerende.items():
        ganz = vertont(stimme) and ansagen.ganz(stimme, eintraege)
        if ganz or not vertont(stimme):                      # ganz da, oder das Gerät spricht selbst: nichts mehr zu überbrücken
            gilt = stimme if ganz else ""
            if bisher.get(wer, "") != gilt:
                await db.execute("INSERT INTO ansage_hoerer (hoerer, stimme) VALUES (?, ?) ON CONFLICT(hoerer) DO UPDATE SET stimme = excluded.stimme",
                                 (wer, gilt))
            if ganz:
                schutz.setdefault(stimme, set()).update(e.datei for e in eintraege)
        else:
            schutz.setdefault(stimme, set()).update(e.datei for e in eintraege)
            if vorher := bisher.get(wer, ""):
                schutz.setdefault(vorher, set()).update(e.datei for e in eintraege)
    for wer in set(bisher) - set(hoerende):                  # ein Profil, das es nicht mehr gibt
        await db.execute("DELETE FROM ansage_hoerer WHERE hoerer = ?", (wer,))
    return schutz


ansagelauf = Ansagelauf()
