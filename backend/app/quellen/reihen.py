"""Reihen in den Bibliothekskatalogen (BF-75): welche Bände einer Reihe ein Katalog kennt, mit Nummer, Titel, Autor, ISBN und
Jahr, aus einer einzigen Anfrage. Die Kataloge antworten in MARC 21; die Reihe steht dort in der Gesamttitelangabe (490 mit
Band in $v), in den Nebeneintragungen der Reihe (800, 810, 811 mit $t, 830 mit $a, Band in $v) oder bei einem mehrbändigen Werk
im Titel (245 $a mit Band in $n und Titel des Bands in $p).

Welcher Katalog gefragt wird, hängt an der Sprache: deutsche Ausgaben kennt die Deutsche Nationalbibliothek am besten (dort
auch nach Sprache gefiltert), andere der Verbundkatalog K10plus (die Sprache prüft hier der Abgleich). Je Frage genau ein
Katalog, der erste der Folge, der nicht abgeschaltet ist. Was die Nummern bedeuten (Zwischenbände, Doppelbände, Gesamtzahl),
entscheidet die App (luecken/), nicht der Anschluss."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from backend.app.quellen import marc, regeln, sru
from backend.app.quellen.abgleich import nachname, norm
from backend.app.quellen.abruf import hole
from backend.app.quellen.regeln import Regel
from backend.app.quellen.sprache import marc_code

# Eine Antwort für eine ganze Reihe; so viele Sätze nimmt keine Suche nach einem Buch (5 bis 10), damit ihr Platz im Vorrat ein
# eigener bleibt
SAETZE_HOECHSTENS = 100
_BAND_IM_NAMEN = re.compile(r"^(?P<reihe>.+?)\s*;\s*(?P<band>[^;]+)$")      # "Leuchtfeuerkai ; 3" ohne eigenes $v
_AUSLASSUNG = re.compile(r"^\[\s*(?:\.{2,}|\u2026)\s*\]$")                   # "[...]": Nummer unbekannt
_ARTIKEL = {"der", "die", "das", "ein", "eine", "the", "a", "an", "le", "la", "les", "il", "lo", "el", "los", "las", "de", "het"}
_RAND = " /:;=.,"
_NEBENEINTRAG_MIT_TITEL = {"800", "810", "811"}                              # Person oder Körperschaft, die Reihe in $t


class Reihenfrage(BaseModel):
    reihe: str                                      # der Name der Sammlung
    autor: str = ""                                 # ihr häufigster Autor; leer: ohne
    sprache: str = ""                               # Kürzel; leer: jede


class Reihenangabe(BaseModel):
    reihe: str
    band: str                                       # wie der Katalog die Nummer nennt: "3", "Bd. 3", "3a"
    titel: str = ""                                 # nur bei einem mehrbändigen Werk ($p); sonst der Titel des Satzes


class Reihenfund(BaseModel):
    """Ein Band einer Reihe, wie ein Katalog ihn kennt."""

    reihe: str
    band: str
    titel: str = ""
    autoren: list[str] = Field(default_factory=list)
    isbn: str = ""
    jahr: int | None = None
    sprache: str = ""
    quelle: str


def _sauber(text: str) -> str:
    return "" if _AUSLASSUNG.match(text.strip()) else text.strip(_RAND)


def reihenangaben(s: marc.Satz) -> list[Reihenangabe]:
    """Alle Reihen, die ein Satz nennt, mit Band; auch Verlagsreihen ("Taschenbuch ; 22953"), die der Abgleich aussortiert."""
    aus: list[Reihenangabe] = []
    for f in s.felder("490", "800", "810", "811", "830"):
        name = s.eins(f, "t") if f.get("tag") in _NEBENEINTRAG_MIT_TITEL else s.eins(f, "a")
        band = s.eins(f, "v")
        if not band and (m := _BAND_IM_NAMEN.match(name)):
            name, band = m["reihe"], m["band"]
        if _sauber(name):
            aus.append(Reihenangabe(reihe=_sauber(name), band=_sauber(band)))
    titel = next(s.felder("245"), None)
    if titel is not None and _sauber(s.eins(titel, "n")):
        aus.append(Reihenangabe(reihe=_sauber(s.eins(titel, "a")), band=_sauber(s.eins(titel, "n")), titel=_sauber(s.eins(titel, "p"))))
    return aus


def _haupttitel(s: marc.Satz) -> str:
    f = next(s.felder("245"), None)
    return _sauber(s.eins(f, "a")) if f is not None else ""


def funde_im_satz(s: marc.Satz, quelle: str) -> list[Reihenfund]:
    a = marc.angaben(s, quelle)
    return [Reihenfund(reihe=r.reihe, band=r.band, titel=r.titel or _haupttitel(s), autoren=a.autoren, isbn=a.isbn, jahr=a.jahr,
                       sprache=a.sprache, quelle=quelle) for r in reihenangaben(s) if r.band]


def reihenname(text: str) -> str:
    """Zum Vergleich: normiert und ohne Artikel am Anfang ("Die Leuchtfeuerkai-Saga" gleich "Leuchtfeuerkai Saga")."""
    worte = norm(text).split()
    return " ".join(worte[1:] if len(worte) > 1 and worte[0] in _ARTIKEL else worte)


def passende(funde: list[Reihenfund], frage: Reihenfrage) -> list[Reihenfund]:
    """Nur Bände dieser Reihe, und bei einer Sprache nur die, deren Sprache nicht widerspricht."""
    gesucht = reihenname(frage.reihe)
    return [f for f in funde if reihenname(f.reihe) == gesucht and (not frage.sprache or not f.sprache or f.sprache == frage.sprache)]


class Reihenkatalog:
    """Ein Katalog mit SRU und MARC 21, gefragt nach allen Bänden einer Reihe."""

    def __init__(self, regel: Regel, format_: str, titel: str, person: str, sprache: str = "", fest: tuple[str, ...] = ()) -> None:
        self.regel = regel
        self._katalog = sru.Katalog(regel, format_)
        self._titel, self._person, self._sprache = titel, person, sprache      # Namen der Suchschlüssel; ohne `sprache`: keiner
        self._fest = fest                                                     # immer dabei, etwa nur Bücher

    def anfrage(self, frage: Reihenfrage) -> str:
        teile = [f'{self._titel}="{sru.wort(frage.reihe)}"']
        if frage.autor and (name := sru.wort(nachname(frage.autor))):
            teile.append(f'{self._person}="{name}"')
        teile += self._fest
        if self._sprache and (code := marc_code(frage.sprache)):
            teile.append(f"{self._sprache}={code}")
        return " and ".join(teile)

    def _lies(self, inhalt: bytes) -> list[dict[str, Any]]:
        return [f.model_dump(exclude_defaults=True) for s in marc.saetze(inhalt) if marc.ist_buch(s) for f in funde_im_satz(s, self.regel.kennung)]

    async def reihe(self, frage: Reihenfrage) -> list[Reihenfund]:
        """Die Bände der Reihe, die der Katalog kennt; eine Anfrage, gemerkt im Vorrat. Wirft QuelleFehler."""
        if not sru.wort(frage.reihe):
            return []
        wert = await hole(self.regel, self._katalog.frage(self.anfrage(frage), SAETZE_HOECHSTENS, self._lies))
        return passende([Reihenfund(**f) for f in wert or []], frage)


# Die Nationalbibliothek mit Material und Sprache in der Anfrage, der Verbundkatalog ohne (die Sprache prüft `passende`)
KATALOGE: dict[str, Reihenkatalog] = {
    "dnb": Reihenkatalog(regeln.DNB, "MARC21-xml", "TIT", "PER", "SPR", ("MAT=books",)),
    "k10plus": Reihenkatalog(regeln.K10PLUS, "marcxml", "pica.tit", "pica.per"),
}
FOLGE: dict[str, tuple[str, ...]] = {"de": ("dnb", "k10plus"), "": ("dnb", "k10plus")}     # leer: die Sprache ist unbekannt
SONST: tuple[str, ...] = ("k10plus",)


def fuer_sprache(sprache: str) -> Reihenkatalog | None:
    """Der eine Katalog, der für diese Sprache gefragt wird; None, wenn keiner bereit ist."""
    return next((KATALOGE[k] for k in FOLGE.get(sprache, SONST) if not KATALOGE[k].regel.hindernis), None)


def katalogname(sprache: str) -> str:
    """Wer für diese Sprache gefragt würde, auch wenn er gerade abgeschaltet ist (für den Grund)."""
    return " oder ".join(KATALOGE[k].regel.name for k in FOLGE.get(sprache, SONST))
