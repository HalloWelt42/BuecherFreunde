"""Ordnung der Bücherliste und das Zusammenfassen großer Sammlungen zu einem Eintrag (GET /api/books, BF-66).

Sortiert wird nach einem Schlüssel aus einem oder mehreren Teilen (`SORTIERUNGEN`), danach immer nach Titel und Nummer.
Die Bandfolge ist natürlich: Nummern der Zahl nach, Bände ohne Zahl dahinter, ohne Band immer zuletzt.

Zusammenfassen: die Bücher einer Sammlung, von der unter dem Filter mindestens `ab` Bücher dabei sind, erscheinen als ein
Eintrag. Er sortiert nach Titel unter dem Namen der Sammlung, nach Datum unter ihrem neuesten Buch, nach Autor unter ihrem
häufigsten Autor, sonst unter ihrem ersten Buch in der gewählten Ordnung. Die Bedingung `where` kommt fertig aus der
Schnittstelle und spricht die Bücher als `b` an; sie enthält schon die Sichtbarkeit des Profils (BF-78). Die Bewertung ist die des
Profils, nach dem sortiert wird (`Ordnung.profil_id`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from backend.app.core.database import db
from backend.app.models.book import BESONDERES, Werkart

STAPEL = 3                                      # so viele Umschläge zeigt ein Sammlungseintrag


def nach_art(art: Werkart, spalte: str = "b.typ") -> tuple[str, tuple]:
    """Bedingung für Bücher (Art leer) oder Besonderes (alles, was kein Buch ist, BF-77)."""
    if art == "buch":
        return f"COALESCE({spalte}, '') = ''", ()
    return f"{spalte} IN ({','.join('?' * len(BESONDERES))})", BESONDERES


@dataclass(frozen=True)
class Teil:
    """Ein Teil des Sortierschlüssels: ein SQL-Ausdruck über `b` (books) und `ud_sort` (Bewertung)."""

    ausdruck: str
    text: bool = False                          # Groß und Klein gelten gleich
    fest: str = ""                              # feste Richtung, gleich welche gewählt ist


def bandfolge(spalte: str) -> tuple[Teil, ...]:
    """Die natürliche Folge der Bände in `spalte`."""
    return (Teil(f"(COALESCE({spalte}, '') = '')", fest="ASC"),     # ohne Band zuletzt
            Teil(f"({spalte} NOT GLOB '[0-9]*')", fest="ASC"),      # Nummern vor Bänden ohne Zahl
            Teil(f"CAST({spalte} AS REAL)"),
            Teil(spalte, text=True))


BANDFOLGE = bandfolge("b.band_nummer")

SORTIERUNGEN: dict[str, tuple[Teil, ...]] = {
    "titel": (Teil("b.title", text=True),),
    "autor": (Teil("b.author", text=True),),
    "datum": (Teil("b.created_at"),),
    "groesse": (Teil("b.file_size"),),
    "jahr": (Teil("b.year"),),
    "verlag": (Teil("b.publisher", text=True),),
    "bewertung": (Teil("COALESCE(ud_sort.rating, 0)"),),
    "band": BANDFOLGE,
}
VORGABE = "titel"


@dataclass(frozen=True)
class Ordnung:
    name: str
    teile: tuple[Teil, ...]
    richtung: Literal["ASC", "DESC"]
    profil_id: str = ""                         # wessen Bewertung zählt

    @property
    def verbindung(self) -> str:
        """Was der Schlüssel an Tabellen dazu braucht (nur die Bewertung des Profils); ihre Werte in `werte`."""
        return "LEFT JOIN user_book_data ud_sort ON ud_sort.book_id = b.id AND ud_sort.profil_id = ?" if self.name == "bewertung" else ""

    @property
    def werte(self) -> tuple:
        return (self.profil_id,) if self.name == "bewertung" else ()

    def nach(self, spalten: list[str] | None = None) -> str:
        """Die Teile für ORDER BY, je mit Sortierfolge und Richtung; `spalten` statt der Ausdrücke, wenn schon berechnet."""
        ausdruecke = spalten or [t.ausdruck for t in self.teile]
        return ", ".join(f"{a}{' COLLATE NOCASE' if t.text else ''} {t.fest or self.richtung}"
                         for a, t in zip(ausdruecke, self.teile, strict=True))

    def sql(self) -> str:
        """ORDER BY für Bücher (`b`), mit Titel und Nummer am Schluss."""
        return f"{self.nach()}, b.title COLLATE NOCASE, b.id"


def ordnung(sortierung: str, richtung: str, profil_id: str = "") -> Ordnung:
    """Die Ordnung zu den Angaben der Anfrage; eine unbekannte Sortierung gilt als Titel."""
    name = sortierung if sortierung in SORTIERUNGEN else VORGABE
    return Ordnung(name, SORTIERUNGEN[name], "DESC" if richtung.lower() == "desc" else "ASC", profil_id)


BANDORDNUNG = Ordnung("band", BANDFOLGE, "ASC")


class Eintrag(BaseModel):
    """Ein Eintrag der zusammengefassten Liste: ein Buch oder eine Sammlung."""

    art: Literal["buch", "sammlung"]
    nr: int                                     # Buch oder Sammlung
    name: str = ""                              # Sammlung: ihr Name
    anzahl: int = 0                             # Sammlung: ihre Bücher unter dem Filter
    autor: str = ""                             # Sammlung: ihr häufigster Autor unter dem Filter


class Zahlen(BaseModel):
    buecher: int                                # alle Bücher unter dem Filter
    sammlungen: int                             # davon zusammengefasste Sammlungen
    in_sammlungen: int                          # Bücher in diesen Sammlungen

    @property
    def eintraege(self) -> int:
        return self.buecher - self.in_sammlungen + self.sammlungen


def _vorab(where: str, o: Ordnung) -> str:
    """Die gefilterten Bücher mit ihrem Sortierschlüssel (k0, k1, ...) und die Sammlungen, die zusammengefasst werden."""
    schluessel = ", ".join(f"{t.ausdruck} AS k{i}" for i, t in enumerate(o.teile))
    return f"""gefiltert AS (SELECT b.id, b.sammlung_id, b.title, b.author, b.created_at, {schluessel}
                             FROM books b {o.verbindung} WHERE {where}),
               gruppen AS (SELECT sammlung_id AS id, COUNT(*) AS n FROM gefiltert WHERE sammlung_id IS NOT NULL
                           GROUP BY sammlung_id HAVING COUNT(*) >= ?)"""


# der häufigste Autor einer Sammlung unter dem Filter; ein leerer Autor nur, wenn keiner dasteht
HAEUFIGSTER_AUTOR = """(SELECT x.author FROM gefiltert x WHERE x.sammlung_id = c.id GROUP BY x.author
                        ORDER BY x.author = '', COUNT(*) DESC, x.author COLLATE NOCASE LIMIT 1)"""


def _schluessel_der_sammlung(o: Ordnung) -> list[str]:
    """Der Sortierschlüssel eines Sammlungseintrags, je Teil; `e` ist ihr erstes Buch in der Ordnung."""
    if o.name == "titel":
        return ["c.name"]
    if o.name == "datum":
        return ["(SELECT MAX(x.created_at) FROM gefiltert x WHERE x.sammlung_id = c.id)"]
    if o.name == "autor":
        return [HAEUFIGSTER_AUTOR]
    return [f"e.k{i}" for i in range(len(o.teile))]


async def zahlen(where: str, werte: tuple, ab: int) -> Zahlen:
    z = await db.fetch_one(f"""WITH {_vorab(where, ordnung(VORGABE, 'asc'))}
                               SELECT (SELECT COUNT(*) FROM gefiltert) AS buecher, (SELECT COUNT(*) FROM gruppen) AS sammlungen,
                                      (SELECT COALESCE(SUM(n), 0) FROM gruppen) AS in_sammlungen""", (*werte, ab))
    return Zahlen(**z) if z else Zahlen(buecher=0, sammlungen=0, in_sammlungen=0)


async def eintraege(where: str, werte: tuple, o: Ordnung, ab: int, anzahl: int, versatz: int) -> list[Eintrag]:
    """Eine Seite der zusammengefassten Liste in Anzeigereihenfolge."""
    k = [f"k{i}" for i in range(len(o.teile))]
    buch_schluessel = ", ".join(f"g.{s}" for s in k)
    sql = f"""WITH {_vorab(where, o)},
              erste AS (SELECT * FROM (SELECT g.*, ROW_NUMBER() OVER (PARTITION BY g.sammlung_id
                                                     ORDER BY {o.nach([f'g.{s}' for s in k])}, g.title COLLATE NOCASE, g.id) AS rang
                                       FROM gefiltert g WHERE g.sammlung_id IN (SELECT id FROM gruppen)) WHERE rang = 1),
              eintraege AS (
                  SELECT 'buch' AS art, g.id AS nr, g.title AS name, 0 AS anzahl, '' AS autor, {buch_schluessel} FROM gefiltert g
                  WHERE g.sammlung_id IS NULL OR g.sammlung_id NOT IN (SELECT id FROM gruppen)
                  UNION ALL
                  SELECT 'sammlung', c.id, c.name, (SELECT n FROM gruppen WHERE id = c.id), {HAEUFIGSTER_AUTOR},
                         {', '.join(f'{a} AS {s}' for a, s in zip(_schluessel_der_sammlung(o), k, strict=True))}
                  FROM erste e JOIN collections c ON c.id = e.sammlung_id)
              SELECT art, nr, name, anzahl, COALESCE(autor, '') AS autor FROM eintraege
              ORDER BY {o.nach(k)}, name COLLATE NOCASE, art, nr LIMIT ? OFFSET ?"""
    return [Eintrag(**z) for z in await db.fetch_all(sql, (*o.werte, *werte, ab, anzahl, versatz))]


async def stapel(where: str, werte: tuple, sammlungen: list[int], spalten: str) -> dict[int, list[dict]]:
    """Je Sammlung ihre ersten Bücher nach Band unter dem Filter (für die Umschläge des Eintrags)."""
    if not sammlungen:
        return {}
    ph = ",".join("?" * len(sammlungen))
    zeilen = await db.fetch_all(f"""SELECT * FROM (SELECT {spalten}, ROW_NUMBER() OVER (PARTITION BY b.sammlung_id
                                                                                       ORDER BY {BANDORDNUNG.sql()}) AS rang
                                                   FROM books b WHERE ({where}) AND b.sammlung_id IN ({ph}))
                                    WHERE rang <= ? ORDER BY sammlung_id, rang""", (*werte, *sammlungen, STAPEL))
    je: dict[int, list[dict]] = {}
    for z in zeilen:
        z.pop("rang")
        je.setdefault(z["sammlung_id"], []).append(z)
    return je
