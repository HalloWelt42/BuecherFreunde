"""Der Auftrag "Texte erkennen" (BF-109): Seiten eines Scans ohne lesbaren Text werden klassisch erkannt (erkennen.py) und als
Zeile in `erkennung.jsonl` abgelegt (ablage.py). Wie alle Aufträge (einrichtung/auftrag.py) ist er sichtbar, lässt sich anhalten
und fortsetzen und geht nach einem Neustart am nächsten offenen Stück weiter; was er weiß, steht in seinen Tabellen
(einrichtung/schema.py) und in den Erkennungen selbst.

Je Stück, in dieser Folge:
1. Vorrang (`vorrang`, aus dem Leser): die Seite, auf der jemand liest, und `TEXTERKENNUNG_VORRANG_SEITEN` danach, die jüngste
   Bitte zuerst und ohne Pause; ein Buch, das noch nicht durchgesehen ist, wird dafür zuerst durchgesehen.
2. Durchsehen: je PDF-Buch einmal (Tabelle `texterkennung_buch`). Erst der gespeicherte Volltext (je Stück bis zu
   DURCHSEHEN_JE_STUECK): ist das Buch danach kein Scan, ist es durchgesehen, ohne das Original zu holen. Sonst das Original
   (höchstens eines je Stück): welche Seiten keinen lesbaren Text tragen und ob es ein Scan ist (beides texterkennung/
   textschicht.py). Je Seite ohne Text eines Scans ein Stück (Tabelle `texterkennung_seite`); was schon eine Erkennung hat,
   zählt als erkannt.
3. Nachziehen: ein Buch, dessen Seiten alle durch sind, das aber noch nicht nachgezogen ist (etwa nach einem Neustart genau
   dazwischen).
4. Buch für Buch die übrigen Seiten, das zuletzt gelesene Buch zuerst.

Ist ein Buch ganz erkannt, entstehen Volltext, Suchindex und Seiten neu, die Codestellen werden neu erkannt, eine fehlende
Seitenzahl wird gefüllt; der geänderte Auszug geht nachts in die Kellerwolke (services/pflege.py). Eine Seite, die scheitert
(Frist, Abbruch, ein Seitenbild, das sich nicht rendern lässt), bleibt mit Grund liegen und kommt im nächsten Lauf wieder dran;
ebenso ein Buch, dessen Original gerade nicht zu holen ist oder das sich nicht nachziehen ließ. Antwortet die Kellerwolke nicht,
ruht der Auftrag.

Ohne Programm (oder ohne Sprachdaten) wird weiter durchgesehen; Seiten erkennt der Auftrag dann nicht, er ruht mit Grund. Die
Wache (`erkennungswache`) sieht beim Start nach einer Weile (`TEXTERKENNUNG_ERST_S`) und im Takt (`TEXTERKENNUNG_TAKT_S`) nach
und stößt ihn an, wenn es Arbeit gibt; von Hand angehalten bleibt er angehalten."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from pydantic import BaseModel

from backend.app.ablage.wolke import WolkeFehler
from backend.app.codestellen.dienst import codestellen
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.core.suchindex import SUCHTEXT_ZEICHEN
from backend.app.einrichtung.auftrag import ANGEHALTEN, Auftrag, Ruhen
from backend.app.einrichtung.modelle import Teil
from backend.app.einrichtung.zustand import jetzt
from backend.app.services.seiten import BEGLEITER as SEITEN_BEGLEITER, SEITENTRENNER, pdf_seitentexte, pdf_volltext
from backend.app.services.storage import get_original_file, get_sidecar_path, load_fulltext, save_fulltext
from backend.app.texterkennung import ablage, erkennen, werkzeug
from backend.app.texterkennung.textschicht import ist_scan, ohne_lesbaren_text, traegt_text

logger = logging.getLogger("buecherfreunde.texterkennung")
DURCHSEHEN_JE_STUECK = 50       # so viele gespeicherte Volltexte sieht ein Stück höchstens durch, bevor es Pause macht
TEILE = (("erkannt", "Erkannt"), ("leer", "Ohne lesbaren Text"), ("fehler", "Nicht erkannt"))
BUECHER = ("buecher", "Bücher durchgesehen")
OHNE_ORIGINAL = "Das Original ist gerade nicht zu holen"
NICHT_LESBAR = "Das Original ließ sich nicht lesen"
OHNE_SEITE = "Die Seite gibt es in der Datei nicht"
NICHT_NACHGEZOGEN = "Volltext und Suche ließen sich nicht nachziehen"
PDF = "lower(COALESCE(b.file_format, '')) = 'pdf'"
# ein Scan, dessen Seiten alle durch sind und von denen eine Text trägt, der aber noch nicht nachgezogen ist (Tabelle t)
NACHZUZIEHEN = """t.scan = 1 AND t.grund = '' AND t.fertig_am IS NULL
    AND NOT EXISTS (SELECT 1 FROM texterkennung_seite s WHERE s.book_id = t.book_id AND s.stand = 'offen')
    AND EXISTS (SELECT 1 FROM texterkennung_seite s WHERE s.book_id = t.book_id AND s.stand = 'erkannt')"""


class Vorrangstand(BaseModel):
    """Antwort auf eine Bitte um Vorrang: ist die Erkennung bereit (sonst warum nicht), und welche der Seiten `von` bis `bis`
    noch auf ihre Erkennung warten."""
    bereit: bool
    grund: str = ""
    von: int
    bis: int
    wartet: list[int]


class Befund(BaseModel):
    """Was das Durchsehen eines Buchs ergibt."""
    seiten: int
    ohne_text: list[int]
    scan: bool


def befund_aus(texte: list[str]) -> Befund:
    """Die Seiten ohne lesbaren Text und ob das Buch ein Scan ist, aus dem schlichten Text je Seite."""
    ohne = [nr for nr, t in enumerate(texte, start=1) if ohne_lesbaren_text(t)]
    return Befund(seiten=len(texte), ohne_text=ohne, scan=ist_scan(len(ohne), len(texte)))


def befund_laut_volltext(file_hash: str, seitenzahl: int | None) -> Befund | None:
    """Der Befund aus dem gespeicherten Volltext, wenn er je Seite geteilt ist; sonst None (dann zählt das Original). Der
    Volltext trägt mindestens den Text der Textschicht; ist das Buch laut ihm kein Scan, ist es auch laut Original keiner."""
    text = load_fulltext(file_hash)
    if not text or (SEITENTRENNER not in text and seitenzahl != 1):
        return None
    return befund_aus(text.split(SEITENTRENNER))


async def nachziehen(buch: int, file_hash: str) -> bool:
    """Volltext, Seiten und Suchindex neu aus der Textschicht (mit den geltenden Erkennungen), eine fehlende Seitenzahl gefüllt,
    Codestellen neu erkennen; nach der Erkennung eines Buchs und nach jeder Nachbesserung oder Wahl einer Fassung (BF-118). False,
    wenn es nicht ging (das Original fehlt, es ließ sich nicht lesen); antwortet die Kellerwolke nicht, kommt WolkeFehler."""
    try:
        original = await asyncio.to_thread(get_original_file, file_hash)
        if original is None:
            raise FileNotFoundError(OHNE_ORIGINAL)
        text = await asyncio.to_thread(pdf_volltext, original, await asyncio.to_thread(ablage.lesen, file_hash))
    except WolkeFehler:
        raise
    except Exception as f:                              # noqa: BLE001 - ein Buch hält die übrigen nie auf
        logger.warning("Texterkennung: Buch %d nicht nachgezogen: %s", buch, f)
        return False
    await asyncio.to_thread(save_fulltext, file_hash, text)
    await asyncio.to_thread(get_sidecar_path(file_hash, SEITEN_BEGLEITER).unlink, True)   # die gedruckten Seiten neu
    async with db.einheit():                           # über fts_content in den Suchindex (Trigger), dann wieder leer
        await db.execute("UPDATE books SET fts_content = ?, page_count = CASE WHEN COALESCE(page_count, 0) = 0 THEN ? "
                         "ELSE page_count END, updated_at = datetime('now') WHERE id = ?",
                         (text[:SUCHTEXT_ZEICHEN], text.count(SEITENTRENNER) + 1, buch))
        await db.execute("UPDATE books SET fts_content = '' WHERE id = ?", (buch,))
    codestellen.vormerken(buch)
    logger.info("Texterkennung: Buch %d nachgezogen, Volltext, Suche und Seiten neu", buch)
    return True


class Texterkennung(Auftrag):
    art = "texterkennung"
    was = "Texte erkennen"

    def __init__(self) -> None:
        super().__init__()
        self._eilig = False                     # das letzte Stück hatte Vorrang: das nächste ohne Pause
        self._anstoss = asyncio.Lock()          # Wache und Leser stoßen zugleich an: ein Lauf

    def abstand_s(self) -> float:
        return 0.0 if self._eilig else settings.texterkennung_abstand_s

    # -- Stand ------------------------------------------------------------------------------------------------------------
    async def zaehlen(self) -> tuple[int, int, list[Teil]]:
        je = {z["stand"]: z["n"] for z in await db.fetch_all("SELECT stand, COUNT(*) AS n FROM texterkennung_seite GROUP BY stand")}
        gesamt = sum(je.values())
        buecher = await db.fetch_one(f"SELECT COUNT(*) AS n FROM books b WHERE {PDF}")
        gesehen = await db.fetch_one(f"SELECT COUNT(*) AS n FROM texterkennung_buch t JOIN books b ON b.id = t.book_id "
                                     f"WHERE t.grund = '' AND {PDF}")
        teile = [Teil(schluessel=BUECHER[0], name=BUECHER[1], gesamt=buecher["n"], fertig=gesehen["n"])]
        teile += [Teil(schluessel=k, name=n, gesamt=gesamt, fertig=je.get(k, 0)) for k, n in TEILE]
        return gesamt, gesamt - je.get("offen", 0), teile

    async def angehalten(self) -> bool:
        z = await self.zeile()
        return z is not None and z["stand"] == "pause" and z["grund"] == ANGEHALTEN

    async def arbeit_da(self) -> bool:
        """Gibt es etwas zu tun: ein Buch, das noch nicht durchgesehen oder nachgezogen ist, eine offene Seite, eine Bitte um
        Vorrang?"""
        return await db.fetch_one(
            f"""SELECT 1 FROM books b LEFT JOIN texterkennung_buch t ON t.book_id = b.id WHERE t.book_id IS NULL AND {PDF}
                UNION ALL SELECT 1 FROM texterkennung_seite WHERE stand = 'offen'
                UNION ALL SELECT 1 FROM texterkennung_buch t WHERE {NACHZUZIEHEN}
                UNION ALL SELECT 1 FROM texterkennung_vorrang LIMIT 1""") is not None

    async def anstossen(self) -> None:
        """Läuft er nicht, ist er nicht von Hand angehalten und gibt es Arbeit: weiter, wo er ruht, sonst ein neuer Lauf."""
        async with self._anstoss:
            if self.laeuft or await self.angehalten() or not await self.arbeit_da():
                return
            z = await self.zeile()
            if z is not None and z["stand"] in ("pause", "fehler", "wartet"):
                await self.fortsetzen()
            else:
                await self.beginnen()

    # -- Lauf -------------------------------------------------------------------------------------------------------------
    async def vorbereiten(self) -> None:
        """Ein neuer Lauf: was beim letzten scheiterte, kommt wieder dran (Seiten mit Fehler, Bücher, die sich nicht durchsehen
        ließen); was erkannt ist, bleibt."""
        await db.execute("UPDATE texterkennung_seite SET stand = 'offen', grund = '' WHERE stand = 'fehler'")
        await db.execute("DELETE FROM texterkennung_buch WHERE grund != ''")
        await db.commit()

    async def naechstes(self) -> bool:
        self._eilig = False
        stand = await werkzeug.bereitschaft()
        if stand.bereit and await self._vorrang():
            self._eilig = True
            return True
        if await self._durchsehen() or await self._nachziehen():
            return True
        offen = await db.fetch_one(
            """SELECT s.book_id, s.seite FROM texterkennung_seite s JOIN texterkennung_buch t ON t.book_id = s.book_id
               WHERE s.stand = 'offen' ORDER BY t.vorrang_am IS NULL, t.vorrang_am DESC, s.book_id, s.seite LIMIT 1""")
        if offen is None:
            return False
        if not stand.bereit:
            raise Ruhen(stand.grund)
        await self._erkennen(offen["book_id"], offen["seite"])
        return True

    async def _vorrang(self) -> bool:
        """Ein Stück für die jüngste Bitte um Vorrang; erledigte Bitten fallen weg."""
        for v in await db.fetch_all("SELECT book_id, von, bis FROM texterkennung_vorrang ORDER BY seit DESC"):
            befund = await db.fetch_one("SELECT scan, grund FROM texterkennung_buch WHERE book_id = ?", (v["book_id"],))
            if befund is None:
                z = await db.fetch_one("SELECT hash FROM books WHERE id = ?", (v["book_id"],))
                if z is not None:
                    await self._buch_durchsehen(v["book_id"], z["hash"])
                    return True
            elif befund["scan"] and not befund["grund"]:
                seite = await db.fetch_one("SELECT seite FROM texterkennung_seite WHERE book_id = ? AND stand = 'offen' AND seite "
                                           "BETWEEN ? AND ? ORDER BY seite LIMIT 1", (v["book_id"], v["von"], v["bis"]))
                if seite is not None:
                    await self._erkennen(v["book_id"], seite["seite"])
                    return True
            await db.execute("DELETE FROM texterkennung_vorrang WHERE book_id = ?", (v["book_id"],))
            await db.commit()
        return False

    async def _durchsehen(self) -> bool:
        """Bücher, die noch nicht durchgesehen sind: erst ihr Volltext, höchstens ein Original je Stück."""
        zeilen = await db.fetch_all(f"""SELECT b.id, b.hash, b.page_count FROM books b LEFT JOIN texterkennung_buch t ON t.book_id = b.id
                                        WHERE t.book_id IS NULL AND {PDF} ORDER BY b.id LIMIT ?""", (DURCHSEHEN_JE_STUECK,))
        if not zeilen:
            return False
        for z in zeilen:
            befund = await asyncio.to_thread(befund_laut_volltext, z["hash"], z["page_count"])
            if befund is not None and not befund.scan:
                await self._befund_merken(z["id"], befund)
                continue
            await self._buch_durchsehen(z["id"], z["hash"])
            break
        return True

    async def _buch_durchsehen(self, buch: int, file_hash: str) -> None:
        """Das Original eines Buchs durchsehen; je Seite ohne Text eines Scans ein Stück."""
        original = await asyncio.to_thread(get_original_file, file_hash)        # kann aus der Kellerwolke laden
        if original is None:
            await self._befund_merken(buch, None, OHNE_ORIGINAL)
            return
        try:
            befund = befund_aus(await asyncio.to_thread(pdf_seitentexte, original))
        except Exception as f:                              # noqa: BLE001 - eine kaputte Datei hält die übrigen nie auf
            logger.info("Texterkennung: Buch %d nicht lesbar: %s", buch, f)
            await self._befund_merken(buch, None, NICHT_LESBAR)
            return
        await self._befund_merken(buch, befund)
        if not befund.scan:
            return
        vorhanden = await asyncio.to_thread(ablage.lesen, file_hash)
        for nr in befund.ohne_text:
            e = vorhanden.get(nr)
            stand = "offen" if e is None else "erkannt" if traegt_text(e) else "leer"
            await db.execute("INSERT OR IGNORE INTO texterkennung_seite(book_id, seite, stand) VALUES (?, ?, ?)", (buch, nr, stand))
        await db.commit()
        logger.info("Texterkennung: Buch %d ist ein Scan, %d von %d Seiten ohne Text", buch, len(befund.ohne_text), befund.seiten)
        if vorhanden:
            await self._vielleicht_fertig(buch, file_hash)

    @staticmethod
    async def _befund_merken(buch: int, befund: Befund | None, grund: str = "") -> None:
        """Der Befund eines Buchs; wartet schon eine Bitte um Vorrang, kommt das Buch danach als erstes dran."""
        await db.execute(
            """INSERT INTO texterkennung_buch(book_id, seiten, ohne_text, scan, grund, geprueft_am, vorrang_am)
               VALUES (?, ?, ?, ?, ?, ?, (SELECT seit FROM texterkennung_vorrang WHERE book_id = ?))
               ON CONFLICT(book_id) DO UPDATE SET seiten = excluded.seiten, ohne_text = excluded.ohne_text, scan = excluded.scan,
               grund = excluded.grund, geprueft_am = excluded.geprueft_am,
               vorrang_am = COALESCE(excluded.vorrang_am, texterkennung_buch.vorrang_am)""",
            (buch, befund.seiten if befund else 0, len(befund.ohne_text) if befund else 0, int(bool(befund and befund.scan)), grund,
             jetzt(), buch))
        await db.commit()

    async def _nachziehen(self) -> bool:
        """Ein Buch, dessen Seiten alle durch sind und von denen eine Text trägt, das aber noch nicht nachgezogen ist."""
        z = await db.fetch_one(f"SELECT t.book_id, b.hash FROM texterkennung_buch t JOIN books b ON b.id = t.book_id "
                               f"WHERE {NACHZUZIEHEN} LIMIT 1")
        if z is None:
            return False
        await self._buch_fertig(z["book_id"], z["hash"])
        return True

    async def _erkennen(self, buch: int, seite: int) -> None:
        z = await db.fetch_one("SELECT hash FROM books WHERE id = ?", (buch,))
        if z is None:
            return
        original = await asyncio.to_thread(get_original_file, z["hash"])
        if original is None:
            await db.execute("UPDATE texterkennung_seite SET stand = 'fehler', grund = ?, geaendert_am = ? WHERE book_id = ? "
                             "AND stand = 'offen'", (OHNE_ORIGINAL, jetzt(), buch))
            await db.commit()
            return
        try:
            e = await erkennen.seite_erkennen(original, seite)
        except werkzeug.WerkzeugFehlt as f:
            raise Ruhen(str(f)) from f
        except (werkzeug.Erkennungsfehler, IndexError) as f:
            await self._vermerken(buch, seite, "fehler", str(f) if isinstance(f, werkzeug.Erkennungsfehler) else OHNE_SEITE)
        else:
            await asyncio.to_thread(ablage.anhaengen, z["hash"], e)
            await self._vermerken(buch, seite, "erkannt" if traegt_text(e) else "leer", dauer_s=e.dauer_s)
        await self._vielleicht_fertig(buch, z["hash"])

    @staticmethod
    async def _vermerken(buch: int, seite: int, stand: str, grund: str = "", dauer_s: float = 0.0) -> None:
        await db.execute("UPDATE texterkennung_seite SET stand = ?, grund = ?, dauer_s = ?, geaendert_am = ? WHERE book_id = ? AND seite = ?",
                         (stand, grund, dauer_s, jetzt(), buch, seite))
        await db.commit()

    async def _vielleicht_fertig(self, buch: int, file_hash: str) -> None:
        if await db.fetch_one("SELECT 1 FROM texterkennung_seite WHERE book_id = ? AND stand = 'offen' LIMIT 1", (buch,)):
            return
        await self._buch_fertig(buch, file_hash)

    @staticmethod
    async def _buch_fertig(buch: int, file_hash: str) -> None:
        """Alles erkannt: das Buch nachziehen (`nachziehen`). Geht das nicht, bekommt es einen Grund und kommt im nächsten Lauf
        wieder dran."""
        if not await nachziehen(buch, file_hash):
            await db.execute("UPDATE texterkennung_buch SET grund = ? WHERE book_id = ?", (NICHT_NACHGEZOGEN, buch))
            await db.commit()
            return
        await db.execute("UPDATE texterkennung_buch SET fertig_am = ? WHERE book_id = ?", (jetzt(), buch))
        await db.commit()

    # -- Für den Leser ----------------------------------------------------------------------------------------------------
    async def wartende(self, buch: int, seiten: Iterable[int]) -> set[int]:
        """Welche dieser Seiten noch auf ihre Erkennung warten. Keine, wenn die Erkennung nicht bereit oder von Hand angehalten
        ist; bei einem Buch, das noch nicht durchgesehen ist, jede, sofern es laut Volltext ein Scan sein kann."""
        gefragt = set(seiten)
        if not gefragt or not (await werkzeug.bereitschaft()).bereit or await self.angehalten():
            return set()
        befund = await db.fetch_one("SELECT scan, grund FROM texterkennung_buch WHERE book_id = ?", (buch,))
        if befund is None:
            z = await db.fetch_one("SELECT hash, page_count FROM books WHERE id = ?", (buch,))
            vorab = await asyncio.to_thread(befund_laut_volltext, z["hash"], z["page_count"]) if z else None
            return gefragt if vorab is None or vorab.scan else set()
        zeilen = await db.fetch_all(f"SELECT seite FROM texterkennung_seite WHERE book_id = ? AND stand = 'offen' "
                                    f"AND seite IN ({','.join('?' * len(gefragt))})", (buch, *gefragt))
        return {z["seite"] for z in zeilen}

    async def vorrang(self, buch: int, seite: int) -> Vorrangstand:
        """Hier liest jemand: die Seite und die nächsten `TEXTERKENNUNG_VORRANG_SEITEN` zuerst. Stößt den Auftrag an."""
        stand = await werkzeug.bereitschaft()
        bis = seite + settings.texterkennung_vorrang_seiten
        if stand.bereit:
            await db.execute("INSERT INTO texterkennung_vorrang(book_id, von, bis, seit) VALUES (?, ?, ?, ?) ON CONFLICT(book_id) "
                             "DO UPDATE SET von = excluded.von, bis = excluded.bis, seit = excluded.seit", (buch, seite, bis, jetzt()))
            await db.execute("UPDATE texterkennung_buch SET vorrang_am = ? WHERE book_id = ?", (jetzt(), buch))
            await db.commit()
            await self.anstossen()
        return Vorrangstand(bereit=stand.bereit, grund=stand.grund, von=seite, bis=bis,
                            wartet=sorted(await self.wartende(buch, range(seite, bis + 1))))


texterkennung = Texterkennung()


class Erkennungswache:
    """Sieht beim Start nach einer Weile und im Takt nach, ob es Arbeit gibt, und stößt den Auftrag an."""

    def __init__(self) -> None:
        self._aufgabe: asyncio.Task | None = None

    def starten(self) -> None:
        if self._aufgabe is None or self._aufgabe.done():
            self._aufgabe = asyncio.create_task(self._schleife())

    async def stoppen(self) -> None:
        if self._aufgabe is not None:
            self._aufgabe.cancel()
            await asyncio.gather(self._aufgabe, return_exceptions=True)
            self._aufgabe = None

    async def _schleife(self) -> None:
        await asyncio.sleep(settings.texterkennung_erst_s)
        while True:
            try:
                await self.runde()
            except Exception:                                # noqa: BLE001 - die Wache darf nie still enden
                logger.exception("Texte erkennen: nachsehen")
            await asyncio.sleep(settings.texterkennung_takt_s)

    async def runde(self) -> None:
        await texterkennung.anstossen()


erkennungswache = Erkennungswache()
