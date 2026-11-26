"""Der Auftrag "Lücken nachschlagen" (BF-75): fragt je Sammlung und Sprache einmal einen Katalog nach der Reihe (quellen/reihen.py),
mit Vorrang Hintergrund (Tagesgrenze der Quelle), mit `LUECKEN_ABSTAND_S` Pause zwischen zwei Abfragen und über den Vorrat des
gemeinsamen Abrufs. Die Antwort bringt die Zahl der Bände und die Angaben je Band; danach wird diese Sammlung in dieser Sprache
nie wieder von selbst gefragt, auch nicht nach einem Fehler (dann steht der Grund da, "Neu nachschlagen" fragt auf Wunsch).

Macht eine Quelle Pause oder ist ihre Tagesgrenze erreicht, endet die Runde und das Offene bleibt offen (es wurde ja nichts
gefragt); ebenso, solange für eine Sprache kein Katalog eingeschaltet ist. Angestoßen beim Start, wenn jemand die Lücken einer
Sammlung ansieht oder ihre Platzhalter einschaltet, und im Takt `LUECKEN_TAKT_S`; nach einem Neustart geht es mit dem Offenen
weiter. Gefragt werden nur Sammlungen mit Platzhaltern und nur Sprachen, in denen ein Band eine Nummer hat."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from backend.app.core.config import settings
from backend.app.luecken import speicher
from backend.app.luecken.dienst import abkuerzung, haeufigster_autor, reihenname
from backend.app.luecken.modelle import Nachschlagestand
from backend.app.luecken.rechnen import aus_den_quellen
from backend.app.luecken.sprachen import hauptsprache, sprachname
from backend.app.quellen import reihen
from backend.app.quellen.fehler import QuelleFehler, ruhig
from backend.app.quellen.reihen import Reihenfrage
from backend.app.quellen.vorrang import hintergrund

logger = logging.getLogger("buecherfreunde.luecken")


def _jetzt() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Nachschlagen:
    def __init__(self) -> None:
        self._anstoss = asyncio.Event()
        self._aufgabe: asyncio.Task | None = None
        self.laeuft = False
        self.gesamt = self.fertig = 0
        self.aktuell = self.grund = ""
        self.begonnen: str | None = None
        self.geaendert: str | None = None
        self.fertig_am: str | None = None

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

    async def stand(self) -> Nachschlagestand:
        offen = len(await speicher.offene_paare())
        art = "laeuft" if self.laeuft else "ruht" if offen and self.grund else "wartet" if offen else "fertig"
        return Nachschlagestand(stand=art, gesamt=self.gesamt, fertig=self.fertig, offen=offen, aktuell=self.aktuell if self.laeuft else "",
                                grund=self.grund, begonnen=self.begonnen, geaendert=self.geaendert, fertig_am=self.fertig_am)

    async def _schleife(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._anstoss.wait(), settings.luecken_takt_s)
            except TimeoutError:
                pass
            self._anstoss.clear()
            try:
                await self.runde()
            except asyncio.CancelledError:
                raise
            except Exception:                              # noqa: BLE001 - der Auftrag darf nie still enden
                logger.exception("Lücken nachschlagen")
                self.laeuft = False

    async def runde(self) -> int:
        """Alles Offene der Reihe nach; liefert, wie viele gefragt wurden."""
        await speicher.abkuerzungen_neu_fragen(abkuerzung)
        offen = await speicher.offene_paare()
        if not offen:
            self.grund = ""
            return 0
        self.laeuft, self.gesamt, self.fertig, self.grund = True, len(offen), 0, ""
        self.begonnen = self.geaendert = _jetzt()
        gefragt = 0
        try:
            for i, (sammlung_id, sprache) in enumerate(offen):
                weiter, frage = await self._paar(sammlung_id, sprache)
                gefragt += frage
                self.fertig += frage                                      # beantwortet oder gescheitert, nicht übersprungen
                self.geaendert = _jetzt()
                if not weiter:
                    break
                if frage and i + 1 < len(offen):
                    await asyncio.sleep(settings.luecken_abstand_s)       # Abstand nur nach einer echten Abfrage
        finally:
            self.laeuft = False
        if not self.grund:
            self.fertig_am = _jetzt()
        return gefragt

    async def _paar(self, sammlung_id: int, sprache: str) -> tuple[bool, int]:
        """Eine Sammlung in einer Sprache: (weiter, ob gefragt wurde). Nicht weiter heißt: die Quellen ruhen gerade."""
        try:
            sammlung = await speicher.sammlung(sammlung_id)
        except speicher.SammlungFehlt:
            return True, 0
        katalog = reihen.fuer_sprache(sprache)
        if katalog is None:
            self.grund = f"{reihen.katalogname(sprache)} ist abgeschaltet"
            return True, 0
        baende = await speicher.buchbaende(sammlung_id)
        haupt = hauptsprache(b.sprache for b in baende)
        oeffentlich = [b for b in baende if not b.privat]                  # was jemand privat hat, geht nie an eine Quelle
        eigene = [b for b in speicher.je_sprache(baende, haupt).get(sprache, []) if not b.privat]
        frage = Reihenfrage(reihe=reihenname(eigene, sammlung["name"]), autor=haeufigster_autor(eigene) or haeufigster_autor(oeffentlich),
                            sprache=sprache)
        self.aktuell = f"{sammlung['name']}, {sprachname(sprache)}"
        try:
            with hintergrund():
                funde = await katalog.reihe(frage)
        except QuelleFehler as f:
            if ruhig(f):
                self.grund = f.grund
                return False, 0
            await speicher.gescheitert(sammlung_id, sprache, katalog.regel.kennung, frage.reihe, f.grund)
            logger.info("Lücken von %s nachschlagen: %s", self.aktuell, f.grund)
            return True, 1
        await speicher.nachgeschlagen(sammlung_id, sprache, katalog.regel.kennung, frage.reihe, aus_den_quellen(funde))
        return True, 1


nachschlagen = Nachschlagen()
