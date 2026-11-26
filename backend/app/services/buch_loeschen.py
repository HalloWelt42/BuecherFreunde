"""Ein Buch löschen (BF-60): vorher alle Folgen nennen, dann löschen.

Die Datei geht in den Papierkorb der Kellerwolke und lässt sich dort zurückholen; liegt sie nur auf dem Gerät, ist sie danach
fort, und die Folgen sagen das. Reihenfolge: Eintrag löschen (noch nicht gebucht), Datei in den Papierkorb, buchen, erst dann
Umschlag, Begleiter und Kopien auf dem Gerät. Scheitert der Papierkorb, rollt die Anfrage zurück und nichts ist verloren."""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from pydantic import BaseModel

from backend.app.ablage import formate
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
    fassungen: list[Datei] = []  # übersetzte Fassungen (BF-71): in der Kellerwolke in den Papierkorb, auf dem Gerät mit dem Buch fort
    formate: list[Datei] = []    # weitere Formate (BF-80): neben dem Original, gehen mit ihm
    material: list[Datei] = []   # Begleitmaterial (BF-81, setzt api/books.py ein): in der Kellerwolke mit dem Original in den Papierkorb,
    #                              sonst mit dem Buchordner fort


class NichtGeloescht(Exception):
    """Die Datei kam nicht in den Papierkorb; das Buch bleibt, wie es war."""


async def _zahl(sql: str, buch: int) -> int:
    return (await db.fetch_one(sql, (buch,)))["n"]


async def _ablage(file_hash: str) -> dict | None:
    """Der Eintrag in der Kellerwolke, über die Verbindung der laufenden Einheit."""
    return await db.fetch_one("SELECT knoten, name, pfad, groesse FROM ablage_datei WHERE hash = ?", (file_hash,))


async def _fassungen(buch: int) -> list[dict]:
    return await db.fetch_all("SELECT datei, knoten FROM fassung WHERE buch_id = ? AND datei != ''", (buch,))


def _fassungsdatei(z: dict) -> Datei:
    if z["knoten"]:
        return Datei(pfad=z["datei"], groesse=0, papierkorb=True)
    hier = Path(z["datei"])
    return Datei(pfad=hier.name, groesse=hier.stat().st_size if hier.is_file() else 0, papierkorb=False)


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
                           "WHERE x.book_id = ? AND c.slug != 'ungeordnet'", buch),          # "Ungeordnet" ist keins (wie api/books.py)
        datei=datei,
        abschnitte=stand["abschnitte"] if stand else None,
        fassungen=[_fassungsdatei(f) for f in await _fassungen(buch)],
        formate=[Datei(pfad=f["pfad"] or f["name"], groesse=f["groesse"], papierkorb=bool(f["knoten"])) for f in await formate.weitere(buch)],
    )


async def loeschen(buch: int) -> bool:
    """False, wenn es das Buch nicht gibt. Wirft NichtGeloescht, wenn die Datei nicht in den Papierkorb kam."""
    z = await db.fetch_one("SELECT hash FROM books WHERE id = ?", (buch,))
    if z is None:
        return False
    ablage = await _ablage(z["hash"])
    weitere = await formate.weitere(buch)
    # das Original zuerst: es nimmt seine Begleiter mit (Auszug, weitere Formate, Material); was danach noch da ist, einzeln
    knoten = ([ablage["knoten"]] if ablage is not None else []) + [f["knoten"] for f in await _fassungen(buch) if f["knoten"]] \
        + [f["knoten"] for f in weitere if f["knoten"]]
    if knoten and not wolke.bereit:
        raise NichtGeloescht("Die Kellerwolke ist nicht angebunden, die Datei käme nicht in den Papierkorb.")
    hashes = [z["hash"], *(f["hash"] for f in weitere)]
    await db.execute("DELETE FROM books WHERE id = ?", (buch,))
    await db.execute(f"DELETE FROM ablage_datei WHERE hash IN ({','.join('?' * len(hashes))})", tuple(hashes))
    for k in knoten:
        try:
            # in den Papierkorb der Kellerwolke, der Begleiter geht mit; endgültig löscht nur das Konto
            await wolke.rufe("DELETE", f"/api/v1/ablage/knoten/{k}")
        except WolkeFehler as f:
            if f.status != 404:                             # schon fort: dann bleibt nur, den Eintrag zu löschen
                raise NichtGeloescht(f.meldung) from f
    await db.commit()
    get_sidecar_path(z["hash"], "cover.jpg").unlink(missing_ok=True)
    for h in hashes:
        await asyncio.to_thread(delete_stored_file, h)
        await asyncio.to_thread(shutil.rmtree, settings.zwischen_dir / "original" / h, True)
    logger.info("Buch %d gelöscht", buch)
    return True
