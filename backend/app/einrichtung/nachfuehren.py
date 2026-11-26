"""Der Auftrag "Persönliches nachführen" (BF-82): hält den kleinen Begleiter `persoenlich` je Buch (ablage/persoenlich.py) und die
Datei der Profile in der Kellerwolke auf dem Stand, laufend und gebündelt. Der Auszug mit Volltext und Umschlag wird dafür nie
neu geschrieben.

Marken in `nachfuehren`:
- `buch`: Trigger (einrichtung/schema.py) merken jedes Buch, an dem sich Notizen, Markierungen, Etiketten, Lesestand,
  Vorlesestelle, "privat" oder eine Freigabe ändern. Nach einer ruhigen Weile ohne neue Änderung (`PERSOENLICH_RUHE_S`) bekommt
  sein Begleiter einmal eine neue Version, höchstens `PERSOENLICH_JE_RUNDE` je Runde mit `PERSOENLICH_ABSTAND_S` Pause; viele
  Änderungen an einem Buch, etwa der Lesestand beim Lesen, werden so ein Schreiben.
- `profile`: die Datei der Profile.
- `leeren`: Ausschalten mit Entfernen: der Begleiter kommt in den Papierkorb der Kellerwolke (dort zurückzuholen), ein alter Auszug,
  der bis BF-81 Persönliches trug, wird ohne neu geschrieben.

Beim ersten Start mit dieser Fassung merkt `beim_start` einmal die Bücher, zu denen es schon Persönliches gibt, und die Datei der
Profile (Merker `persoenlich_nachgetragen`), nie alle Bücher. Einschalten merkt ebenso nur Bücher mit Persönlichem. Ist Persönliches
aus, fallen Marken `buch` und `profile` weg. Ohne Kellerwolke ruht der Auftrag, die Marken bleiben."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta

from backend.app.ablage import auszug, persoenlich
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core import einstellungen
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.einrichtung import profildatei
from backend.app.einrichtung.modelle import Auftragsstand, Persoenlichfolgen, ProfilZahl, Teil
from backend.app.einrichtung.zustand import Einrichtungsfehler, jetzt

logger = logging.getLogger("buecherfreunde.einrichtung.nachfuehren")
WAS = "Persönliches nachführen"
NACHGETRAGEN = "persoenlich_nachgetragen"       # app_settings: die Bücher mit Persönlichem sind einmal vorgemerkt
IN_DER_WOLKE = "SELECT b.id FROM books b JOIN ablage_datei a ON a.hash = b.hash"
# je Profil und Buch, wo es Persönliches gibt (dieselben Tabellen wie in ablage/persoenlich.py)
JE_BUCH = ("SELECT profil_id, book_id FROM user_book_data UNION SELECT profil_id, buch_id FROM vorlesestelle UNION SELECT profil_id, book_id "
           "FROM book_notes UNION SELECT profil_id, book_id FROM book_highlights UNION SELECT profil_id, book_id FROM book_labels UNION "
           "SELECT profil_id, book_id FROM buch_privat UNION SELECT profil_id, ziel_id FROM freigabe WHERE art = 'buch'")


def _grenze() -> str:
    return (datetime.now(UTC) - timedelta(seconds=settings.persoenlich_ruhe_s)).strftime("%Y-%m-%dT%H:%M:%SZ")


async def merken(art: str) -> int:
    """Jedes Buch, zu dem es Persönliches gibt, bekommt eine Marke dieser Art (sofort fällig), dazu die Datei der Profile."""
    c = await db.execute(f"INSERT INTO nachfuehren(art, ziel, seit) SELECT DISTINCT ?, book_id, '' FROM ({JE_BUCH}) WHERE true "
                         "ON CONFLICT(art, ziel) DO UPDATE SET seit = ''", (art,))
    await db.execute("INSERT INTO nachfuehren(art, ziel, seit) VALUES ('profile', 0, '') ON CONFLICT(art, ziel) DO UPDATE SET seit = ''")
    await db.commit()
    return c.rowcount


class Nachfuehren:
    def __init__(self) -> None:
        self._anstoss = asyncio.Event()
        self._aufgabe: asyncio.Task | None = None
        self.laeuft = False
        self.geschrieben = 0
        self.bytes = 0
        self.grund = ""
        self.begonnen: str | None = None
        self.geaendert: str | None = None

    async def beim_start(self) -> None:
        """Einmal je Bestand: was es schon an Persönlichem gibt, und die Datei der Profile; danach nur noch, was sich ändert."""
        if await einstellungen.lesen(NACHGETRAGEN) is not None:
            return
        n = await merken("buch")
        await einstellungen.schreiben(NACHGETRAGEN, "1")
        logger.info("Persönliches einmal nachgetragen: %d Bücher vorgemerkt", n)

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
                await asyncio.wait_for(self._anstoss.wait(), settings.persoenlich_takt_s)
            except TimeoutError:
                pass
            self._anstoss.clear()
            try:
                await self.runde()
            except asyncio.CancelledError:
                raise
            except Exception:                              # noqa: BLE001 - der Auftrag darf nie still enden
                logger.exception(WAS)
                self.laeuft = False

    async def _ein_buch(self, art: str, buch: int, file_hash: str, original: str) -> bool:
        if art == "buch":
            groesse = await persoenlich.schreiben(original, buch, file_hash)
            self.bytes += groesse
            return groesse > 0
        if k := await persoenlich.knoten(original):            # leeren
            await wolke.papierkorb(k)
        kennung = await wolke.auszug_schreiben(original, await auszug.bauen(buch, file_hash))
        await db.execute("UPDATE ablage_datei SET begleiter = ? WHERE hash = ?", (kennung, file_hash))
        return True

    async def runde(self, sofort: bool = False) -> int:
        """Eine Runde; `sofort` ohne die ruhige Weile (Tests). Antwortet, wie viele Bücher in der Kellerwolke geschrieben wurden."""
        if not wolke.bereit:
            self.grund = "Ohne Kellerwolke gibt es nichts nachzuführen"
            return 0
        an = await persoenlich.an()
        grenze = jetzt() if sofort else _grenze()
        if not an:
            await db.execute("DELETE FROM nachfuehren WHERE art IN ('buch', 'profile')")
        await db.execute(f"DELETE FROM nachfuehren WHERE art IN ('buch', 'leeren') AND ziel NOT IN ({IN_DER_WOLKE})")   # nur auf dem Gerät
        await db.commit()
        self.laeuft, self.grund = True, ""
        self.begonnen = self.begonnen or jetzt()
        n, zeilen = 0, []
        try:
            if await db.fetch_one("SELECT 1 FROM nachfuehren WHERE art = 'profile' AND seit <= ?", (grenze,)):
                await profildatei.schreiben()
                await db.execute("DELETE FROM nachfuehren WHERE art = 'profile' AND seit <= ?", (grenze,))
                await db.commit()
            zeilen = await db.fetch_all(
                "SELECT n.art, n.ziel, n.seit, b.hash, a.knoten FROM nachfuehren n JOIN books b ON b.id = n.ziel JOIN ablage_datei a ON a.hash = b.hash "
                "WHERE n.art IN ('buch', 'leeren') AND n.seit <= ? ORDER BY n.seit, n.ziel LIMIT ?", (grenze, settings.persoenlich_je_runde))
            for z in zeilen:
                if await self._ein_buch(z["art"], z["ziel"], z["hash"], z["knoten"]):
                    n += 1
                    self.geschrieben += 1
                # nur, was seither nicht wieder geändert wurde
                await db.execute("DELETE FROM nachfuehren WHERE art = ? AND ziel = ? AND seit = ?", (z["art"], z["ziel"], z["seit"]))
                await db.commit()
                self.geaendert = jetzt()
                await asyncio.sleep(settings.persoenlich_abstand_s)
        except WolkeFehler as f:
            self.grund = f.meldung
        finally:
            self.laeuft = False
        if len(zeilen) == settings.persoenlich_je_runde:
            self.anstossen()                               # mehr offen: gleich die nächste Runde
        return n

    async def stand(self) -> Auftragsstand:
        offen = (await db.fetch_one("SELECT COUNT(DISTINCT ziel) AS n FROM nachfuehren WHERE art IN ('buch', 'leeren')"))["n"]
        art = "laeuft" if self.laeuft else "pause" if offen and self.grund else "wartet" if offen else "fertig"
        return Auftragsstand(art="nachfuehren", was=WAS, stand=art, gesamt=offen + self.geschrieben, fertig=self.geschrieben,
                             teile=[Teil(schluessel="buecher", name="Bücher", gesamt=offen + self.geschrieben, fertig=self.geschrieben),
                                    Teil(schluessel="bytes", name="Geschrieben", gesamt=self.bytes, fertig=self.bytes)],
                             grund=self.grund, begonnen=self.begonnen, geaendert=self.geaendert)


nachfuehren = Nachfuehren()


# -- Einschalten, Ausschalten mit Folgen ------------------------------------------------------------------------------------

async def folgen() -> Persoenlichfolgen:
    """Was Einschalten in die Kellerwolke schreibt und Ausschalten mit Entfernen dort wegnimmt (die Daten in der App bleiben)."""
    async def zahl(sql: str) -> int:
        return (await db.fetch_one(f"SELECT COUNT(*) AS n FROM ({sql})"))["n"]

    teile = {
        "lesestaende": f"SELECT 1 FROM user_book_data WHERE book_id IN ({IN_DER_WOLKE})",
        "vorlesestellen": f"SELECT 1 FROM vorlesestelle WHERE buch_id IN ({IN_DER_WOLKE})",
        "notizen": f"SELECT 1 FROM book_notes WHERE book_id IN ({IN_DER_WOLKE})",
        "markierungen": f"SELECT 1 FROM book_highlights WHERE book_id IN ({IN_DER_WOLKE})",
        "etiketten": f"SELECT 1 FROM book_labels WHERE book_id IN ({IN_DER_WOLKE})",
        "private": f"SELECT 1 FROM buch_privat WHERE book_id IN ({IN_DER_WOLKE})",
        "freigaben": f"SELECT 1 FROM freigabe WHERE art = 'buch' AND ziel_id IN ({IN_DER_WOLKE})",
    }
    zahlen = {k: await zahl(v) for k, v in teile.items()}
    buecher = await zahl(f"SELECT DISTINCT book_id FROM ({JE_BUCH}) WHERE book_id IN ({IN_DER_WOLKE})")
    profile = [ProfilZahl(**z) for z in await db.fetch_all(
        f"SELECT p.id, p.name, COUNT(DISTINCT x.book_id) AS buecher FROM profil p JOIN ({JE_BUCH}) x ON x.profil_id = p.id "
        f"WHERE x.book_id IN ({IN_DER_WOLKE}) GROUP BY p.id ORDER BY p.sortierung, p.name")]
    an = await persoenlich.an()
    stand = hashlib.sha256(json.dumps([an, buecher, zahlen, [p.model_dump() for p in profile]], sort_keys=True).encode()).hexdigest()[:16]
    return Persoenlichfolgen(buecher=buecher, profile_datei=profildatei.pfad(), profile=profile, stand=stand, **zahlen)


async def schalten(an: bool, entfernen: bool, stand: str) -> None:
    """Einschalten schreibt den Begleiter jedes Buchs mit Persönlichem und die Datei der Profile; Ausschalten lässt alles in der
    Kellerwolke, wie es ist, außer mit `entfernen`: dann kommen Begleiter und Datei der Profile in den Papierkorb. Beides, was in
    der Kellerwolke etwas anlegt oder wegnimmt, nur mit dem `stand` der Folgen."""
    vorher = await persoenlich.an()
    if entfernen and an:
        raise Einrichtungsfehler("Entfernen: nur beim Ausschalten", 422)
    schreibt = (an and not vorher) or entfernen
    if schreibt and not stand:
        raise Einrichtungsfehler("Stand: erst die Folgen ansehen (GET /api/kellerwolke/persoenlich/folgen)", 422)
    if schreibt and stand != (await folgen()).stand:
        raise Einrichtungsfehler("Seit der Vorschau hat sich etwas geändert, bitte die Folgen neu ansehen")
    await persoenlich.setzen(an)
    if an and not vorher:
        await merken("buch")
    elif entfernen:
        await merken("leeren")
        await db.execute("DELETE FROM nachfuehren WHERE art = 'profile'")
        await db.commit()
        if wolke.bereit:
            await profildatei.in_den_papierkorb()
    nachfuehren.anstossen()
