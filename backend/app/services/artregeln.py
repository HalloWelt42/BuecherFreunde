"""Feste Regeln für die Art eines Werks (BF-77): ein Buch (books.typ leer), eine Anleitung oder ein Dokument, je mit kurzer
Begründung. Was keine Regel sicher sagt, bestimmt danach die lokale KI (services/einordnung.py).

1. Buch: eine ISBN und mehr als `EINORDNEN_BUCH_AB_SEITEN` (40) Seiten. Nur, wenn der Umschlag sicher nicht schlicht ist:
   für ein gezeichnetes Deckblatt braucht ein Buch eine Gattung, die nur die KI bestimmt.
2. Anleitung, nur ohne ISBN (BF-80): Titel oder Dateiname nennt eine Anleitung (Bedienungsanleitung, Gebrauchsanweisung,
   Gebrauchsanleitung, Montageanleitung, Aufbauanleitung, Bauanleitung, Kurzanleitung, Benutzerhandbuch, user manual,
   owner's manual, instruction manual, quick start guide, installation guide), am Wortanfang, Groß und klein gleich.
3. Dokument, nur ohne ISBN: Titel oder Dateiname nennt das Programm, aus dem das Dokument stammt ("Microsoft Word - ...",
   Endungen .docx, .pptx, .xlsx), oder ein Wort, das ein Schriftstück verrät (Rechnung, Beleg, Datenblatt, datasheet, Folien,
   slides, lecture), jeweils am Wortanfang, Groß und klein gleich.
4. Dokument: höchstens `EINORDNEN_DOKUMENT_BIS_SEITEN` (4) Seiten und keine ISBN.

Eine Art, die der Nutzer gesetzt hat, fasst keine Regel an; das entscheidet, wer die Regeln anwendet."""

from __future__ import annotations

import re

from pydantic import BaseModel

from backend.app.core.config import settings

PROGRAMM = re.compile(r"^\s*microsoft\s+(?:office\s+)?(word|powerpoint|excel)\s*-", re.I)
PROGRAMME = {"word": "einem Schreibprogramm", "powerpoint": "einem Folienprogramm", "excel": "einer Tabellenkalkulation"}
ENDUNG = re.compile(r"\.(docx?|pptx?|xlsx?)(?!\w)", re.I)
ANLEITUNG = re.compile(r"(?<!\w)(bedienungsanleitung|gebrauchsanweisung|gebrauchsanleitung|montageanleitung|aufbauanleitung|bauanleitung|"
                       r"kurzanleitung|benutzerhandbuch|user\s+manual|owner'?s\s+manual|instruction\s+manual|quick\s+start\s+guide|"
                       r"installation\s+guide)", re.I)
SCHRIFTSTUECK = re.compile(r"(?<!\w)(rechnung|beleg|datenblatt|datasheet|folien|slides|lecture)", re.I)


class Werk(BaseModel):
    """Was die Regeln und die KI über ein Werk erfahren (dazu der Anfang des Volltexts)."""

    id: int
    hash: str
    title: str = ""
    author: str = ""
    publisher: str | None = ""
    year: int | None = None
    isbn: str | None = ""
    file_format: str = ""
    file_name: str = ""
    page_count: int | None = 0
    umschlag_schlicht: int | None = None        # NULL: noch nicht geprüft

    @property
    def hat_isbn(self) -> bool:
        return bool((self.isbn or "").strip())

    @property
    def seiten(self) -> int:
        return self.page_count or 0

    @property
    def gattung_gefragt(self) -> bool:
        """Ob das gezeichnete Deckblatt die Gattung braucht: der Umschlag ist schlicht."""
        return self.umschlag_schlicht == 1


class Regelurteil(BaseModel):
    typ: str                                    # leer: ein Buch
    grund: str


def _im_namen(muster: re.Pattern[str], w: Werk) -> tuple[re.Match[str], str] | None:
    """Der erste Treffer im Titel, sonst im Dateinamen (Unterstriche wie Leerzeichen), und wo er stand."""
    for text, wo in ((w.title, "Titel"), (w.file_name.replace("_", " "), "Dateinamen")):
        if t := muster.search(text or ""):
            return t, wo
    return None


def urteil(w: Werk) -> Regelurteil | None:
    """Die Art nach den festen Regeln, oder None, wenn keine sicher ist."""
    if w.hat_isbn:
        if w.seiten > settings.einordnen_buch_ab_seiten and w.umschlag_schlicht == 0:
            return Regelurteil(typ="", grund=f"ISBN und {w.seiten} Seiten")
        return None
    if gefunden := _im_namen(ANLEITUNG, w):
        t, wo = gefunden
        return Regelurteil(typ="anleitung", grund=f"\"{t.group(1)}\" im {wo}, keine ISBN")
    if t := PROGRAMM.search(w.title or ""):
        return Regelurteil(typ="dokument", grund=f"Der Titel stammt aus {PROGRAMME[t.group(1).lower()]}")
    if gefunden := _im_namen(ENDUNG, w):
        t, wo = gefunden
        return Regelurteil(typ="dokument", grund=f"Endung .{t.group(1).lower()} im {wo}")
    if gefunden := _im_namen(SCHRIFTSTUECK, w):
        t, wo = gefunden
        return Regelurteil(typ="dokument", grund=f"\"{t.group(1)}\" im {wo}, keine ISBN")
    if 0 < w.seiten <= settings.einordnen_dokument_bis_seiten:
        return Regelurteil(typ="dokument", grund=f"{w.seiten} {'Seite' if w.seiten == 1 else 'Seiten'} und keine ISBN")
    return None
