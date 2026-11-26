"""Was Regeln und KI über ein Werk wissen (BF-69): Titel, Autor, Verlag, Art und der Anfang der Beschreibung aus `books`,
dazu die Schlagworte.

Schlagworte und Sachgruppen der Quellen landen beim Ergänzen als Regale am Buch (`quellen/marc.py`, `api/metadata.py`);
die Begleitdatei `metadata.json` hält sie nicht. Deshalb gelten die Namen der Regale eines Buchs (ohne "Ungeordnet") als
seine Schlagworte, und ein Name, der eine Sachgruppe der Nationalbibliografie ist ("Informatik", "Belletristik"), gibt
ihm deren Nummer (`quellen/sachgruppen.py`)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.core.database import db
from backend.app.katalog.regeln import Suchtext, suchtext
from backend.app.quellen.sachgruppen import NAMEN

BESCHREIBUNG_ZEICHEN = 300                     # so viel vom Anfang der Beschreibung bekommt die KI
TRENNER = "\x1f"
NUMMER_ZU = {name.casefold(): nummer for nummer, name in NAMEN.items()}
# Kategorien des Katalogs, in denen ein Buch steht
IN_KATEGORIE = ("EXISTS (SELECT 1 FROM book_categories x JOIN categories c ON c.id = x.category_id "
                "WHERE x.book_id = b.id AND c.art = 'kategorie')")
SPALTEN = f"""b.id, b.title AS titel, b.author AS autor, COALESCE(b.publisher, '') AS verlag, COALESCE(b.typ, '') AS typ,
              substr(COALESCE(b.description, ''), 1, {BESCHREIBUNG_ZEICHEN}) AS beschreibung,
              COALESCE((SELECT group_concat(c.name, char(31)) FROM book_categories x JOIN categories c ON c.id = x.category_id
                        WHERE x.book_id = b.id AND c.art = 'regal' AND c.slug != 'ungeordnet'), '') AS regale"""


def nur_arten(arten: list[str]) -> tuple[str, tuple]:
    """Bedingung für Werke dieser Arten (books.typ, leer: Buch)."""
    if not arten:
        return "0", ()
    return f"COALESCE(b.typ, '') IN ({','.join('?' * len(arten))})", tuple(arten)


def sachgruppen_aus(namen: list[str]) -> list[str]:
    """Die Nummern der Sachgruppen, deren Namen unter den Schlagworten stehen."""
    return list(dict.fromkeys(NUMMER_ZU[n.casefold()] for n in namen if n.casefold() in NUMMER_ZU))


class Buchmerkmale(BaseModel):
    id: int
    titel: str = ""
    autor: str = ""
    verlag: str = ""
    typ: str = ""                              # die Art des Werks, leer: ein Buch
    beschreibung: str = ""                     # der Anfang
    schlagworte: list[str] = Field(default_factory=list)

    @property
    def sachgruppen(self) -> list[str]:
        return sachgruppen_aus(self.schlagworte)

    def suchtext(self) -> Suchtext:
        return suchtext(self.titel, self.verlag, self.schlagworte, self.sachgruppen)


def _merkmale(z: dict) -> Buchmerkmale:
    schlagworte = [s for s in (z.pop("regale") or "").split(TRENNER) if s]
    return Buchmerkmale(**{k: v or "" for k, v in z.items() if k != "id"}, id=z["id"], schlagworte=schlagworte)


async def laden(wo: str = "1", werte: tuple = (), anzahl: int | None = None) -> list[Buchmerkmale]:
    """Die Merkmale der Bücher, die `wo` trifft (Bedingung aus dem Code über `b`), nach Nummer."""
    grenze = f" LIMIT {int(anzahl)}" if anzahl else ""
    zeilen = await db.fetch_all(f"SELECT {SPALTEN} FROM books b WHERE {wo} ORDER BY b.id{grenze}", werte)
    return [_merkmale(z) for z in zeilen]
