"""Erkennen (BF-81): der Abgleich sieht in der Kellerwolke neben den Originalen nach Dateien, die nach ihrem Namen zum Buch
gehören (material/zugehoerig.py), etwa vom Nutzer selbst dort abgelegt. Jede wird ein Fund ("als Begleitmaterial nehmen?");
erst ein Ja macht sie zu Material (material/dienst.py), ein Nein lässt sie liegen, und sie kommt nie wieder. Nichts wird
still übernommen, nichts verschoben.

Ein Auftrag im Hintergrund, angestoßen von Hand und sonst im Takt `MATERIAL_ABGLEICH_TAKT_S`; er sieht jeden Ordner mit
Originalen einmal an. Ein Lauf ist in sich vollständig: nach einem Neustart beginnt der nächste von vorn, Funde bleiben."""

from __future__ import annotations

import asyncio
import logging
import posixpath
from collections import defaultdict
from datetime import UTC, datetime

from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.material import zugehoerig
from backend.app.material.modelle import Abgleichstand

logger = logging.getLogger("buecherfreunde.material.erkennen")
OHNE_KELLERWOLKE = "Ohne Kellerwolke gibt es nichts abzugleichen; Material liegt dann im Buchordner"


def passt(name: str, original: str) -> int:
    """Wie lang der Teil des Namens ist, mit dem die Datei zum Original gehört (mit oder ohne die Nummer des Buchs im
    Namen); 0: gar nicht."""
    return max((len(s) for s in (zugehoerig.stamm(original), zugehoerig.stamm_ohne_nummer(original)) if zugehoerig.gehoert_zu(name, s)),
               default=0)


def bestes_buch(name: str, buecher: list[dict]) -> dict | None:
    """Das Buch, zu dem die Datei am deutlichsten gehört: der längste passende Name gewinnt ("Titel [12]" vor "Titel")."""
    laenge, buch = max(((passt(name, b["name"]), b) for b in buecher), key=lambda x: x[0], default=(0, None))
    return buch if laenge else None


class Abgleich:
    def __init__(self) -> None:
        self._wecker = asyncio.Event()
        self._aufgabe: asyncio.Task | None = None
        self.laeuft = False
        self.ordner = self.ordner_gesamt = 0
        self.grund = ""
        self.zuletzt: str | None = None

    def starten(self) -> None:
        self._wecker = asyncio.Event()
        self._aufgabe = asyncio.create_task(self._arbeiten())

    async def stoppen(self) -> None:
        if self._aufgabe is not None:
            self._aufgabe.cancel()
            self._aufgabe = None

    def anstossen(self) -> None:
        self._wecker.set()

    async def stand(self) -> Abgleichstand:
        offen = await db.fetch_one("SELECT COUNT(*) AS n FROM material_fund WHERE stand = 'offen'")
        return Abgleichstand(bereit=wolke.bereit, laeuft=self.laeuft, ordner=self.ordner, ordner_gesamt=self.ordner_gesamt,
                             gefunden=offen["n"], grund=self.grund if wolke.bereit else OHNE_KELLERWOLKE, zuletzt=self.zuletzt)

    async def _arbeiten(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._wecker.wait(), settings.material_abgleich_takt_s)
            except TimeoutError:
                pass
            self._wecker.clear()
            try:
                await self.lauf()
            except asyncio.CancelledError:
                raise
            except Exception:                              # noqa: BLE001 - der Auftrag darf nie still enden
                logger.exception("Abgleich des Begleitmaterials")

    async def lauf(self) -> int:
        """Ein Lauf über alle Ordner mit Originalen; liefert, wie viele Funde neu sind."""
        if not wolke.bereit:
            return 0
        je_ordner: dict[str, list[dict]] = defaultdict(list)
        for z in await db.fetch_all("SELECT b.id, a.name, a.pfad FROM books b JOIN ablage_datei a ON a.hash = b.hash WHERE a.pfad != ''"):
            je_ordner[posixpath.dirname(z["pfad"])].append(z)
        self.laeuft, self.grund, self.ordner, self.ordner_gesamt = True, "", 0, len(je_ordner)
        neu = 0
        try:
            for pfad, buecher in je_ordner.items():
                try:
                    neu += await self._ordner(pfad, buecher)
                except WolkeFehler as f:
                    self.grund = f"{pfad}: {f.meldung}"
                    logger.info("Abgleich von %s: %s", pfad, f.meldung)
                self.ordner += 1
        finally:
            self.laeuft = False
            self.zuletzt = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        if neu:
            logger.info("Abgleich: %d Dateien neben Originalen gefunden", neu)
        return neu

    async def _ordner(self, pfad: str, buecher: list[dict]) -> int:
        ordner = await wolke.ordner(pfad)
        bekannt = {z["k"] for z in await db.fetch_all("""SELECT knoten AS k FROM ablage_datei UNION SELECT knoten FROM buch_material WHERE knoten IS NOT NULL
                                                        UNION SELECT knoten FROM material_fund""")}
        neu = 0
        async for k in wolke.kinder(ordner["id"]):
            if k.get("typ") != "datei" or k.get("haupt_id") or k["id"] in bekannt:
                continue                                   # Ordner, Begleiter (Auszug, Formate, Material) und Bekanntes
            if b := bestes_buch(k["name"], buecher):
                c = await db.execute("INSERT OR IGNORE INTO material_fund (knoten, buch_id, name, groesse, pfad) VALUES (?, ?, ?, ?, ?)",
                                     (k["id"], b["id"], k["name"], k.get("groesse") or 0, k.get("pfad") or f"{pfad}/{k['name']}"))
                neu += c.rowcount
        await db.commit()
        return neu


abgleich = Abgleich()
