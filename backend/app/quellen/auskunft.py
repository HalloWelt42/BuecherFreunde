"""Auskunft zu einem Buch: eine Quelle fragen, alle fragen und je Feld das Beste nehmen, oder im Hintergrund nur so viele
fragen, bis das Fehlende da ist."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from pydantic import BaseModel, Field

from backend.app.quellen import isbn as nummern
from backend.app.quellen import open_library, regeln
from backend.app.quellen.abgleich import gleiche_ausgabe, punkte
from backend.app.quellen.anschluss import Buchquelle
from backend.app.quellen.crossref import Crossref
from backend.app.quellen.dnb import Nationalbibliothek
from backend.app.quellen.fehler import QuelleFehler, ruhig
from backend.app.quellen.google_books import GoogleBooks
from backend.app.quellen.k10plus import Verbundkatalog
from backend.app.quellen.lexikon import Lexikon
from backend.app.quellen.modelle import FELDER, Angaben, Buchfrage
from backend.app.quellen.open_library import OpenLibrary

logger = logging.getLogger("buecherfreunde.quellen.auskunft")
ALLE = "alle"
QUELLEN: dict[str, Buchquelle] = {q.regel.kennung: q for q in (GoogleBooks(), OpenLibrary(), Nationalbibliothek(), Verbundkatalog(), Crossref(), Lexikon())}
NACHEINANDER = ("dnb", "google_books", "open_library", "k10plus", "crossref", "wikipedia")
KATALOGE = ("dnb", "k10plus", "google_books", "open_library", "crossref", "wikipedia")
# Wessen Angabe gilt, wenn mehrere eine haben
VORRANG: dict[str, tuple[str, ...]] = {
    "titel": ("dnb", "k10plus", "crossref", "google_books", "open_library", "wikipedia"), "untertitel": ("dnb", "k10plus", "crossref", "google_books", "open_library", "wikipedia"),
    "doi": ("crossref", "k10plus", "dnb"), "beschreibung": ("google_books", "k10plus", "crossref", "wikipedia", "open_library", "dnb"),
    "kategorien": ("dnb", "k10plus", "google_books", "wikipedia", "open_library", "crossref"), "umschlag": ("google_books", "open_library"),
}
DER_AUSGABE = {"verlag", "jahr", "seiten", "isbn", "doi", "umschlag"}      # darf nicht aus verschiedenen Ausgaben gemischt werden


class Auskunft(BaseModel):
    angaben: Angaben | None = None
    hinweise: list[str] = Field(default_factory=list)      # Quellen, die gerade nicht antworten, mit Grund
    ruht: bool = False                                     # alle gefragten Quellen haben Pause oder die Tagesgrenze erreicht


def aktive() -> list[Buchquelle]:
    return [QUELLEN[k] for k in NACHEINANDER if not QUELLEN[k].regel.hindernis]


async def frage_eine(quelle: Buchquelle, frage: Buchfrage) -> Angaben | None:
    """ISBN, dann DOI, dann Titel und Autor. Wirft QuelleFehler."""
    fund = await quelle.nach_isbn(frage.isbn) if frage.isbn else None
    if fund is None and frage.doi:
        fund = await quelle.nach_doi(frage.doi)
    if fund is None and frage.titel:
        fund = await quelle.nach_titel(frage)
    return fund and _mit_herkunft(fund, frage)


def _mit_herkunft(a: Angaben, frage: Buchfrage) -> Angaben:
    """Herkunft je gefülltem Feld; die ISBN des Buchs behält ihre Schreibweise."""
    eigene = {"isbn": frage.isbn} if frage.isbn and any(nummern.gleich(frage.isbn, n) for n in (a.isbn, *a.isbns)) else {}
    neu = a.model_copy(update=eigene)
    return neu.model_copy(update={"herkunft": {f: a.quelle for f in FELDER if getattr(neu, f)}})


async def _versuche(quelle: Buchquelle, frage: Buchfrage) -> tuple[Angaben | None, QuelleFehler | None]:
    try:
        return await frage_eine(quelle, frage), None
    except QuelleFehler as f:
        logger.info("%s", f.grund)
        return None, f


def _auskunft(angaben: Angaben | None, fehler: Iterable[QuelleFehler | None]) -> Auskunft:
    """`fehler` hat je gefragter Quelle einen Platz, None heißt: sie hat geantwortet."""
    gefragt = list(fehler)
    echte = [f for f in gefragt if f is not None]
    return Auskunft(angaben=angaben, hinweise=list(dict.fromkeys(f.grund for f in echte)), ruht=bool(gefragt) and len(echte) == len(gefragt) and all(ruhig(f) for f in echte))


async def suche(frage: Buchfrage, kennung: str | None = None) -> Auskunft:
    """Eine Quelle (kennung), alle zusammen ("alle") oder die erste, die etwas weiß (ohne Angabe)."""
    if kennung and kennung != ALLE:
        fund, fehler = await _versuche(QUELLEN[kennung], frage)
        return _auskunft(fund, [fehler])
    if kennung == ALLE:
        ergebnisse = await asyncio.gather(*(_versuche(q, frage) for q in aktive()))      # verschiedene Rechner, je eine Anfrage
        fund = zusammenfuehren([a for a, _ in ergebnisse if a], frage)
        if fund and not fund.umschlag and (bild := await open_library.umschlag_oder_nichts(fund.isbn or frage.isbn)):
            fund = fund.model_copy(update={"umschlag": bild, "herkunft": {**fund.herkunft, "umschlag": regeln.OPEN_LIBRARY.kennung}})
        return _auskunft(fund, [f for _, f in ergebnisse])
    fehler = []
    for quelle in aktive():
        fund, f = await _versuche(quelle, frage)
        fehler.append(f)
        if fund:
            return _auskunft(fund, fehler)
    return _auskunft(None, fehler)


def _beste(feld: str, leitend: list[Angaben], uebrige: list[Angaben]) -> Angaben | None:
    """Wessen Angabe in diesem Feld gilt: die Funde der richtigen Ausgabe zuerst, dann nach dem Vorrang der Quellen."""
    rang = VORRANG.get(feld, KATALOGE)
    for gruppe in (leitend, [] if feld in DER_AUSGABE else uebrige):
        gefuellt = [a for a in gruppe if getattr(a, feld)]
        if gefuellt:
            return min(gefuellt, key=lambda a: rang.index(a.quelle) if a.quelle in rang else len(rang))
    return None


def zusammenfuehren(funde: list[Angaben], frage: Buchfrage) -> Angaben | None:
    """Je Feld die Angabe der besten Quelle. Was zur Ausgabe gehört, kommt nur von Funden über die ISBN, sonst von einem einzigen."""
    if not funde:
        return None
    leitend = [a for a in funde if a.fund in ("isbn", "doi")] or [max(funde, key=lambda a: punkte(frage, a))]
    uebrige = [a for a in funde if not any(a is x for x in leitend)]
    beste = {f: a for f in FELDER if (a := _beste(f, leitend, uebrige))}
    roh = {f"{regeln.REGELN[a.quelle].name}, {k}": w for a in funde for k, w in a.roh.items()}
    personen = {k: w for a in reversed(funde) for k, w in a.personen.items()}
    return Angaben(**{f: getattr(a, f) for f, a in beste.items()}, quelle=ALLE, fund=leitend[0].fund, sicher=all(a.sicher for a in leitend), isbns=[n for a in leitend for n in a.isbns],
                   herkunft={f: a.quelle for f, a in beste.items()}, personen=personen, roh=roh)


# -- Hintergrund -------------------------------------------------------------------------------------------------------
def _reihenfolge(frage: Buchfrage) -> list[Buchquelle]:
    """Deutsche ISBN zuerst bei der Nationalbibliothek; fremde kennt sie selten, dort steht sie nicht auf dem Weg."""
    deutsch = nummern.deutschsprachig(frage.isbn) or (not frage.isbn and frage.sprache in ("", "de"))
    kennungen = ("dnb", "open_library", "k10plus", "google_books", "crossref") if deutsch else ("open_library", "k10plus", "google_books", "crossref")
    return [QUELLEN[k] for k in kennungen if not QUELLEN[k].regel.hindernis]


def _nur_werk(a: Angaben) -> Angaben:
    """Ein Fund ohne das, was nur für eine bestimmte Ausgabe gilt."""
    return a.model_copy(update={f: Angaben.model_fields[f].get_default(call_default_factory=True) for f in DER_AUSGABE})


async def _sicherer_fund(quelle: Buchquelle, frage: Buchfrage) -> Angaben | None:
    """Mit ISBN zählt nur die ISBN. Ohne sie muss der Titel sicher sein, und Verlag, Jahr und ISBN gelten nur für dieselbe Ausgabe."""
    if frage.isbn:
        return await quelle.nach_isbn(frage.isbn)
    fund = await quelle.nach_titel(frage)
    if fund is None or not fund.sicher:
        return None
    return fund.model_copy(update={"fund": "isbn"}) if fund.isbn and gleiche_ausgabe(frage, fund) else _nur_werk(fund)


async def ergaenze(frage: Buchfrage, fehlend: set[str]) -> Auskunft:
    """Nur das Fehlende, mit so wenigen Anfragen wie möglich."""
    funde: list[Angaben] = []
    fehler: list[QuelleFehler | None] = []
    offen = set(fehlend)
    for quelle in _reihenfolge(frage):
        if not offen:
            break
        try:
            fund = await _sicherer_fund(quelle, frage)
            fehler.append(None)
        except QuelleFehler as f:
            fund = None
            fehler.append(f)
        if fund:
            frage = frage.model_copy(update={"isbn": frage.isbn or fund.isbn})      # ab hier genau diese Ausgabe
            funde.append(_mit_herkunft(fund, frage))
            offen -= {f for f in offen if getattr(fund, f)}
    angaben = zusammenfuehren(funde, frage)
    if "umschlag" in offen and (bild := await open_library.umschlag_oder_nichts(frage.isbn)):
        angaben = (angaben or Angaben()).model_copy(update={"umschlag": bild})
    return _auskunft(angaben, fehler)
