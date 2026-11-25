"""Open Library: offene Bibliotheksdatenbank mit Umschlägen. Nach ISBN über /api/books (mehrere auf einmal möglich), nach Titel
über die Suche mit der passenden Ausgabe statt irgendeiner."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from backend.app.quellen import isbn as nummern
from backend.app.quellen import regeln
from backend.app.quellen.abgleich import bester, haupttitel, suchbar
from backend.app.quellen.abruf import Frage, abruf, hole
from backend.app.quellen.anschluss import OhneDoi
from backend.app.quellen.fehler import QuelleFehler
from backend.app.quellen.modelle import Angaben, Buchfrage
from backend.app.quellen.sprache import kuerzel

BUECHER = "https://openlibrary.org/api/books"
SUCHE = "https://openlibrary.org/search.json"
UMSCHLAG = "https://covers.openlibrary.org/b"
SAMMEL_HOECHSTENS = 40
KATEGORIEN_HOECHSTENS = 12
_FELDER = ("key,title,subtitle,author_name,first_publish_year,cover_i,language,subject,editions,editions.key,editions.title,editions.subtitle,editions.isbn,editions.publisher,"
           "editions.publish_date,editions.language,editions.cover_i")
_KEIN_THEMA = re.compile(r"^(series:|reading level|open_syllabus|long now manual|nyt:|pr\d{4}|collectionid:|new york times|accessible book|protected daisy|in library|internet archive|our brockhaus|\d)", re.IGNORECASE)
_NAMENSLISTEN = ("subjects", "subject_places", "subject_people", "subject_times")


def _nfc(text: Any) -> str:
    return unicodedata.normalize("NFC", text).strip() if isinstance(text, str) else ""


def _namen(liste: Any) -> list[str]:
    return [n for e in liste or [] if (n := _nfc(e.get("name") if isinstance(e, dict) else e))]


def _themen(namen: list[str]) -> list[str]:
    """Die ersten Themen ohne Verwaltungswörter; die ganze Liste steht bei den Rohdaten."""
    einmal = {n.lower(): n for n in reversed(namen) if not _KEIN_THEMA.match(n)}
    return list(dict.fromkeys(einmal[n.lower()] for n in namen if n.lower() in einmal))[:KATEGORIEN_HOECHSTENS]


def _jahr(datum: Any) -> int | None:
    treffer = re.search(r"\b(\d{4})\b", str(datum or "").replace("?", ""))
    return int(treffer.group(1)) if treffer else None


def aus_buch(buch: dict[str, Any], isbn: str) -> Angaben:
    """Antwort von /api/books mit jscmd=data."""
    kennungen = buch.get("identifiers") or {}
    isbns = list(dict.fromkeys([*nummern.formen(isbn)[:1], *(nummern.sauber(n) for art in ("isbn_13", "isbn_10") for n in kennungen.get(art, []))]))
    roh = {k: w for k, w in buch.items() if k not in _NAMENSLISTEN} | {k: n for k in _NAMENSLISTEN if (n := _namen(buch.get(k)))}
    roh["excerpts"] = [_nfc(e.get("text")) for e in buch.get("excerpts", [])]
    return Angaben(quelle=regeln.OPEN_LIBRARY.kennung, fund="isbn", titel=_nfc(buch.get("title")), untertitel=_nfc(buch.get("subtitle")), autoren=_namen(buch.get("authors")),
                   verlag=next(iter(_namen(buch.get("publishers"))), ""), jahr=_jahr(buch.get("publish_date")), seiten=buch.get("number_of_pages") or 0, isbn=isbns[0] if isbns else "", isbns=isbns,
                   kategorien=_themen(_namen(buch.get("subjects"))), umschlag=(buch.get("cover") or {}).get("large", ""), roh={k: w for k, w in roh.items() if w})


def aus_suche(werk: dict[str, Any]) -> Angaben:
    """Ein Werk der Suche mit der Ausgabe, die zur Frage passt; ohne Ausgabe bleiben ISBN und Verlag leer."""
    ausgabe = next(iter((werk.get("editions") or {}).get("docs", [])), {})
    isbns = [n for n in (nummern.sauber(i) for i in ausgabe.get("isbn", [])) if n]
    bild = ausgabe.get("cover_i") or werk.get("cover_i")
    sprachen = ausgabe.get("language") or []
    return Angaben(quelle=regeln.OPEN_LIBRARY.kennung, titel=_nfc(ausgabe.get("title") or werk.get("title")), untertitel=_nfc(ausgabe.get("subtitle") or ""),
                   autoren=[_nfc(a) for a in werk.get("author_name", [])], verlag=_nfc(next(iter(ausgabe.get("publisher", [])), "")),
                   jahr=_jahr(next(iter(ausgabe.get("publish_date", [])), "")) or (None if ausgabe else werk.get("first_publish_year")), isbn=isbns[0] if isbns else "", isbns=isbns,
                   sprache=kuerzel(sprachen[0]) if sprachen else "", kategorien=_themen([_nfc(s) for s in werk.get("subject", [])]),
                   umschlag=f"{UMSCHLAG}/id/{bild}-L.jpg" if isinstance(bild, int) and bild > 0 else "", roh={k: werk[k] for k in ("key", "first_publish_year", "subject") if werk.get(k)})


class OpenLibrary(OhneDoi):
    regel = regeln.OPEN_LIBRARY

    def _frage(self, isbn: str) -> Frage:
        return Frage(BUECHER, (("bibkeys", f"ISBN:{isbn}"), ("format", "json"), ("jscmd", "data")), ist_leer=lambda w: not w, verdichte=lambda w: next(iter(w.values())))

    async def nach_isbn(self, isbn: str) -> Angaben | None:
        formen = nummern.formen(isbn)
        buch = await hole(self.regel, self._frage(formen[0])) if formen else None
        return aus_buch(buch, isbn) if buch else None

    async def vorwaermen(self, isbns: list[str]) -> None:
        """Viele ISBN mit einer Anfrage in den Vorrat holen (für lange Läufe), statt jede einzeln zu fragen."""
        offen = [n for n in dict.fromkeys(nummern.dreizehn(i) for i in isbns) if n and not await abruf().bekannt(self._frage(n))]
        for ab in range(0, len(offen), SAMMEL_HOECHSTENS):
            teil = offen[ab:ab + SAMMEL_HOECHSTENS]
            frage = Frage(BUECHER, (("bibkeys", ",".join(f"ISBN:{n}" for n in teil)), ("format", "json"), ("jscmd", "data")))
            antwort = await hole(self.regel, frage) or {}
            for n in teil:
                buch = antwort.get(f"ISBN:{n}")
                await abruf().merke(self.regel, self._frage(n), {f"ISBN:{n}": buch} if buch else None)

    async def nach_titel(self, frage: Buchfrage) -> Angaben | None:
        titel = haupttitel(frage.titel)
        if not suchbar(titel):
            return None
        felder = [("title", titel), ("limit", "5"), ("fields", _FELDER)]
        if frage.autoren:
            felder.append(("author", frage.autoren[0]))
        if frage.sprache:
            felder.append(("lang", frage.sprache))
        werke = await hole(self.regel, Frage(SUCHE, tuple(felder), ist_leer=lambda w: not w["docs"], verdichte=lambda w: w["docs"])) or []
        return bester(frage, [aus_suche(w) for w in werke])

    async def umschlag(self, isbn: str) -> str:
        """Adresse des Umschlags zu einer ISBN, wenn es einen gibt."""
        n = nummern.dreizehn(isbn)
        if not n:
            return ""
        adresse = f"{UMSCHLAG}/isbn/{n}-L.jpg?default=false"
        return adresse if await hole(regeln.OPEN_LIBRARY_BILDER, Frage(adresse, methode="HEAD")) else ""

    async def probe(self) -> None:
        await hole(self.regel, self._frage("9783257229530"), probe=True)


async def umschlag_oder_nichts(isbn: str) -> str:
    try:
        return await OpenLibrary().umschlag(isbn) if isbn and not regeln.OPEN_LIBRARY.hindernis else ""
    except QuelleFehler:
        return ""
