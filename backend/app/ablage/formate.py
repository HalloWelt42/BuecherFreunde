"""Die Dateien eines Buchs (BF-80): das Original und weitere Formate desselben Werks, je eine Zeile in `buch_datei`.

Das Original (`haupt`) ist `books.hash`: aus ihm stammen Text, Umschlag und Angaben, seine Zeile hält die Datenbank selbst
gleich (Trigger in core/database.py). Ein weiteres Format ist eine eigene Datei mit eigener Prüfsumme, je Buch höchstens eine
je Format. Wo eine Datei liegt, sagt wie beim Original ihre Prüfsumme: `ablage_datei` in der Kellerwolke, sonst der Speicher
auf dem Gerät (`get_storage_path`). In der Kellerwolke ist ein weiteres Format Begleiter des Originals (Rolle
`format_<endung>`, Zusatz `.<endung>`): es liegt daneben, heißt wie das Original und zieht mit ihm um, auch in den Papierkorb.
Das Lesen wählt das Format (`GET /api/books/{id}/file?format=`)."""

from __future__ import annotations

import asyncio
import shutil
import sqlite3
import uuid
from pathlib import Path

from backend.app.ablage.namen import ablageort, dateiname
from backend.app.ablage.wolke import wolke
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.models.book import Buchdatei
from backend.app.services.storage import get_storage_path

SPALTEN = "id, format, name, groesse, haupt"


class FormatDa(Exception):
    """Das Buch hat dieses Format schon, oder es gibt die Datei schon."""

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


def rolle(format_: str) -> str:
    return f"format_{format_}"


def endung(name: str) -> str:
    return Path(name).suffix.lower().lstrip(".")


async def dateien(buch: int) -> list[Buchdatei]:
    """Das Original zuerst, dann die weiteren Formate in der Folge, in der sie dazukamen."""
    zeilen = await db.fetch_all(f"SELECT {SPALTEN} FROM buch_datei WHERE buch_id = ? ORDER BY haupt DESC, angelegt_am, format", (buch,))
    return [Buchdatei(id=z["id"], format=z["format"], name=z["name"], groesse=z["groesse"], haupt=bool(z["haupt"])) for z in zeilen]


async def zum_lesen(buch: int, format_: str | None) -> dict | None:
    """Prüfsumme, Name und Format der Datei, die gelesen wird: das gewählte Format, ohne Wahl das Original."""
    if not format_:
        return await db.fetch_one("SELECT hash, file_name AS name, file_format AS format FROM books WHERE id = ?", (buch,))
    return await db.fetch_one("SELECT hash, name, format FROM buch_datei WHERE buch_id = ? AND format = ?", (buch, format_.lower()))


async def hat_format(buch: int, format_: str) -> bool:
    return await db.fetch_one("SELECT 1 AS da FROM buch_datei WHERE buch_id = ? AND format = ?", (buch, format_)) is not None


async def pruefsummen(buch: int) -> list[str]:
    """Alle Dateien des Buchs, das Original zuerst."""
    return [z["hash"] for z in await db.fetch_all("SELECT hash FROM buch_datei WHERE buch_id = ? ORDER BY haupt DESC", (buch,))]


async def weitere(buch: int) -> list[dict]:
    """Die weiteren Formate mit ihrem Ort in der Kellerwolke, wenn sie dort liegen (für die Folgen und das Löschen)."""
    return await db.fetch_all("""SELECT d.hash, d.format, d.name, d.groesse, a.knoten, a.pfad FROM buch_datei d
                                 LEFT JOIN ablage_datei a ON a.hash = d.hash WHERE d.buch_id = ? AND d.haupt = 0 ORDER BY d.angelegt_am""", (buch,))


async def eintragen(buch: int, summe: str, name: str, groesse: int) -> Buchdatei:
    """Ein weiteres Format zum Buch; FormatDa, wenn es das Format oder die Datei schon gibt."""
    format_ = endung(name)
    if await hat_format(buch, format_):
        raise FormatDa(f"Das Buch hat schon ein {format_.upper()}")
    if await db.fetch_one("SELECT 1 AS da FROM books WHERE hash = ?", (summe,)):
        raise FormatDa("Diese Datei ist schon ein eigenes Buch")
    nr = str(uuid.uuid4())
    try:
        await db.execute("INSERT INTO buch_datei (id, buch_id, hash, format, name, groesse, haupt) VALUES (?, ?, ?, ?, ?, ?, 0)",
                         (nr, buch, summe, format_, name, groesse))
    except sqlite3.IntegrityError as f:
        raise FormatDa("Diese Datei gehört schon zu einem Buch") from f
    return Buchdatei(id=nr, format=format_, name=name, groesse=groesse, haupt=False)


async def ablegen(buch: int, summe: str, name: str, *, knoten: str | None, pfad: Path | None, behalten: bool) -> str:
    """Die Datei eines weiteren Formats an ihren Ort, wie das Original: in der Kellerwolke neben das Original (aus einem
    Knoten oder vom Gerät hinaufgeladen), ohne Kellerwolke in den Speicher je Prüfsumme (`behalten`: kopieren, die Quelle
    bleibt). Liefert den Ort zum Anzeigen."""
    haupt = await db.fetch_one("SELECT b.title, b.author, b.file_name, a.knoten FROM books b LEFT JOIN ablage_datei a ON a.hash = b.hash WHERE b.id = ?", (buch,))
    format_ = endung(name)
    if wolke.bereit and (knoten or haupt["knoten"]):
        k = await _in_die_wolke(buch, haupt, format_, knoten, pfad)
        await db.execute("INSERT OR REPLACE INTO ablage_datei(hash, knoten, name, pfad, groesse) VALUES (?, ?, ?, ?, ?)",
                         (summe, k["id"], k["name"], k.get("pfad", ""), (pfad.stat().st_size if pfad else 0) or k.get("groesse") or 0))
        if pfad and not behalten:
            pfad.unlink(missing_ok=True)
        return k.get("pfad") or k["name"]
    assert pfad is not None, "ohne Kellerwolke liegt die Datei auf dem Gerät"
    ziel = get_storage_path(summe) / dateiname(name)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(shutil.copy2 if behalten else shutil.move, pfad, ziel)
    return str(ziel)


async def _in_die_wolke(buch: int, haupt: dict, format_: str, knoten: str | None, pfad: Path | None) -> dict:
    """Neben das Original als Begleiter; liegt das Original nicht in der Kellerwolke, in das Fach des Buchs."""
    if haupt["knoten"]:
        if knoten:
            return await wolke.begleiter_anhaengen(haupt["knoten"], rolle(format_), knoten, f".{format_}")
        assert pfad is not None
        return await wolke.begleiter_schreiben(haupt["knoten"], rolle(format_), f".{format_}", pfad)
    fach, name = ablageort(buch, haupt["title"], haupt["author"], haupt["file_name"], format_)
    ordner = await wolke.ordner(f"{settings.ablage_ordner}/Bücher/{fach}")
    if knoten:
        return await wolke.umziehen(knoten, ordner["id"], name)
    assert pfad is not None
    return await wolke.datei_schreiben(f"{settings.ablage_ordner}/Bücher/{fach}/{name}", pfad)
