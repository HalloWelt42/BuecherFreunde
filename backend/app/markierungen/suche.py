"""Wortsuche in den eigenen Markierungen (BF-123): ihr Text, auch der über ein Rechteck gelesene, gehört dem Profil allein und
steht darum nicht im Index der Bücher. Gesucht wird nach den Wörtern der Anfrage (dieselbe Schreibweise wie die Suche in den
Büchern, services/query_parser.py), jedes muss vorkommen, nur in Büchern, die die Sicht sieht (BF-78). Ein Treffer nennt das Buch,
die Stelle und die Seite; der Auszug hebt das erste Wort hervor."""

from __future__ import annotations

import html
import re

from pydantic import BaseModel

from backend.app.core.database import db
from backend.app.familie.sichtbar import Sicht
from backend.app.services.query_parser import parse_query

AUSZUG_UM = 60                       # so viele Zeichen vor und nach dem Wort zeigt der Auszug
FTS_WOERTER = {"AND", "OR", "NOT", "NEAR"}


class Markierungstreffer(BaseModel):
    """Ein Treffer der Wortsuche in einer Markierung des Profils."""
    markierung_id: int
    buch_id: int
    titel: str
    autor: str
    stelle: str
    seite: int | None
    auszug: str


def woerter(q: str) -> list[str]:
    """Die Wörter der Anfrage ohne Filter, Anführungszeichen und Verknüpfungen."""
    return [w for w in re.findall(r"\w+", parse_query(q).fts_query) if w not in FTS_WOERTER]


def auszug(text: str, wort: str) -> str:
    """Ein Stück um das erste Vorkommen, sicher als HTML, das Wort in <mark>."""
    i = text.lower().find(wort.lower())
    if i < 0:
        return html.escape(text[: 2 * AUSZUG_UM])
    von, bis = max(0, i - AUSZUG_UM), min(len(text), i + len(wort) + AUSZUG_UM)
    vorn, mitte, hinten = text[von:i], text[i : i + len(wort)], text[i + len(wort) : bis]
    return f"{'...' if von else ''}{html.escape(vorn)}<mark>{html.escape(mitte)}</mark>{html.escape(hinten)}{'...' if bis < len(text) else ''}"


def _wie(wort: str) -> str:
    return "%" + wort.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def suchen(q: str, profil: str, sicht: Sicht, anzahl: int = 20) -> list[Markierungstreffer]:
    gesucht = woerter(q)
    if not gesucht:
        return []
    bedingung, werte = sicht.bedingung("b.id")
    passt = " AND ".join("h.text_snippet LIKE ? ESCAPE '\\'" for _ in gesucht)
    zeilen = await db.fetch_all(f"""SELECT h.id, h.book_id, h.cfi_range, h.text_snippet, b.title, b.author FROM book_highlights h
                                    JOIN books b ON b.id = h.book_id WHERE h.profil_id = ? AND {passt} AND {bedingung}
                                    ORDER BY h.created_at DESC LIMIT ?""", (profil, *map(_wie, gesucht), *werte, anzahl))
    treffer = []
    for z in zeilen:
        seite = re.match(r"^page:(\d+)", z["cfi_range"])
        treffer.append(Markierungstreffer(markierung_id=z["id"], buch_id=z["book_id"], titel=z["title"], autor=z["author"],
                                          stelle=z["cfi_range"], seite=int(seite.group(1)) if seite else None,
                                          auszug=auszug(z["text_snippet"], gesucht[0])))
    return treffer
