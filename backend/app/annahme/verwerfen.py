"""Verwerfen einer Vorschau (BF-80), nur nach der Folgenvorschau mit der Liste der Dateien (`folgen`, dann `verwerfen` mit
deren `stand`).

- In der Kellerwolke kommt jede Datei in den Papierkorb und lässt sich dort zurückholen.
- Ohne Kellerwolke ist sie endgültig fort, auch aus dem Eingangsordner auf dem Gerät; die Folgen sagen das je Datei.
- Aus dem Einlese-Ordner und der externen Sammlung bleibt die Datei, wo sie ist (sie gehört der App nicht).

Ins Regal kommt nichts, im Bestand ändert sich nichts; die Aufnahmen bleiben im Verlauf (Stand `verworfen`). Was die Vorschau
selbst angelegt hat (Text und Umschlag zur Prüfsumme, der Eintrag zum Lesen aus der Kellerwolke), geht mit, wenn kein Buch und
keine andere Aufnahme es braucht."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
from pathlib import Path

from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.annahme.modelle import Verwerffolge, Verwerffolgen
from backend.app.annahme.uebernehmen import BEHALTEN
from backend.app.annahme.vorschau import IN_ARBEIT, WARTET, VorschauFehlt, beruehrt, offene
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services.storage import delete_stored_file, get_sidecar_path

logger = logging.getLogger("buecherfreunde.annahme.verwerfen")
OFFEN_ODER_LIEGEND = (WARTET, *IN_ARBEIT, "da", "format", "kaputt", "fehler", "entpackt")


class StandVeraltet(Exception):
    pass


class NichtVerworfen(Exception):
    """Eine Datei kam nicht in den Papierkorb; was schon verworfen ist, bleibt es, der Rest wartet weiter."""


def _im_eingang(z: dict) -> Path | None:
    ordner = settings.eingang_dir / str(z["id"])
    return next((f for f in ordner.iterdir() if f.is_file()), None) if ordner.is_dir() else None


def _folge(z: dict) -> Verwerffolge:
    ordner = (z["zip_pfad"] or "").rpartition("/")[0]
    if z["quelle"] in BEHALTEN and z["pfad"]:
        wirkung, pfad = "bleibt", z["pfad"]
    elif z["knoten"]:
        wirkung, pfad = "papierkorb", f"{settings.ablage_ordner}/Eingang"
    elif z["pfad"]:
        wirkung, pfad = "endgueltig", z["pfad"]
    elif hier := _im_eingang(z):
        wirkung, pfad = "endgueltig", str(hier)
    else:
        wirkung, pfad = "nichts", ""
    return Verwerffolge(id=z["id"], name=z["name"], ordner=ordner, groesse=z["groesse"], wirkung=wirkung, pfad=pfad)


async def _zeilen(nr: str, ids: list[int] | None) -> list[dict]:
    """Was zu verwerfen ist: die Aufnahmen der Vorschau, die noch nicht im Regal sind."""
    zeilen = await db.fetch_all(f"SELECT * FROM aufnahme WHERE vorschau = ? AND stand IN ({','.join('?' * len(OFFEN_ODER_LIEGEND))}) ORDER BY id",
                                (nr, *OFFEN_ODER_LIEGEND))
    if ids is not None:
        if fremd := set(ids) - {z["id"] for z in zeilen}:
            raise VorschauFehlt(f"Diese Aufnahme lässt sich hier nicht verwerfen: {', '.join(map(str, sorted(fremd)))}")
        zeilen = [z for z in zeilen if z["id"] in ids]
    return zeilen


def _stand(nr: str, folgen: list[Verwerffolge]) -> str:
    return hashlib.sha256(json.dumps([nr, [f.model_dump() for f in folgen]], sort_keys=True).encode()).hexdigest()[:16]


async def folgen(nr: str, ids: list[int] | None) -> Verwerffolgen:
    v = await offene(nr)
    liste = [_folge(z) for z in await _zeilen(nr, ids)]
    zahl = lambda w: sum(1 for f in liste if f.wirkung == w)          # noqa: E731
    return Verwerffolgen(vorschau=nr, name=v["name"], dateien=liste, papierkorb=zahl("papierkorb"), endgueltig=zahl("endgueltig"),
                         bleibt=zahl("bleibt"), stand=_stand(nr, liste))


TEXT = {"papierkorb": "Verworfen, im Papierkorb der Kellerwolke", "endgueltig": "Verworfen, endgültig gelöscht",
        "bleibt": "Verworfen, die Datei bleibt im Ordner", "nichts": "Verworfen"}


async def verwerfen(nr: str, ids: list[int] | None, stand: str) -> int:
    """Nur mit dem `stand` aus den Folgen; liefert, wie viele Aufnahmen verworfen sind."""
    if (f := await folgen(nr, ids)).stand != stand:
        raise StandVeraltet("Seit der Vorschau hat sich etwas geändert, bitte die Folgen noch einmal ansehen")
    zeilen = {z["id"]: z for z in await _zeilen(nr, ids)}
    verworfen = 0
    try:
        for folge in f.dateien:
            z = zeilen[folge.id]
            await _datei_weg(z, folge)
            await db.execute("UPDATE aufnahme SET stand = 'verworfen', schritt = 0, text = ?, ki_stand = '', "
                             "geaendert_am = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?", (TEXT[folge.wirkung], z["id"]))
            await db.commit()
            await _vorschau_reste(z)
            verworfen += 1
    finally:
        offen = await db.fetch_one(f"SELECT COUNT(*) AS n FROM aufnahme WHERE vorschau = ? AND stand IN ({','.join('?' * len(OFFEN_ODER_LIEGEND))})",
                                   (nr, *OFFEN_ODER_LIEGEND))
        if not offen["n"]:
            await db.execute("UPDATE vorschau SET stand = 'verworfen' WHERE id = ?", (nr,))
        await beruehrt(nr)
        await db.commit()
    return verworfen


async def _datei_weg(z: dict, folge: Verwerffolge) -> None:
    if z["upload"] and z["stand"] in ("wartet", "laedt", "angehalten"):
        try:
            await wolke.upload_abbrechen(z["upload"])
        except WolkeFehler as f:
            logger.info("Upload %s nicht abgebrochen: %s", z["upload"], f)
    if folge.wirkung == "papierkorb":
        try:
            await wolke.papierkorb(z["knoten"])
        except WolkeFehler as f:
            raise NichtVerworfen(f"{z['name']}: {f.meldung}") from f
    elif folge.wirkung == "endgueltig":
        await asyncio.to_thread(Path(folge.pfad).unlink, True)
        ordner = settings.eingang_dir / str(z["id"])
        if ordner.is_dir() and not any(ordner.iterdir()):
            ordner.rmdir()


async def _vorschau_reste(z: dict) -> None:
    """Text und Umschlag, die die Vorschau zur Prüfsumme abgelegt hat, und der Eintrag zum Lesen aus der Kellerwolke, wenn kein
    Buch und keine andere wartende Aufnahme sie braucht."""
    summe = z["sha256"]
    if not summe or await db.fetch_one("SELECT 1 AS da FROM books WHERE hash = ? UNION SELECT 1 FROM buch_datei WHERE hash = ?", (summe, summe)):
        return
    if await db.fetch_one(f"SELECT 1 AS da FROM aufnahme WHERE sha256 = ? AND id != ? AND stand IN ({','.join('?' * len(OFFEN_ODER_LIEGEND))})",
                          (summe, z["id"], *OFFEN_ODER_LIEGEND)):
        return
    await db.execute("DELETE FROM ablage_datei WHERE hash = ?", (summe,))
    await db.commit()
    get_sidecar_path(summe, "cover.jpg").unlink(missing_ok=True)
    await asyncio.to_thread(delete_stored_file, summe)
    await asyncio.to_thread(shutil.rmtree, settings.zwischen_dir / "original" / summe, True)
