"""Der Auftrag "Texte nachbessern" (BF-118): nur auf Wunsch aus dem Leser, nur für die Seite, auf der jemand liest, und die
nächsten (`TEXTERKENNUNG_KI_SEITEN` zusammen), über die Leitstelle (texterkennung/nachbessern.py). Wie alle Aufträge
(einrichtung/auftrag.py) ist er sichtbar, lässt sich anhalten und fortsetzen und geht nach einem Neustart am nächsten offenen
Stück weiter; was er weiß, steht in der Tabelle `texterkennung_nachbessern` und in den Erkennungen selbst.

Je Stück eine Seite, die älteste Bitte zuerst. Das Ergebnis kommt als Fassung mit Herkunft ki in `erkennung.jsonl` und gilt
ab dann; die klassische Fassung bleibt und lässt sich je Seite wieder wählen (`waehlen`). Was eine Nachbesserung hat, wird nie
wieder von selbst nachgebessert. Ist die letzte gewünschte Seite eines Buchs durch, wird das Buch nachgezogen (Volltext, Suche,
Seiten, Codestellen). Eine Seite, die scheitert, bleibt mit Grund liegen; eine neue Bitte für sie versucht es erneut."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.einrichtung.auftrag import ANGEHALTEN, Auftrag, Ruhen
from backend.app.einrichtung.modelle import Teil
from backend.app.einrichtung.zustand import jetzt
from backend.app.services.ki import ki
from backend.app.services.storage import get_original_file
from backend.app.texterkennung import ablage
from backend.app.texterkennung.auftrag import OHNE_ORIGINAL, OHNE_SEITE, nachziehen
from backend.app.texterkennung.modelle import Herkunft
from backend.app.texterkennung.nachbessern import Nachbesserungsfehler, seite_nachbessern

logger = logging.getLogger("buecherfreunde.texterkennung")
TEILE = (("fertig", "Nachgebessert"), ("fehler", "Nicht nachgebessert"))
OHNE_LEITSTELLE = "Keine Leitstelle eingetragen: ohne sie gibt es keine Nachbesserung"


class Seitenwunsch(BaseModel):
    """Wo die Nachbesserung einer Seite steht: wartet (offen) oder gescheitert (mit Grund); fertig steht in den Fassungen."""
    stand: str
    grund: str = ""


class Nachbesserungsantwort(BaseModel):
    """Antwort auf eine Bitte: welche Seiten jetzt nachgebessert werden; ohne Leitstelle mit Grund."""
    bereit: bool
    grund: str = ""
    seiten: list[int]


class Nachbesserung(Auftrag):
    art = "nachbesserung"
    was = "Texte nachbessern"

    def __init__(self) -> None:
        super().__init__()
        self._anstoss = asyncio.Lock()
        self._nachzug: set[asyncio.Task] = set()

    # -- Stand ------------------------------------------------------------------------------------------------------------
    async def zaehlen(self) -> tuple[int, int, list[Teil]]:
        je = {z["stand"]: z["n"] for z in await db.fetch_all("SELECT stand, COUNT(*) AS n FROM texterkennung_nachbessern GROUP BY stand")}
        gesamt = sum(je.values())
        return gesamt, gesamt - je.get("offen", 0), [Teil(schluessel=k, name=n, gesamt=gesamt, fertig=je.get(k, 0)) for k, n in TEILE]

    async def angehalten(self) -> bool:
        z = await self.zeile()
        return z is not None and z["stand"] == "pause" and z["grund"] == ANGEHALTEN

    async def anstossen(self) -> None:
        """Läuft er nicht, ist er nicht von Hand angehalten und gibt es Arbeit: weiter, wo er ruht, sonst ein neuer Lauf."""
        async with self._anstoss:
            if self.laeuft or await self.angehalten():
                return
            if await db.fetch_one("SELECT 1 FROM texterkennung_nachbessern WHERE stand = 'offen' LIMIT 1") is None:
                return
            z = await self.zeile()
            if z is not None and z["stand"] in ("pause", "fehler", "wartet"):
                await self.fortsetzen()
            else:
                await self.beginnen()

    # -- Lauf -------------------------------------------------------------------------------------------------------------
    async def naechstes(self) -> bool:
        z = await db.fetch_one("""SELECT n.book_id, n.seite, b.hash FROM texterkennung_nachbessern n JOIN books b ON b.id = n.book_id
                                  WHERE n.stand = 'offen' ORDER BY n.gewuenscht_am, n.book_id, n.seite LIMIT 1""")
        if z is None:
            return False
        if not ki.bereit:
            raise Ruhen(OHNE_LEITSTELLE)
        stand, grund = await self._nachbessern(z["hash"], z["seite"])
        await db.execute("UPDATE texterkennung_nachbessern SET stand = ?, grund = ? WHERE book_id = ? AND seite = ?",
                         (stand, grund, z["book_id"], z["seite"]))
        await db.commit()
        if stand == "fertig" and not await db.fetch_one("SELECT 1 FROM texterkennung_nachbessern WHERE book_id = ? AND stand = 'offen'",
                                                        (z["book_id"],)):
            await nachziehen(z["book_id"], z["hash"])
        return True

    @staticmethod
    async def _nachbessern(file_hash: str, seite: int) -> tuple[str, str]:
        original = await asyncio.to_thread(get_original_file, file_hash)
        if original is None:
            return "fehler", OHNE_ORIGINAL
        klassisch = await asyncio.to_thread(ablage.fassung, file_hash, seite, "klassisch")
        try:
            e = await seite_nachbessern(original, seite, klassisch)
        except Nachbesserungsfehler as f:
            logger.info("Nachbesserung: Seite %d nicht nachgebessert: %s", seite, f)
            return "fehler", str(f)
        except IndexError:
            return "fehler", OHNE_SEITE
        await asyncio.to_thread(ablage.anhaengen, file_hash, e)
        return "fertig", ""

    # -- Für den Leser ----------------------------------------------------------------------------------------------------
    async def bitten(self, buch: int, file_hash: str, ab: int) -> Nachbesserungsantwort:
        """Die Seite `ab` und die nächsten nachbessern, soweit sie erkannt sind und noch keine Nachbesserung haben (eine
        gescheiterte kommt wieder dran)."""
        if not ki.bereit:
            return Nachbesserungsantwort(bereit=False, grund=OHNE_LEITSTELLE, seiten=[])
        fassungen = await asyncio.to_thread(ablage.fassungen, file_hash)
        seiten = [s for s in range(ab, ab + settings.texterkennung_ki_seiten) if s in fassungen and not fassungen[s].ki]
        for s in seiten:
            await db.execute("""INSERT INTO texterkennung_nachbessern (book_id, seite, stand, grund, gewuenscht_am) VALUES (?, ?, 'offen', '', ?)
                                ON CONFLICT (book_id, seite) DO UPDATE SET stand = 'offen', grund = '', gewuenscht_am = excluded.gewuenscht_am
                                WHERE stand != 'offen'""", (buch, s, jetzt()))
        await db.commit()
        if seiten:
            await self.anstossen()
        return Nachbesserungsantwort(bereit=True, seiten=seiten)

    async def wuensche(self, buch: int, seiten: Iterable[int]) -> dict[int, Seitenwunsch]:
        """Wo die Nachbesserung dieser Seiten steht (nur offene und gescheiterte)."""
        gefragt = list(seiten)
        if not gefragt:
            return {}
        zeilen = await db.fetch_all(f"SELECT seite, stand, grund FROM texterkennung_nachbessern WHERE book_id = ? AND stand != 'fertig' "
                                    f"AND seite IN ({','.join('?' * len(gefragt))})", (buch, *gefragt))
        return {z["seite"]: Seitenwunsch(stand=z["stand"], grund=z["grund"]) for z in zeilen}

    async def waehlen(self, buch: int, file_hash: str, seite: int, gilt: Herkunft) -> bool:
        """Diese Fassung der Seite soll gelten; danach wird das Buch im Hintergrund nachgezogen. False, wenn es sie nicht gibt."""
        stand = (await asyncio.to_thread(ablage.fassungen, file_hash)).get(seite)
        if stand is None or not getattr(stand, gilt):
            return False
        if stand.gilt != gilt:
            await asyncio.to_thread(ablage.waehlen, file_hash, seite, gilt)
            aufgabe = asyncio.create_task(nachziehen(buch, file_hash))
            self._nachzug.add(aufgabe)
            aufgabe.add_done_callback(self._nachzug.discard)
        return True

    async def nachgezogen(self) -> None:
        """Bis das Nachziehen nach einer Wahl durch ist (für Tests und das Herunterfahren)."""
        if self._nachzug:
            await asyncio.gather(*self._nachzug, return_exceptions=True)


nachbesserung = Nachbesserung()
