"""Der Auftrag "Volltexte mit falschen Ligaturen neu lesen" (BF-104): gespeicherte Volltexte von PDF, die noch mit falsch
abgebildeten Ligaturen gewonnen wurden ("Funk?on" statt "Funktion", services/pdfseite.py), werden aus dem Original neu
gelesen; Seiten und Suchindex ziehen nach.

Je PDF-Buch ein Stück (Tabelle `ligatur_befund`): betroffen ist ein Volltext, in dem ein Fehlzeichen mitten im Wort zwischen
zwei Buchstaben steht; ein einzelnes Zeichen (etwa ein Formelzeichen) zählt nicht. Je Aufruf werden bis zu PRUEFEN_JE_STUECK
Volltexte durchgesehen und höchstens ein betroffener neu gelesen, mit demselben Leser wie beim Aufnehmen (eigener Prozess).
Gelöscht wird nichts, was nicht neu gewonnen ist: fehlt das Original oder lässt es sich nicht lesen, bleibt der alte Volltext
und das Stück steht mit Grund im Bericht. Wie alle Aufträge (auftrag.py) lässt er sich anhalten, fortsetzen und geht nach einem
Neustart weiter; gestartet wird er von Hand (POST /api/einrichtung/ligaturen)."""

from __future__ import annotations

import asyncio

from backend.app.annahme import auswertung
from backend.app.core.database import db
from backend.app.core.suchindex import SUCHTEXT_ZEICHEN
from backend.app.einrichtung.auftrag import Auftrag
from backend.app.einrichtung.modelle import Teil
from backend.app.services.pdfseite import fehlzeichen_im_wort
from backend.app.services.seiten import BEGLEITER
from backend.app.services.storage import get_original_file, get_sidecar_path, load_fulltext, save_fulltext

PRUEFEN_JE_STUECK = 50          # so viele Volltexte sieht ein Aufruf höchstens durch, bevor er Pause macht
TEILE = (("neu", "Neu gelesen"), ("heil", "Ohne falsche Ligaturen"), ("ohne", "Original nicht zu holen, alter Text bleibt"),
         ("fehler", "Nicht lesbar, alter Text bleibt"))
OHNE_ORIGINAL = "Das Original ist gerade nicht zu holen; der alte Volltext bleibt"
NICHT_LESBAR = "Das Original ließ sich nicht lesen; der alte Volltext bleibt"


class Ligaturen(Auftrag):
    art = "ligaturen"
    was = "Volltexte mit falschen Ligaturen neu lesen"

    async def zaehlen(self) -> tuple[int, int, list[Teil]]:
        je = {z["stand"]: z["n"] for z in await db.fetch_all("SELECT stand, COUNT(*) AS n FROM ligatur_befund GROUP BY stand")}
        gesamt = sum(je.values())
        return gesamt, gesamt - je.get("offen", 0), [Teil(schluessel=k, name=n, gesamt=gesamt, fertig=je.get(k, 0)) for k, n in TEILE]

    async def vorbereiten(self) -> None:
        """Je PDF-Buch ein offenes Stück; der Bericht des letzten Laufs fällt weg (die Bücher und Texte bleiben)."""
        await db.execute("DELETE FROM ligatur_befund")
        await db.execute("INSERT INTO ligatur_befund(book_id) SELECT id FROM books WHERE lower(COALESCE(file_format, '')) = 'pdf'")
        await db.commit()

    async def naechstes(self) -> bool:
        offen = await db.fetch_all("SELECT f.book_id, b.hash FROM ligatur_befund f JOIN books b ON b.id = f.book_id "
                                   "WHERE f.stand = 'offen' ORDER BY f.book_id LIMIT ?", (PRUEFEN_JE_STUECK,))
        if not offen:
            return False
        for z in offen:
            text = await asyncio.to_thread(load_fulltext, z["hash"]) or ""
            gefunden = await asyncio.to_thread(fehlzeichen_im_wort, text)
            if not gefunden:
                await self._vermerken(z["book_id"], "heil")
                continue
            stand, grund = await self._neu_lesen(z["book_id"], z["hash"])
            await self._vermerken(z["book_id"], stand, grund, gefunden)
            break                                          # ein Buch neu lesen ist ein Stück; danach Pause
        return True

    async def _neu_lesen(self, buch: int, file_hash: str) -> tuple[str, str]:
        original = await asyncio.to_thread(get_original_file, file_hash)        # kann aus der Kellerwolke laden
        if original is None:
            return "ohne", OHNE_ORIGINAL
        e = await auswertung.text(original)                                     # derselbe Leser wie beim Aufnehmen
        if not e.lesbar or not e.fulltext.strip():
            return "fehler", e.grund or NICHT_LESBAR
        await asyncio.to_thread(save_fulltext, file_hash, e.fulltext)
        await asyncio.to_thread(get_sidecar_path(file_hash, BEGLEITER).unlink, True)   # die Seiten ergeben sich neu
        async with db.einheit():                           # über fts_content in den Suchindex (Trigger), dann wieder leer
            await db.execute("UPDATE books SET fts_content = ?, updated_at = datetime('now') WHERE id = ?",
                             (e.fulltext[:SUCHTEXT_ZEICHEN], buch))
            await db.execute("UPDATE books SET fts_content = '' WHERE id = ?", (buch,))
        rest = fehlzeichen_im_wort(e.fulltext)
        return "neu", f"Noch {rest} Zeichen in einer Schrift, die keine Fehlschrift ist" if rest else ""

    @staticmethod
    async def _vermerken(buch: int, stand: str, grund: str = "", zeichen: int = 0) -> None:
        await db.execute("UPDATE ligatur_befund SET stand = ?, text = ?, zeichen = ?, geaendert_am = strftime('%Y-%m-%dT%H:%M:%SZ', "
                         "'now') WHERE book_id = ?", (stand, grund, zeichen, buch))
        await db.commit()


ligaturen = Ligaturen()
