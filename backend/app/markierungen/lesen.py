"""Der Auftrag "Markierungen lesen" (BF-123): der Text eines Rechtecks auf einer gescannten Seite (texterkennung/ausschnitt.py).

Gelesen wird schon, wenn jemand das Rechteck zieht, noch bevor er markiert: das Menü daran zeigt den Text nach wenigen Sekunden.
Wird daraus eine Markierung, hängt die Lesung an ihr (`verknuepfen`), und ihr Text wird der Text der Markierung, sobald er da ist.
Eine Markierung über einen Bereich bekommt immer eine Lesung (`fuer_markierung`), auch ohne Menü (Markierstift). "Erneut lesen"
setzt die Lesung der Markierung zurück. Scheitert das Lesen, bleibt der Grund stehen und der Text der klassischen Erkennung wird
als Notbehelf Text der Markierung, damit Suche und Vorlesen etwas haben.

Wie alle Aufträge (einrichtung/auftrag.py) ist er sichtbar, lässt sich anhalten und fortsetzen und macht nach einem Neustart weiter;
was er weiß, steht in der Tabelle `markierung_lesen`. Je Stück eine Lesung, die älteste zuerst. Lesungen, aus denen keine
Markierung wurde, sind nach `LOSE_STUNDEN` vergessen: sie gehören niemandem, nur dem Menü, das sie zeigte."""

from __future__ import annotations

import asyncio
import logging

from pydantic import BaseModel

from backend.app.core.database import db
from backend.app.einrichtung.auftrag import ANGEHALTEN, Auftrag
from backend.app.einrichtung.modelle import Teil
from backend.app.einrichtung.zustand import jetzt
from backend.app.markierungen.stelle import bereich_aus
from backend.app.services.ki import ki
from backend.app.services.storage import get_original_file
from backend.app.texterkennung import ablage
from backend.app.texterkennung.ausschnitt import OHNE_TEXT, Ausschnittsfehler, klassischer_text, lies, im_bereich
from backend.app.texterkennung.auftrag import OHNE_ORIGINAL, OHNE_SEITE
from backend.app.texterkennung.nachbessern import seitenrahmen

logger = logging.getLogger("buecherfreunde.markierungen")
TEILE = (("fertig", "Gelesen"), ("fehler", "Nicht gelesen"))
OHNE_LEITSTELLE = "Keine Leitstelle eingetragen: ohne sie liest nur die klassische Erkennung"
LOSE_STUNDEN = 24


class Lesestand(BaseModel):
    """Wo das Lesen eines Bereichs steht: offen (wird gelesen), fertig (mit Text, leer: dort steht keiner) oder fehler (mit Grund)."""
    id: int
    stand: str
    text: str = ""
    grund: str = ""


def _stand(z) -> Lesestand:
    return Lesestand(id=z["id"], stand=z["stand"], text=z["text"], grund=z["grund"])


class Markierungslesen(Auftrag):
    art = "markierungslesen"
    was = "Markierungen lesen"

    def __init__(self) -> None:
        super().__init__()
        self._anstoss = asyncio.Lock()

    # -- Stand ------------------------------------------------------------------------------------------------------------
    async def zaehlen(self) -> tuple[int, int, list[Teil]]:
        je = {z["stand"]: z["n"] for z in await db.fetch_all("SELECT stand, COUNT(*) AS n FROM markierung_lesen GROUP BY stand")}
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
            if await db.fetch_one("SELECT 1 FROM markierung_lesen WHERE stand = 'offen' LIMIT 1") is None:
                return
            z = await self.zeile()
            if z is not None and z["stand"] in ("pause", "fehler", "wartet"):
                await self.fortsetzen()
            else:
                await self.beginnen()

    # -- Lauf -------------------------------------------------------------------------------------------------------------
    async def naechstes(self) -> bool:
        z = await db.fetch_one("""SELECT l.id, l.stelle, l.markierung, b.hash FROM markierung_lesen l JOIN books b ON b.id = l.book_id
                                  WHERE l.stand = 'offen' ORDER BY l.gewuenscht_am, l.id LIMIT 1""")
        if z is None:
            return False
        stand, text, grund = await self._lesen(z["hash"], z["stelle"])
        # Wurde die Lesung inzwischen neu gewünscht (Erneut lesen), zählt dieses Ergebnis nicht mehr
        if await db.fetch_one("SELECT 1 FROM markierung_lesen WHERE id = ? AND stand = 'offen'", (z["id"],)) is None:
            return True
        await db.execute("UPDATE markierung_lesen SET stand = ?, text = ?, grund = ?, gelesen_am = ? WHERE id = ?",
                         (stand, text, grund, jetzt(), z["id"]))
        verknuepft = (await db.fetch_one("SELECT markierung FROM markierung_lesen WHERE id = ?", (z["id"],)))["markierung"]
        if verknuepft is not None and (text or stand == "fertig"):
            await db.execute("UPDATE book_highlights SET text_snippet = ? WHERE id = ?", (text, verknuepft))
        await db.commit()
        return True

    @staticmethod
    async def _lesen(file_hash: str, stelle: str) -> tuple[str, str, str]:
        ort = bereich_aus(stelle)
        if ort is None:
            return "fehler", "", "Die Stelle nennt kein Rechteck"
        seite, bereich = ort
        original = await asyncio.to_thread(get_original_file, file_hash)
        if original is None:
            return "fehler", "", OHNE_ORIGINAL
        klassisch = await asyncio.to_thread(ablage.fassung, file_hash, seite, "klassisch")
        if not ki.bereit:
            try:
                rahmen = await asyncio.to_thread(seitenrahmen, original, seite)
            except IndexError:
                return "fehler", "", OHNE_SEITE
            return "fehler", klassischer_text(im_bereich(klassisch, bereich.in_punkten(rahmen))) if klassisch else "", OHNE_LEITSTELLE
        try:
            text = await lies(original, seite, bereich, klassisch)
        except Ausschnittsfehler as f:
            logger.info("Markierung lesen: Seite %d nicht gelesen: %s", seite, f)
            return "fehler", f.notbehelf, str(f)
        except IndexError:
            return "fehler", "", OHNE_SEITE
        return "fertig", text, "" if text else OHNE_TEXT

    # -- Für den Leser ----------------------------------------------------------------------------------------------------
    async def beginnen_fuer(self, profil: str, buch: int, stelle: str) -> Lesestand:
        """Das Rechteck lesen, für das Menü daran; ValueError, wenn die Stelle kein Rechteck nennt."""
        if bereich_aus(stelle) is None:
            raise ValueError("Die Stelle nennt kein Rechteck")
        await db.execute(f"DELETE FROM markierung_lesen WHERE markierung IS NULL AND gewuenscht_am < "
                         f"strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-{LOSE_STUNDEN} hours')")
        cursor = await db.execute("INSERT INTO markierung_lesen (profil_id, book_id, stelle, gewuenscht_am) VALUES (?, ?, ?, ?)",
                                  (profil, buch, stelle, jetzt()))
        await db.commit()
        await self.anstossen()
        return await self.lesestand(profil, cursor.lastrowid)

    async def lesestand(self, profil: str, lesung: int) -> Lesestand | None:
        z = await db.fetch_one("SELECT * FROM markierung_lesen WHERE id = ? AND profil_id = ?", (lesung, profil))
        return _stand(z) if z else None

    async def fuer_markierung(self, profil: str, markierung: int, lesung: int | None) -> Lesestand | None:
        """Die neue Markierung über einen Bereich bekommt ihre Lesung: die aus dem Menü, wenn sie zu ihr passt, sonst eine neue.
        Ist der Text schon da, wird er gleich ihr Text. None, wenn die Markierung kein Rechteck nennt."""
        m = await db.fetch_one("SELECT book_id, cfi_range FROM book_highlights WHERE id = ? AND profil_id = ?", (markierung, profil))
        if m is None or bereich_aus(m["cfi_range"]) is None:
            return None
        z = None
        if lesung is not None:
            z = await db.fetch_one("SELECT * FROM markierung_lesen WHERE id = ? AND profil_id = ? AND book_id = ? AND stelle = ? "
                                   "AND markierung IS NULL", (lesung, profil, m["book_id"], m["cfi_range"]))
        if z is None:
            cursor = await db.execute("INSERT INTO markierung_lesen (profil_id, book_id, stelle, markierung, gewuenscht_am) VALUES (?, ?, ?, ?, ?)",
                                      (profil, m["book_id"], m["cfi_range"], markierung, jetzt()))
            z = await db.fetch_one("SELECT * FROM markierung_lesen WHERE id = ?", (cursor.lastrowid,))
        else:
            await db.execute("UPDATE markierung_lesen SET markierung = ? WHERE id = ?", (markierung, z["id"]))
            if z["stand"] != "offen" and z["text"]:
                await db.execute("UPDATE book_highlights SET text_snippet = ? WHERE id = ?", (z["text"], markierung))
        await db.commit()
        await self.anstossen()
        return _stand(z)

    async def erneut(self, profil: str, markierung: int) -> Lesestand | None:
        """Die Markierung noch einmal lesen; None, wenn sie keinen Bereich hat oder es sie nicht gibt."""
        z = await db.fetch_one("SELECT l.id FROM markierung_lesen l JOIN book_highlights h ON h.id = l.markierung "
                               "WHERE l.markierung = ? AND h.profil_id = ?", (markierung, profil))
        if z is None:
            return await self.fuer_markierung(profil, markierung, None)
        await db.execute("UPDATE markierung_lesen SET stand = 'offen', grund = '', gewuenscht_am = ? WHERE id = ?", (jetzt(), z["id"]))
        await db.commit()
        await self.anstossen()
        return await self.lesestand(profil, z["id"])

    async def von_markierung(self, profil: str, markierung: int) -> Lesestand | None:
        z = await db.fetch_one("SELECT * FROM markierung_lesen WHERE profil_id = ? AND markierung = ?", (profil, markierung))
        return _stand(z) if z else None

    async def je_markierung(self, profil: str, buch: int) -> dict[int, Lesestand]:
        """Wo das Lesen der Markierungen eines Buchs steht, je Markierung mit Bereich."""
        zeilen = await db.fetch_all("SELECT * FROM markierung_lesen WHERE profil_id = ? AND book_id = ? AND markierung IS NOT NULL",
                                    (profil, buch))
        return {z["markierung"]: _stand(z) for z in zeilen}


markierungslesen = Markierungslesen()
