"""Ein Buch löschen (BF-60): vorher alle Folgen nennen, dann löschen.

Die Datei geht in den Papierkorb der Kellerwolke und lässt sich dort zurückholen; liegt sie nur auf dem Gerät, ist sie danach
fort, und die Folgen sagen das. Reihenfolge: Eintrag löschen (noch nicht gebucht), Datei in den Papierkorb, buchen, erst dann
Umschlag, Begleiter und Kopien auf dem Gerät. Scheitert der Papierkorb, rollt die Anfrage zurück und nichts ist verloren."""

from __future__ import annotations

import asyncio
import logging
import shutil

from pydantic import BaseModel

from backend.app.ablage.antwort import auf_dem_geraet
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core.anschluesse import anschluesse
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services import bedeutung
from backend.app.services.storage import delete_stored_file, get_sidecar_path

logger = logging.getLogger("buecherfreunde.buch_loeschen")


class Datei(BaseModel):
    pfad: str                   # Ort in der Kellerwolke, sonst der Name der Datei auf dem Gerät
    groesse: int
    papierkorb: bool            # True: kommt in den Papierkorb der Kellerwolke; False: liegt nur hier und ist danach fort


class Folgen(BaseModel):
    """Was mit dem Buch verloren geht; Zahlen, die Sätze bildet die Oberfläche."""
    titel: str
    autor: str
    notizen: int
    markierungen: int
    etiketten: int
    lesestand: bool
    vorlesestelle: bool
    regale: int
    datei: Datei | None
    abschnitte: int | None      # in der Suche nach Bedeutung; None, wenn sie nicht angeschlossen ist oder das Buch nicht kennt


class NichtGeloescht(Exception):
    """Die Datei kam nicht in den Papierkorb; das Buch bleibt, wie es war."""


async def _zahl(sql: str, buch: int) -> int:
    return (await db.fetch_one(sql, (buch,)))["n"]


async def _ablage(file_hash: str) -> dict | None:
    """Der Eintrag in der Kellerwolke, über die Verbindung der laufenden Einheit."""
    return await db.fetch_one("SELECT knoten, name, pfad, groesse FROM ablage_datei WHERE hash = ?", (file_hash,))


async def folgen(buch: int) -> Folgen | None:
    z = await db.fetch_one("SELECT hash, title, author, file_size, file_name FROM books WHERE id = ?", (buch,))
    if z is None:
        return None
    ablage = await _ablage(z["hash"])
    if ablage is not None:
        datei = Datei(pfad=ablage["pfad"] or ablage["name"], groesse=z["file_size"] or ablage["groesse"] or 0, papierkorb=True)
    else:
        hier = await asyncio.to_thread(auf_dem_geraet, z["hash"])
        datei = Datei(pfad=hier.name, groesse=z["file_size"] or 0, papierkorb=False) if hier else None
    stand = await bedeutung.buch_stand(buch) if anschluesse().bedeutung else None
    return Folgen(
        titel=z["title"] or z["file_name"] or "", autor=z["author"] or "",
        notizen=await _zahl("SELECT count(*) AS n FROM book_notes WHERE book_id = ?", buch),
        markierungen=await _zahl("SELECT count(*) AS n FROM book_highlights WHERE book_id = ?", buch),
        etiketten=await _zahl("SELECT count(*) AS n FROM book_labels WHERE book_id = ?", buch),
        lesestand=bool(await _zahl("SELECT count(*) AS n FROM user_book_data WHERE book_id = ? AND COALESCE(reading_position, '') != ''", buch)),
        vorlesestelle=bool(await _zahl("SELECT count(*) AS n FROM vorlesestelle WHERE buch_id = ?", buch)),
        regale=await _zahl("SELECT count(*) AS n FROM book_categories x JOIN categories c ON c.id = x.category_id "
                           "WHERE x.book_id = ? AND COALESCE(c.spezial, 0) = 0", buch),          # "Ungeordnet" ist keins
        datei=datei,
        abschnitte=stand["abschnitte"] if stand else None,
    )


async def loeschen(buch: int) -> bool:
    """False, wenn es das Buch nicht gibt. Wirft NichtGeloescht, wenn die Datei nicht in den Papierkorb kam."""
    z = await db.fetch_one("SELECT hash FROM books WHERE id = ?", (buch,))
    if z is None:
        return False
    ablage = await _ablage(z["hash"])
    if ablage is not None and not wolke.bereit:
        raise NichtGeloescht("Die Kellerwolke ist nicht angebunden, die Datei käme nicht in den Papierkorb.")
    await db.execute("DELETE FROM books WHERE id = ?", (buch,))
    await db.execute("DELETE FROM ablage_datei WHERE hash = ?", (z["hash"],))
    if ablage is not None:
        try:
            # in den Papierkorb der Kellerwolke, der Begleiter geht mit; endgültig löscht nur das Konto
            await wolke.rufe("DELETE", f"/api/v1/ablage/knoten/{ablage['knoten']}")
        except WolkeFehler as f:
            if f.status != 404:                             # schon fort: dann bleibt nur, den Eintrag zu löschen
                raise NichtGeloescht(f.meldung) from f
    await db.commit()
    get_sidecar_path(z["hash"], "cover.jpg").unlink(missing_ok=True)
    await asyncio.to_thread(delete_stored_file, z["hash"])
    await asyncio.to_thread(shutil.rmtree, settings.zwischen_dir / "original" / z["hash"], True)
    logger.info("Buch %d gelöscht", buch)
    return True
