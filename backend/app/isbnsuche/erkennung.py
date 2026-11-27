"""Jede ISBN im Text eines Buchs, in der Reihenfolge des Buchs, mit Seite, Lage, Schreibweise und dem Merkmal Druck oder E-Book.

Erkannt wird mit Wortgrenzen (keine Nummer mitten aus einer längeren Zahl) und nur mit stimmender Prüfziffer. Zwischen zwei
Ziffern darf ein Trennzeichen stehen (Strich, Leerzeichen), so zählt auch die Zeile unter dem Strichcode ("9 783999 991016").
Eine ISBN-13 beginnt mit 978 oder 979; eine ISBN-10 zählt nur mit "ISBN" davor oder in der üblichen Schreibweise mit drei
Strichen, sonst wäre jede zehnstellige Zahl mit passender Prüfziffer eine (Telefon, Bestellnummer)."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from backend.app.isbnsuche.modelle import Ausgabe
from backend.app.quellen import isbn as nummern

_TRENNER = r"[ \-\u2010\u2011\u2012\u2013\u00a0\u2009\u202f]"      # Strich, Leerzeichen, auch die typografischen
_STRICH = r"[\-\u2010\u2011]"
_VORN = rf"(?<!\d)(?<!\d{_STRICH})"         # keine Ziffer davor, auch nicht mit Strich dazwischen
_HINTEN = rf"(?!\d)(?!{_STRICH}\d)"
_ISBN13 = re.compile(rf"{_VORN}(?:\d{_TRENNER}?){{12}}\d{_HINTEN}")
_ISBN10 = re.compile(rf"{_VORN}(?:\d{_TRENNER}?){{9}}[\dXx]{_HINTEN}")
_MARKE_DAVOR = re.compile(r"isbn(?:[\s-]*1[03])?\s*[:.]?\s*$", re.IGNORECASE)
_MARKE_REICHWEITE = 16                    # so weit vor der Nummer darf "ISBN" stehen
_DRUCK = r"druckausgabe|gedruckte ausgabe|print(?:ausgabe)?|gebunden(?:e ausgabe)?|hardcover|paperback|taschenbuch|broschiert|broschur|kartoniert|softcover|buchausgabe"
_EBOOK = r"e-?book|epub|e-pub|pdf|mobi|kindle|digitalausgabe|elektronische ausgabe|online-?ausgabe"
_ISBN_WORT = r"isbn(?:[\s-]*1[03])?"
# dahinter, was nicht schon die nächste Nummer ankündigt ("gebunden: ISBN ...")
_NACHHER = re.compile(rf"^[\s(\[,:;-]*\b(?:(?P<druck>{_DRUCK})|(?P<ebook>{_EBOOK}))\b(?!\s*:)", re.IGNORECASE)
# in Klammern am Anfang der nächsten Zeile ("ISBN ...\n(E-Book)"): umbrochen, gehört zur Nummer davor, kündigt keine an
_NACHHER_UMBROCHEN = re.compile(rf"^[ \t,;]*\n\s*[(\[]\s*(?:(?P<druck>{_DRUCK})|(?P<ebook>{_EBOOK}))\b[^)\]\n]{{0,12}}[)\]]", re.IGNORECASE)
# davor nur, was unmittelbar zur Nummer gehört ("E-Book (PDF): ISBN", "Print-ISBN", "eISBN"), kein Komma dazwischen
_DAVOR = re.compile(rf"\b(?:(?:(?P<druck>{_DRUCK})|(?P<ebook>{_EBOOK}))[\s)\]-]*:?\s*(?:{_ISBN_WORT})?|(?P<e>e)-?{_ISBN_WORT})\s*:?\s*$", re.IGNORECASE)
_NACHHER_REICHWEITE = 24                  # so weit nach der Nummer zählt ein Merkmal
_DAVOR_REICHWEITE = 30
UMFELD = 80                               # Zeichen vor und nach einer Nummer im Ausschnitt, wie in der Suche im Buch


@dataclass(frozen=True)
class Fund:
    """Eine Nummer an einer Stelle des Buchs."""

    seite: int                            # Index der Seite ab 0
    anfang: int                           # Lage im Text der Seite
    ende: int
    form: str                             # wie sie im Buch steht
    isbn13: str
    lage: int                             # Lage im ganzen Buch, für den Anteil
    ausgabe: Ausgabe


def _ziffern(text: str) -> str:
    return re.sub(r"[^0-9Xx]", "", text).upper()


def _mit_marke(text: str, anfang: int) -> bool:
    return bool(_MARKE_DAVOR.search(text[max(0, anfang - _MARKE_REICHWEITE):anfang]))


def _zehn_in_ueblicher_form(form: str) -> bool:
    return len(re.findall(r"[-\u2010\u2011]", form)) == 3


def _treffer(text: str) -> list[tuple[int, int, str]]:
    """(anfang, ende, isbn13) je gültiger Nummer auf einer Seite, nach Lage geordnet."""
    aus: list[tuple[int, int, str]] = []
    belegt: list[tuple[int, int]] = []
    for m in _ISBN13.finditer(text):
        z = _ziffern(m.group())
        if z[:3] in ("978", "979") and nummern.gueltig(z):
            aus.append((m.start(), m.end(), z))
            belegt.append((m.start(), m.end()))
    for m in _ISBN10.finditer(text):
        if any(a < m.end() and m.start() < e for a, e in belegt):
            continue
        z = _ziffern(m.group())
        if nummern.gueltig(z) and (_mit_marke(text, m.start()) or _zehn_in_ueblicher_form(m.group())):
            aus.append((m.start(), m.end(), nummern.dreizehn(z)))
    return sorted(aus)


def ausgabe(text: str, anfang: int, ende: int, davor_bis: int, danach_ab: int) -> Ausgabe:
    """Druck oder E-Book, wenn der Text unmittelbar neben der Nummer es sagt: erst dahinter ("(E-Book)", auch in Klammern am Anfang
    der nächsten Zeile), dann davor ("E-Book: ISBN"); nie über die Nummer davor oder danach hinaus."""
    rest = text[ende:min(danach_ab, ende + _NACHHER_REICHWEITE)]
    davor = text[max(davor_bis, anfang - _DAVOR_REICHWEITE):anfang].rsplit("\n", 1)[-1]
    for m in (_NACHHER.search(rest.split("\n", 1)[0]), _NACHHER_UMBROCHEN.search(rest), _DAVOR.search(davor)):
        if m:
            return Ausgabe.DRUCK if m.group("druck") else Ausgabe.EBOOK       # "e" vor ISBN heißt E-Book
    return Ausgabe.OFFEN


def finde(seiten: list[str]) -> list[Fund]:
    """Alle Nummern des Buchs in der Reihenfolge des Buchs."""
    funde: list[Fund] = []
    versatz = 0
    for nr, text in enumerate(seiten):
        treffer = _treffer(text)
        for i, (anfang, ende, isbn13) in enumerate(treffer):
            davor_bis = treffer[i - 1][1] if i else 0
            danach_ab = treffer[i + 1][0] if i + 1 < len(treffer) else len(text)
            funde.append(Fund(seite=nr, anfang=anfang, ende=ende, form=text[anfang:ende], isbn13=isbn13, lage=versatz + anfang,
                              ausgabe=ausgabe(text, anfang, ende, davor_bis, danach_ab)))
        versatz += len(text) + 1
    return funde


def auszug(text: str, von: int, bis: int, markiert: list[tuple[int, int]]) -> str:
    """Der Text von `von` bis `bis`, maskiert, die Stellen in `markiert` in <mark>, "..." wo abgeschnitten (wie die Suche im Buch)."""
    teile, zuletzt = [], von
    for a, e in sorted(markiert):
        if a < zuletzt or e > bis:
            continue
        teile += [html.escape(text[zuletzt:a], quote=False), f"<mark>{html.escape(text[a:e], quote=False)}</mark>"]
        zuletzt = e
    teile.append(html.escape(text[zuletzt:bis], quote=False))
    innen = " ".join("".join(teile).split())
    return ("..." if von > 0 else "") + innen + ("..." if bis < len(text) else "")


def fenster(text: str, anfang: int, ende: int) -> tuple[int, int]:
    """Der Ausschnitt um eine Stelle, an Wortgrenzen."""
    von, bis = max(0, anfang - UMFELD), min(len(text), ende + UMFELD)
    while von > 0 and not text[von - 1].isspace() and anfang - von < UMFELD + 20:
        von -= 1
    while bis < len(text) and not text[bis].isspace() and bis - ende < UMFELD + 20:
        bis += 1
    return von, bis
