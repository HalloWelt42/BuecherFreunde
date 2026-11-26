"""Bücher in Sammlungen: eine Sammlung aus einem Vorschlag anlegen und ab wann eine Sammlung in der Bücherliste ein Eintrag
ist (BF-66). Ein Buch gehört höchstens zu einer Sammlung; seine Bandnummer gilt nur in ihr."""

from __future__ import annotations

from backend.app.core import einstellungen
from backend.app.core.database import db
from backend.app.models.grenzen import SAMMLUNG_ALS_EINTRAG_AB, SAMMLUNG_ALS_EINTRAG_BIS

ALS_EINTRAG_AB = "sammlung_als_eintrag_ab"           # Schlüssel in app_settings
ALS_EINTRAG_AB_VORGABE = 8


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


async def anlegen(name: str, farbe: str) -> int:
    c = await db.execute("INSERT INTO collections (name, color) VALUES (?, ?)", (name, farbe))
    return c.lastrowid


async def einordnen(sammlung_id: int, baende: list[tuple[int, str]]) -> None:
    """Bücher mit ihrer Bandnummer in die Sammlung."""
    for buch, band in baende:
        await db.execute("UPDATE books SET sammlung_id = ?, band_nummer = ? WHERE id = ?", (sammlung_id, band, buch))
