"""Die Vorschläge des Sammlungsfinders (BF-66) in `sammlung_vorschlag`: die Ergebnisse eines Laufs merken, die offenen
lesen, einen als Sammlung anlegen oder verwerfen. Angelegt und verworfen ist endgültig: die Schlüssel solcher Vorschläge
schlägt kein Lauf wieder vor. Gezeigt und angelegt werden nur Bücher, die noch in keiner Sammlung sind."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel

from backend.app.core.database import db
from backend.app.services import sammlungen
from backend.app.services.buchliste import Ordnung, bandfolge

Stand = Literal["offen", "angelegt", "verworfen"]
JETZT = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
NACH_BAND = Ordnung("band", bandfolge("v.band"), "ASC").nach()       # die erkannte Bandnummer in sammlung_vorschlag_buch


class VorschlagFehlt(LookupError):
    pass


class NichtOffen(Exception):
    """Der Vorschlag ist schon angelegt oder verworfen."""


class FalscheAuswahl(ValueError):
    """Die gewählten Bücher passen nicht zum Vorschlag."""


class Bandangabe(BaseModel):
    buch_id: int
    band: str


class Ergebnis(BaseModel):
    """Was ein Lauf für eine Reihe gefunden hat."""

    schluessel: list[str]                       # die Schlüssel der Regelfunde (Reihe|Autor, normiert)
    name: str
    autor: str
    wege: list[str]
    ki: str
    ki_geprueft: bool
    ki_zweifel: bool = False                    # die KI hält es für keine Reihe; der Vorschlag bleibt, du entscheidest
    baende: list[Bandangabe]


class OffenerVorschlag(BaseModel):
    id: int
    name: str
    autor: str
    wege: list[str]
    ki: str
    ki_geprueft: bool
    ki_zweifel: bool
    baende: list[Bandangabe]                    # nur Bücher ohne Sammlung, nach Band


async def geschlossene_schluessel() -> set[str]:
    """Die Schlüssel der Regelfunde aller angelegten und verworfenen Vorschläge."""
    zeilen = await db.fetch_all("SELECT schluessel FROM sammlung_vorschlag WHERE stand != 'offen'")
    return {s for z in zeilen for s in z["schluessel"].split("\n")}


async def ohne_sammlung(buecher: set[int]) -> set[int]:
    """Welche dieser Bücher in keiner Sammlung sind."""
    if not buecher:
        return set()
    ph = ",".join("?" * len(buecher))
    return {z["id"] for z in await db.fetch_all(f"SELECT id FROM books WHERE sammlung_id IS NULL AND id IN ({ph})", tuple(buecher))}


async def merken(ergebnisse: list[Ergebnis]) -> int:
    """Die Ergebnisse eines Laufs als offene Vorschläge (gleicher Schlüssel: derselbe Vorschlag, mit neuem Inhalt); offene,
    die der Lauf nicht mehr findet, gehen. Gibt zurück, wie viele offen sind."""
    async with db.einheit():
        behalten: list[int] = []
        for e in ergebnisse:
            z = await db.fetch_one(f"""INSERT INTO sammlung_vorschlag (schluessel, name, autor, wege, ki, ki_geprueft, ki_zweifel)
                                       VALUES (?, ?, ?, ?, ?, ?, ?)
                                       ON CONFLICT(schluessel) DO UPDATE SET name = excluded.name, autor = excluded.autor,
                                           wege = excluded.wege, ki = excluded.ki, ki_geprueft = excluded.ki_geprueft,
                                           ki_zweifel = excluded.ki_zweifel, geaendert_am = {JETZT}
                                       WHERE sammlung_vorschlag.stand = 'offen' RETURNING id""",
                                   ("\n".join(sorted(e.schluessel)), e.name, e.autor, json.dumps(e.wege, ensure_ascii=False), e.ki,
                                    int(e.ki_geprueft), int(e.ki_zweifel)))
            if z is None:                                   # angelegt oder verworfen: bleibt es
                continue
            await db.execute("DELETE FROM sammlung_vorschlag_buch WHERE vorschlag_id = ?", (z["id"],))
            await db.execute_many("INSERT OR IGNORE INTO sammlung_vorschlag_buch (vorschlag_id, buch_id, band) VALUES (?, ?, ?)",
                                  [(z["id"], b.buch_id, b.band) for b in e.baende])
            behalten.append(z["id"])
        await db.execute(f"DELETE FROM sammlung_vorschlag WHERE stand = 'offen' AND id NOT IN ({','.join('?' * len(behalten))})",
                         tuple(behalten))
    return len(behalten)


async def _baende(vorschlag_id: int) -> list[Bandangabe]:
    zeilen = await db.fetch_all(f"""SELECT v.buch_id, v.band FROM sammlung_vorschlag_buch v JOIN books b ON b.id = v.buch_id
                                    WHERE v.vorschlag_id = ? AND b.sammlung_id IS NULL
                                    ORDER BY {NACH_BAND}, b.title COLLATE NOCASE, b.id""", (vorschlag_id,))
    return [Bandangabe(**z) for z in zeilen]


def _vorschlag(z: dict, baende: list[Bandangabe]) -> OffenerVorschlag:
    return OffenerVorschlag(id=z["id"], name=z["name"], autor=z["autor"], wege=json.loads(z["wege"] or "[]"), ki=z["ki"],
                            ki_geprueft=bool(z["ki_geprueft"]), ki_zweifel=bool(z["ki_zweifel"]), baende=baende)


async def offene() -> list[OffenerVorschlag]:
    """Die offenen Vorschläge mit mindestens einem Buch ohne Sammlung, die größten zuerst; die, an denen die KI zweifelt, am Ende."""
    aus = []
    for z in await db.fetch_all("SELECT * FROM sammlung_vorschlag WHERE stand = 'offen'"):
        if baende := await _baende(z["id"]):
            aus.append(_vorschlag(z, baende))
    return sorted(aus, key=lambda v: (v.ki_zweifel, -len(v.baende), v.name.casefold(), v.id))


async def offener(vorschlag_id: int) -> OffenerVorschlag:
    z = await db.fetch_one("SELECT * FROM sammlung_vorschlag WHERE id = ?", (vorschlag_id,))
    if z is None:
        raise VorschlagFehlt("Vorschlag nicht gefunden")
    if z["stand"] != "offen":
        raise NichtOffen(f"Der Vorschlag ist schon {z['stand']}")
    return _vorschlag(z, await _baende(vorschlag_id))


def auswahl(v: OffenerVorschlag, book_ids: list[int] | None) -> list[Bandangabe]:
    """Die Bücher, die in die Sammlung kommen: alle des Vorschlags oder die gewählten davon, nach Band."""
    if book_ids is None:
        baende = v.baende
    else:
        if fremd := sorted(set(book_ids) - {b.buch_id for b in v.baende}):
            raise FalscheAuswahl(sammlungen.gehoeren_nicht(fremd, "zu diesem Vorschlag oder schon zu einer Sammlung"))
        baende = [b for b in v.baende if b.buch_id in set(book_ids)]
    if not baende:
        raise FalscheAuswahl("Für die Sammlung ist kein Buch gewählt")
    return baende


async def _schliessen(vorschlag_id: int, stand: Stand, sammlung_id: int | None = None) -> None:
    await db.execute(f"UPDATE sammlung_vorschlag SET stand = ?, sammlung_id = ?, geaendert_am = {JETZT} WHERE id = ?",
                     (stand, sammlung_id, vorschlag_id))


async def anlegen(vorschlag_id: int, name: str | None, book_ids: list[int] | None, farbe: str) -> int:
    """Legt die Sammlung an, ordnet die Bücher mit ihrer erkannten Bandnummer ein und schließt den Vorschlag; gibt die neue
    Sammlung zurück."""
    async with db.einheit():
        v = await offener(vorschlag_id)
        baende = auswahl(v, book_ids)
        sammlung = await sammlungen.anlegen(name or v.name, farbe)
        await sammlungen.einordnen(sammlung, [(b.buch_id, b.band) for b in baende])
        await _schliessen(v.id, "angelegt", sammlung)
    return sammlung


async def verwerfen(vorschlag_id: int) -> None:
    async with db.einheit():
        v = await offener(vorschlag_id)
        await _schliessen(v.id, "verworfen")
