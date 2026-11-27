"""ISBN-Suche in einem gespeicherten Buch und Prüfen einer ISBN bei den Quellen, für das Fenster "ISBN im Buch" (BF-111)."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.app.core.database import db
from backend.app.isbnsuche import wahl
from backend.app.isbnsuche.kandidaten import als_seiten, aus_quelle, kandidaten
from backend.app.isbnsuche.modelle import Isbnpruefung, Isbnsuche
from backend.app.quellen import auskunft
from backend.app.quellen import isbn as nummern
from backend.app.quellen.abgleich import isbn_abgleich
from backend.app.quellen.modelle import Buchfrage
from backend.app.services import volltext
from backend.app.services.autorennamen import zerlegen
from backend.app.services.seiten import buch_seiten
from backend.app.services.storage import get_original_file, load_fulltext

SPALTEN = "id, hash, isbn, title, author, file_format, page_count"


class KeinBuch(LookupError):
    pass


class KeineIsbn(ValueError):
    pass


def frage_aus(buch: Mapping[str, Any]) -> Buchfrage:
    """Titel und Autoren des Buchs, gegen die jede ISBN geprüft wird."""
    return Buchfrage(titel=buch.get("title") or "", autoren=zerlegen(buch.get("author") or ""))


async def buch(buch_id: int) -> dict:
    zeile = await db.fetch_one(f"SELECT {SPALTEN} FROM books WHERE id = ?", (buch_id,))
    if not zeile:
        raise KeinBuch("Buch nicht gefunden")
    return zeile


def _seiten(b: Mapping[str, Any], seitenzahl: int | None) -> list[str]:
    """Ein PDF in seinen Dateiseiten wie im Leser (services/seiten.py); andere Formate in Stücken, die nur am Zeilenende enden."""
    if (b["file_format"] or "").lower() == "pdf":
        return buch_seiten(b["hash"], b["file_format"], seitenzahl)[0]
    return als_seiten(load_fulltext(b["hash"]) or "", seitenzahl)


async def seiten(b: Mapping[str, Any], original: Path | None = None) -> list[str]:
    """Der Text des Buchs je Seite; fehlt er, wird er erst aus der Datei gelesen (`original`, wenn sie schon geholt ist)."""
    texte = await asyncio.to_thread(_seiten, b, b["page_count"])
    if any(t.strip() for t in texte):
        return texte
    original = original or await asyncio.to_thread(get_original_file, b["hash"])        # kann aus der Kellerwolke laden
    if original is None or not await volltext.nachlesen(b["id"], b["hash"], original):
        return []
    zeile = await db.fetch_one("SELECT page_count FROM books WHERE id = ?", (b["id"],))     # das Lesen trägt eine fehlende Seitenzahl nach
    return await asyncio.to_thread(_seiten, b, zeile["page_count"] if zeile else None)


async def im_buch(buch_id: int) -> Isbnsuche:
    """Alle ISBN des Buchs als Kandidaten in der Rangfolge, mit dem, was ein Lauf bei den Quellen schon erfahren hat."""
    b = await buch(buch_id)
    texte = await seiten(b)
    liste = await asyncio.to_thread(kandidaten, texte, frage_aus(b))
    liste = await wahl.mit_pruefungen(buch_id, liste)
    return Isbnsuche(kandidaten=liste, funde=sum(k.funde for k in liste), aktuell=b["isbn"] or "", seiten=len(texte))


async def frage_quellen(frage: Buchfrage, isbn13: str) -> tuple[Isbnpruefung, bool]:
    """Die Quellen der Reihe nach über die ISBN, bis eine sie kennt (wie die Suche ohne gewählte Quelle); die Antworten merkt der
    gemeinsame Abruf, "Angaben suchen" fragt danach nicht noch einmal. Zweiter Wert: ob eine Quelle geantwortet hat."""
    antwort = await auskunft.suche(Buchfrage(isbn=isbn13), nur_isbn=True)
    einstufung = aus_quelle(isbn_abgleich(frage, antwort.angaben), antwort.angaben) if antwort.angaben else None
    pruefung = Isbnpruefung(isbn=nummern.mit_strichen(isbn13) or isbn13, einstufung=einstufung, hinweise=antwort.hinweise, ruht=antwort.ruht)
    return pruefung, antwort.angaben is not None or not antwort.ruht


async def pruefe(buch_id: int, isbn: str) -> Isbnpruefung:
    """Eine ISBN gegen Titel und Autor des Buchs, nach dem, was die Quellen zu ihr nennen."""
    if not nummern.gueltig(isbn):
        raise KeineIsbn("Das ist keine gültige ISBN")
    b = await buch(buch_id)
    pruefung, _gefragt = await frage_quellen(frage_aus(b), nummern.dreizehn(isbn))
    return pruefung
