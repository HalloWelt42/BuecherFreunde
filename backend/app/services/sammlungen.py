"""Bücher in Sammlungen: viele auf einmal zuordnen und entfernen, die Reihenfolge der Bände (BF-67), eine Sammlung aus
einem Vorschlag anlegen und ab wann eine Sammlung in der Bücherliste ein Eintrag ist (BF-66).

Ein Buch gehört höchstens zu einer Sammlung; seine Bandnummer gilt nur in ihr. Neue Bücher kommen hinten an: die bisher
höchste Nummer der Sammlung plus eins, der Reihe nach."""

from __future__ import annotations

from backend.app.core import einstellungen
from backend.app.core.database import db
from backend.app.models.grenzen import SAMMLUNG_ALS_EINTRAG_AB, SAMMLUNG_ALS_EINTRAG_BIS
from backend.app.services.buchliste import BANDORDNUNG

ALS_EINTRAG_AB = "sammlung_als_eintrag_ab"           # Schlüssel in app_settings
ALS_EINTRAG_AB_VORGABE = 8


class NichtInDerSammlung(ValueError):
    """Ein Buch der Reihenfolge gehört nicht zur Sammlung (oder steht doppelt darin)."""


async def als_eintrag_ab() -> int:
    """Ab so vielen Büchern unter dem Filter ist eine Sammlung in der Liste ein Eintrag."""
    wert = await einstellungen.lesen(ALS_EINTRAG_AB)
    try:
        zahl = int(wert) if wert is not None else ALS_EINTRAG_AB_VORGABE
    except ValueError:
        return ALS_EINTRAG_AB_VORGABE
    return zahl if SAMMLUNG_ALS_EINTRAG_AB <= zahl <= SAMMLUNG_ALS_EINTRAG_BIS else ALS_EINTRAG_AB_VORGABE


async def als_eintrag_ab_setzen(zahl: int) -> None:
    await einstellungen.schreiben(ALS_EINTRAG_AB, str(zahl))


def gehoeren_nicht(nummern: list[int], wozu: str) -> str:
    """Der Satz für Bücher, die nicht dazugehören, etwa "Das Buch 12 gehört nicht zu dieser Sammlung"."""
    eins = len(nummern) == 1
    return f"{'Das Buch' if eins else 'Die Bücher'} {', '.join(map(str, nummern))} {'gehört' if eins else 'gehören'} nicht {wozu}"


def _eindeutig(book_ids: list[int]) -> list[int]:
    return list(dict.fromkeys(book_ids))


async def hoechste_nummer(sammlung_id: int) -> int:
    """Die höchste Bandnummer der Sammlung, soweit sie mit einer Zahl beginnt; 0 ohne."""
    z = await db.fetch_one("""SELECT MAX(CAST(band_nummer AS INTEGER)) AS n FROM books
                              WHERE sammlung_id = ? AND band_nummer GLOB '[0-9]*'""", (sammlung_id,))
    return (z["n"] if z else None) or 0


async def anhaengen(sammlung_id: int, book_ids: list[int]) -> int:
    """Die Bücher in die Sammlung, neue hinten an in der gegebenen Reihenfolge; wer dort schon eine Nummer hat, bleibt, wo er
    ist. Gibt zurück, wie viele Bücher sich geändert haben."""
    naechste = await hoechste_nummer(sammlung_id) + 1
    geaendert = 0
    for buch in _eindeutig(book_ids):
        z = await db.fetch_one("SELECT sammlung_id, band_nummer FROM books WHERE id = ?", (buch,))
        if z is None or (z["sammlung_id"] == sammlung_id and (z["band_nummer"] or "").strip()):
            continue
        await db.execute("UPDATE books SET sammlung_id = ?, band_nummer = ? WHERE id = ?", (sammlung_id, str(naechste), buch))
        naechste += 1
        geaendert += 1
    await db.commit()
    return geaendert


async def entfernen(book_ids: list[int]) -> int:
    """Die Bücher aus ihrer Sammlung; die Bandnummer geht mit. Gibt zurück, wie viele in einer waren."""
    geaendert = 0
    for buch in _eindeutig(book_ids):
        geaendert += (await db.execute("UPDATE books SET sammlung_id = NULL, band_nummer = '' WHERE id = ? AND sammlung_id IS NOT NULL",
                                       (buch,))).rowcount
    await db.commit()
    return geaendert


async def reihenfolge_setzen(sammlung_id: int, book_ids: list[int]) -> None:
    """Bandnummern 1 bis n in dieser Reihenfolge. Bücher der Sammlung, die nicht genannt sind, folgen in ihrer bisherigen
    Bandfolge, damit keine Nummer doppelt ist."""
    if len(set(book_ids)) != len(book_ids):
        raise NichtInDerSammlung("Ein Buch steht mehr als einmal in der Reihenfolge")
    alle = [z["id"] for z in await db.fetch_all(f"SELECT b.id FROM books b WHERE b.sammlung_id = ? ORDER BY {BANDORDNUNG.sql()}",
                                                (sammlung_id,))]
    dabei = set(alle)
    if fremd := [b for b in book_ids if b not in dabei]:
        raise NichtInDerSammlung(gehoeren_nicht(fremd, "zu dieser Sammlung"))
    genannt = set(book_ids)
    for band, buch in enumerate([*book_ids, *(b for b in alle if b not in genannt)], start=1):
        await db.execute("UPDATE books SET band_nummer = ? WHERE id = ?", (str(band), buch))
    await db.commit()


async def anlegen(name: str, farbe: str) -> int:
    c = await db.execute("INSERT INTO collections (name, color) VALUES (?, ?)", (name, farbe))
    return c.lastrowid


async def einordnen(sammlung_id: int, baende: list[tuple[int, str]]) -> None:
    """Bücher mit ihrer Bandnummer in die Sammlung."""
    for buch, band in baende:
        await db.execute("UPDATE books SET sammlung_id = ?, band_nummer = ? WHERE id = ?", (sammlung_id, band, buch))
