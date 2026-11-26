"""Sichtbarkeit (BF-78): welche Bücher jemand sieht, an einer Stelle entschieden.

- Ein Buch, das ein anderes Profil privat markiert hat, gibt es für niemanden sonst.
- Ein Kind sieht nur, was ihm freigegeben ist: das Buch selbst oder eine Kategorie, in der es steht (auch eine Unterkategorie,
  etwa eine Kategorie in einem freigegebenen Bereich). Nichts geht von selbst frei; die Altersangabe ist nur Hilfe.
- Andere Apps (Fundus) sehen nur, was niemand privat markiert hat.

`Sicht.bedingung` gibt die Bedingung als SQL mit ihren Werten für eine Spalte mit der Nummer des Buchs; jede Liste, Suche und
jeder Zähler setzt sie dazu. Wege mit einem Buch im Pfad prüft `pfad_pruefen` (aus core/auth.py), bevor der Weg selbst läuft."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.app.core.database import db
from backend.app.familie.modelle import Profil
from backend.app.models.grenzen import GROESSTE_ZAHL

BUCH_IM_PFAD = ("book_id", "buch_id", "buch")      # Namen im Pfad, die immer ein Buch dieser App meinen
FASSUNG_IM_PFAD = "fid"

# Kategorien eines Kindes mit allem darunter
FREIE_KATEGORIEN = """WITH RECURSIVE frei(id) AS (SELECT ziel_id FROM freigabe WHERE profil_id = ? AND art = 'kategorie'
                                                 UNION SELECT c.id FROM categories c JOIN frei ON c.parent_id = frei.id)
                      SELECT id FROM frei"""
FREIGEGEBEN = f"""SELECT ziel_id FROM freigabe WHERE profil_id = ? AND art = 'buch'
                  UNION SELECT x.book_id FROM book_categories x WHERE x.category_id IN ({FREIE_KATEGORIEN})"""


class Verborgen(LookupError):
    """Das Buch gibt es für diese Sicht nicht."""

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


@dataclass(frozen=True)
class Sicht:
    profil_id: str | None                           # leer: eine andere App
    kind: bool = False

    @classmethod
    def von(cls, p: Profil) -> Sicht:
        return cls(p.id, p.kind)

    def bedingung(self, spalte: str = "b.id") -> tuple[str, tuple]:
        """SQL über `spalte` (Nummer eines Buchs) und seine Werte, in dieser Folge einzusetzen."""
        if self.profil_id is None:
            return f"{spalte} NOT IN (SELECT book_id FROM buch_privat)", ()
        privat = f"{spalte} NOT IN (SELECT book_id FROM buch_privat WHERE profil_id != ?)"
        if not self.kind:
            return privat, (self.profil_id,)
        return f"({privat} AND {spalte} IN ({FREIGEGEBEN}))", (self.profil_id, self.profil_id, self.profil_id)


APPS = Sicht(None)


async def sieht(sicht: Sicht, buch: int) -> bool:
    bedingung, werte = sicht.bedingung("b.id")
    return await db.fetch_one(f"SELECT 1 FROM books b WHERE b.id = ? AND {bedingung}", (buch, *werte)) is not None


async def nur_sichtbare(sicht: Sicht, buecher: list[int]) -> list[int]:
    """Die sichtbaren in ihrer Folge; die anderen gibt es für diese Sicht nicht."""
    if not buecher:
        return []
    bedingung, werte = sicht.bedingung("b.id")
    da = {z["id"] for z in await db.fetch_all(f"SELECT b.id FROM books b WHERE b.id IN ({','.join('?' * len(set(buecher)))}) AND {bedingung}",
                                              (*set(buecher), *werte))}
    return [b for b in buecher if b in da]


def _nummer(wert: str) -> int | None:
    return int(wert) if wert.isdigit() and 0 < int(wert) <= GROESSTE_ZAHL else None


async def pfad_pruefen(sicht: Sicht, pfad: Mapping[str, str]) -> None:
    """Wirft `Verborgen`, wenn der Pfad ein Buch oder eine Fassung nennt, die diese Sicht nicht sieht. Was keine Nummer ist,
    prüft der Weg selbst (404 oder 422)."""
    for name in BUCH_IM_PFAD:
        if name in pfad and (nr := _nummer(str(pfad[name]))) and not await sieht(sicht, nr):
            raise Verborgen("Buch nicht gefunden")
    if FASSUNG_IM_PFAD in pfad and (nr := _nummer(str(pfad[FASSUNG_IM_PFAD]))):
        z = await db.fetch_one("SELECT buch_id FROM fassung WHERE id = ?", (nr,))
        if z and not await sieht(sicht, z["buch_id"]):
            raise Verborgen("Fassung nicht gefunden")


async def privat_setzen(profil_id: str, buch: int, privat: bool) -> None:
    if privat:
        await db.execute("INSERT OR IGNORE INTO buch_privat (profil_id, book_id) VALUES (?, ?)", (profil_id, buch))
    else:
        await db.execute("DELETE FROM buch_privat WHERE profil_id = ? AND book_id = ?", (profil_id, buch))


async def private(profil_id: str, buecher: list[int]) -> set[int]:
    """Welche dieser Bücher das Profil privat markiert hat."""
    if not buecher:
        return set()
    zeilen = await db.fetch_all(f"SELECT book_id FROM buch_privat WHERE profil_id = ? AND book_id IN ({','.join('?' * len(buecher))})",
                                (profil_id, *buecher))
    return {z["book_id"] for z in zeilen}
