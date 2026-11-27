"""ISBN zur Wahl (BF-111): was der Lauf "ISBN" nicht eintragen durfte, weil es nicht sicher passt. Je Buch seine Kandidaten in der
Rangfolge; angenommen wird der beste, abgelehnte kommen bei einem neuen Lauf nicht wieder. Gezeigt wird ein Buch nur, solange es
keine ISBN hat; bekommt es eine auf anderem Weg, ist seine Wahl erledigt."""

from __future__ import annotations

from backend.app.core.database import db
from backend.app.isbnsuche.kandidaten import rang
from backend.app.isbnsuche.modelle import Kandidat, Wahl
from backend.app.quellen.abgleich import STUFEN

OFFEN, ABGELEHNT = "offen", "abgelehnt"
_STUFENRANG = "CASE w.stufe " + " ".join(f"WHEN '{s.value}' THEN {n}" for n, s in enumerate(STUFEN)) + " END"
_OHNE_ISBN = "COALESCE(b.isbn, '') = ''"


def _liste(werte: list[int]) -> str:
    return ",".join("?" * len(werte))


async def merken(buch_id: int, kandidaten: list[Kandidat]) -> None:
    """Die offenen Kandidaten eines Buchs ersetzen; abgelehnte bleiben abgelehnt."""
    async with db.einheit():
        await db.execute("DELETE FROM isbn_wahl WHERE buch_id = ? AND stand = ?", (buch_id, OFFEN))
        for n, k in enumerate(kandidaten):
            await db.execute("INSERT OR IGNORE INTO isbn_wahl (buch_id, isbn, rang, stufe, kandidat) VALUES (?, ?, ?, ?, ?)",
                             (buch_id, k.isbn13, n, k.einstufung.stufe.value, k.model_dump_json()))


async def abgelehnt(buch_id: int) -> set[str]:
    zeilen = await db.fetch_all("SELECT isbn FROM isbn_wahl WHERE buch_id = ? AND stand = ?", (buch_id, ABGELEHNT))
    return {z["isbn"] for z in zeilen}


async def fuer_buch(buch_id: int) -> list[Kandidat]:
    """Die offenen Kandidaten eines Buchs ohne ISBN, in der Rangfolge."""
    zeilen = await db.fetch_all(f"""SELECT w.kandidat FROM isbn_wahl w JOIN books b ON b.id = w.buch_id
                                    WHERE w.buch_id = ? AND w.stand = ? AND {_OHNE_ISBN} ORDER BY w.rang""", (buch_id, OFFEN))
    return [Kandidat.model_validate_json(z["kandidat"]) for z in zeilen]


async def mit_pruefungen(buch_id: int, kandidaten: list[Kandidat]) -> list[Kandidat]:
    """Frisch gefundene Kandidaten mit dem, was der Lauf bei den Quellen schon erfahren hat, wieder in der Rangfolge."""
    gemerkt = {k.isbn13: k.quelle for k in await fuer_buch(buch_id) if k.quelle}
    if not gemerkt:
        return kandidaten
    return sorted((k.model_copy(update={"quelle": gemerkt.get(k.isbn13, k.quelle)}) for k in kandidaten), key=rang)


async def zahl() -> int:
    z = await db.fetch_one(f"""SELECT COUNT(DISTINCT w.buch_id) AS n FROM isbn_wahl w JOIN books b ON b.id = w.buch_id
                               WHERE w.stand = ? AND {_OHNE_ISBN}""", (OFFEN,))
    return z["n"] if z else 0


async def seite(anzahl: int, versatz: int) -> tuple[int, list[Wahl]]:
    """Je Buch der beste Kandidat, die besten Stufen zuerst, dann nach Titel."""
    zeilen = await db.fetch_all(f"""SELECT w.buch_id, w.kandidat,
                                           (SELECT COUNT(*) FROM isbn_wahl x WHERE x.buch_id = w.buch_id AND x.stand = ?) - 1 AS weitere
                                    FROM isbn_wahl w JOIN books b ON b.id = w.buch_id
                                    WHERE w.stand = ? AND w.rang = (SELECT MIN(y.rang) FROM isbn_wahl y WHERE y.buch_id = w.buch_id AND y.stand = ?)
                                      AND {_OHNE_ISBN}
                                    ORDER BY {_STUFENRANG}, b.title COLLATE NOCASE, w.buch_id LIMIT ? OFFSET ?""",
                                (OFFEN, OFFEN, OFFEN, anzahl, versatz))
    return await zahl(), [Wahl(buch_id=z["buch_id"], kandidat=Kandidat.model_validate_json(z["kandidat"]), weitere=z["weitere"]) for z in zeilen]


async def annehmen(buecher: list[int]) -> int:
    """Je Buch ohne ISBN den besten offenen Kandidaten eintragen; seine Wahl ist damit erledigt."""
    buecher = list(dict.fromkeys(buecher))
    zeilen = await db.fetch_all(f"""SELECT w.buch_id, w.kandidat FROM isbn_wahl w JOIN books b ON b.id = w.buch_id
                                    WHERE w.buch_id IN ({_liste(buecher)}) AND w.stand = ? AND {_OHNE_ISBN} ORDER BY w.buch_id, w.rang""",
                                (*buecher, OFFEN))
    beste: dict[int, Kandidat] = {}
    for z in zeilen:
        beste.setdefault(z["buch_id"], Kandidat.model_validate_json(z["kandidat"]))
    async with db.einheit():
        for buch_id, k in beste.items():
            await db.execute("UPDATE books SET isbn = ?, updated_at = datetime('now') WHERE id = ?", (k.isbn, buch_id))
        if beste:
            await db.execute(f"DELETE FROM isbn_wahl WHERE buch_id IN ({_liste(list(beste))})", tuple(beste))
    return len(beste)


async def ablehnen(buecher: list[int]) -> int:
    """Alle offenen Kandidaten dieser Bücher ablehnen; gibt zurück, für wie viele Bücher."""
    buecher = list(dict.fromkeys(buecher))
    async with db.einheit():
        zeilen = await db.fetch_all(f"SELECT DISTINCT buch_id FROM isbn_wahl WHERE buch_id IN ({_liste(buecher)}) AND stand = ?", (*buecher, OFFEN))
        await db.execute(f"UPDATE isbn_wahl SET stand = ? WHERE buch_id IN ({_liste(buecher)}) AND stand = ?", (ABGELEHNT, *buecher, OFFEN))
    return len(zeilen)
