"""Lesbares Begleitmaterial in die Suche (BF-81): ein Auftrag im Hintergrund liest den Text jeder Datei, deren Text noch offen
ist (PDF, EPUB, Text, Markdown; material/arten.json), im eigenen Prozess wie beim Aufnehmen, und legt ihn je Seite in den
Suchindex (`suche.material_text`, core/suchindex.py). Der Stand steht in `buch_material.text_stand`: nach einem Neustart geht
es mit dem weiter, was offen ist, und fehlt der Text im Index (neue Suchdatei), wird er wieder gelesen."""

from __future__ import annotations

import asyncio
import logging

from backend.app.annahme import auswertung
from backend.app.core.database import db
from backend.app.core.suchindex import SUCHTEXT_ZEICHEN
from backend.app.material import ablage
from backend.app.material.modelle import Textlauf as Textstand

logger = logging.getLogger("buecherfreunde.material.text")
TAKT_S = 600                                   # so oft sieht der Auftrag von selbst nach, auch ohne Anstoß


def seiten(text: str) -> list[tuple[int | None, str]]:
    """Der Text je Seite (ein PDF trennt Seiten durch einen Seitenvorschub), zusammen höchstens SUCHTEXT_ZEICHEN Zeichen;
    leere Seiten fallen weg. Ohne Seiten eine Zeile ohne Nummer."""
    teile = text.split("\f")
    aus, platz = [], SUCHTEXT_ZEICHEN
    for nr, t in enumerate(teile, 1):
        if platz <= 0:
            break
        if t.strip():
            aus.append((nr if len(teile) > 1 else None, t[:platz]))
            platz -= len(t)
    return aus


class Lauf:
    def __init__(self) -> None:
        self._wecker = asyncio.Event()
        self._aufgabe: asyncio.Task | None = None
        self.laeuft = False

    def starten(self) -> None:
        self._wecker = asyncio.Event()
        self._wecker.set()
        self._aufgabe = asyncio.create_task(self._arbeiten())

    async def stoppen(self) -> None:
        if self._aufgabe is not None:
            self._aufgabe.cancel()
            self._aufgabe = None

    def anstossen(self) -> None:
        self._wecker.set()

    async def stand(self) -> Textstand:
        z = {r["text_stand"]: r["n"] for r in await db.fetch_all("SELECT text_stand, COUNT(*) AS n FROM buch_material GROUP BY text_stand")}
        return Textstand(offen=z.get("offen", 0), fertig=z.get("fertig", 0), ohne=z.get("ohne", 0), fehler=z.get("fehler", 0), laeuft=self.laeuft)

    async def _arbeiten(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._wecker.wait(), TAKT_S)
            except TimeoutError:
                pass
            self._wecker.clear()
            try:
                await self.runde()
            except asyncio.CancelledError:
                raise
            except Exception:                              # noqa: BLE001 - der Auftrag darf nie still enden
                logger.exception("Text des Begleitmaterials")

    async def runde(self) -> int:
        """Alles Offene, eins nach dem anderen; liefert, wie viele gelesen wurden."""
        gelesen = 0
        self.laeuft = True
        try:
            while z := await db.fetch_one("SELECT * FROM buch_material WHERE text_stand = 'offen' ORDER BY angelegt_am, id LIMIT 1"):
                await self.lesen(z)
                gelesen += 1
        finally:
            self.laeuft = False
        return gelesen

    @staticmethod
    async def lesen(z: dict) -> None:
        try:
            async with ablage.von(z).lokal(z) as pfad:
                e = await auswertung.text(pfad)
        except Exception as f:                             # noqa: BLE001 - eine Datei darf die übrigen nie aufhalten
            logger.info("Text von Material %s nicht gelesen: %s", z["id"], f)
            await db.execute("UPDATE buch_material SET text_stand = 'fehler', text_grund = ? WHERE id = ?", (str(f)[:300] or type(f).__name__, z["id"]))
            await db.commit()
            return
        teile = seiten(e.fulltext) if e.lesbar else []
        async with db.einheit():
            if await db.fetch_one("SELECT 1 AS da FROM buch_material WHERE id = ?", (z["id"],)) is None:
                return                                     # inzwischen entfernt: kein Text ohne Material
            await db.execute("DELETE FROM material_text WHERE material = ?", (z["id"],))
            await db.execute_many("INSERT INTO material_text (material, buch_id, seite, inhalt) VALUES (?, ?, ?, ?)",
                                  [(z["id"], z["buch_id"], s, t) for s, t in teile])
            await db.execute("UPDATE buch_material SET text_stand = ?, text_seiten = ?, text_grund = ? WHERE id = ?",
                             ("fertig" if teile else "ohne", len(teile), e.grund, z["id"]))


textlauf = Lauf()
