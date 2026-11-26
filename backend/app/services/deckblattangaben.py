"""Was Treffer und Werke brauchen, um ihr Deckblatt zu zeigen (BF-59): Art, Gattung, Wahl, Befund, Umschlagdatei, Jahr.

Suche, Suche nach Bedeutung und Autorenseite liefern Bücher in eigener Form; sie hängen diese Angaben an, damit überall
dasselbe Deckblatt erscheint wie in der Bücherliste. Die Rechnung des Umschlags steht im Modell (models/book.py)."""

from __future__ import annotations

from backend.app.core.database import db
from backend.app.models.book import Deckblatt


async def fuer(nummern: list[int]) -> dict[int, Deckblatt]:
    """Die Angaben je Buch, in einer Abfrage; unbekannte Nummern fehlen im Ergebnis."""
    if not nummern:
        return {}
    platz = ",".join("?" * len(set(nummern)))
    zeilen = await db.fetch_all(
        f"SELECT id, typ, gattung, umschlag_wahl, umschlag_schlicht, cover_path, file_format, year FROM books WHERE id IN ({platz})",
        tuple(set(nummern)))
    return {z["id"]: Deckblatt(**{k: z[k] for k in z.keys() if k != "id" and z[k] is not None}) for z in zeilen}
