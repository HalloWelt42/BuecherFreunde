"""Feste Regeln je Buch und Kategorie (BF-69). Vier Arten:

- Sachgruppe: die Nummer des Buchs beginnt mit dem Wert ("62" trifft "621.3", "B" trifft "B").
- Schlagwort: der Wert steht als ganzes Wort in einem Schlagwort des Buchs (die Schlagworte der Quellen landen als Regale
  am Buch; die Namen seiner alten Regale zählen deshalb als Schlagworte).
- Titelwort: ein Wort des Titels beginnt mit dem Wert ("programmier" trifft "Programmierung").
- Verlag: der Wert steht im Verlag.

Groß und klein zählen nicht, Bindestriche gelten wie Leerzeichen ("Science-Fiction" gleich "Science Fiction"). Jede Art hat
ihre Sicherheit (`SICHERHEIT`); trifft mehr als eine Regel, steigt sie je weiterer um `JE_WEITERER`, höchstens auf
`HOECHSTENS`."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from pydantic import BaseModel

from backend.app.katalog.modelle import Regelart, Regeln

SICHERHEIT: dict[Regelart, int] = {"sachgruppen": 90, "schlagworte": 80, "titelwoerter": 70, "verlage": 60}
JE_WEITERER = 3
HOECHSTENS = 97
WORTANFANG, WORTENDE = r"(?<!\w)", r"(?!\w)"
WORTE = {"sachgruppen": "Sachgruppe", "schlagworte": "Schlagwort", "titelwoerter": "Titelwort", "verlage": "Verlag"}


def klein(text: str) -> str:
    """Zum Vergleichen: ohne Unterschied von Groß und klein, Bindestriche als Leerzeichen, Leerraum einfach."""
    t = unicodedata.normalize("NFC", text or "").casefold().replace("-", " ")
    return " ".join(t.split())


@dataclass(frozen=True)
class Suchtext:
    """Was die Regeln an einem Werk ansehen, schon für den Vergleich vorbereitet (`suchtext`)."""

    titel: str
    verlag: str
    schlagworte: str                           # alle in einem Text, je Zeile eins: kein Wort reicht über zwei hinweg
    sachgruppen: tuple[str, ...]


def suchtext(titel: str, verlag: str, schlagworte: Iterable[str], sachgruppen: Iterable[str]) -> Suchtext:
    return Suchtext(titel=klein(titel), verlag=klein(verlag), schlagworte="\n".join(klein(s) for s in schlagworte),
                    sachgruppen=tuple(s.strip().upper() for s in sachgruppen))


class Regeltreffer(BaseModel):
    art: Regelart
    wert: str                                  # der Wert der Regel, der traf

    @property
    def satz(self) -> str:
        return f"{WORTE[self.art]} {self.wert}"


class Pruefer:
    """Die Regeln einer Kategorie, einmal übersetzt, für viele Werke. `trifft` sagt schnell, ob irgendeine Regel trifft
    (eine Suche je Art), `treffer` nennt die Regeln einzeln."""

    def __init__(self, regeln: Regeln) -> None:
        self.regeln = regeln
        self._sachgruppen = [(w, n) for w in regeln.sachgruppen if (n := w.strip().upper())]
        self._schlagworte = [(w, n) for w in regeln.schlagworte if (n := klein(w))]
        self._titelwoerter = [(w, n) for w in regeln.titelwoerter if (n := klein(w))]
        self._verlage = [(w, n) for w in regeln.verlage if (n := klein(w))]
        self._ein_schlagwort = _muster([n for _, n in self._schlagworte], ganz=True)
        self._ein_titelwort = _muster([n for _, n in self._titelwoerter], ganz=False)

    def trifft(self, t: Suchtext) -> bool:
        return bool(any(g.startswith(n) for _, n in self._sachgruppen for g in t.sachgruppen)
                    or (self._ein_schlagwort and self._ein_schlagwort.search(t.schlagworte))
                    or (self._ein_titelwort and self._ein_titelwort.search(t.titel))
                    or any(n in t.verlag for _, n in self._verlage))

    def treffer(self, t: Suchtext) -> list[Regeltreffer]:
        if not self.trifft(t):
            return []
        aus = [Regeltreffer(art="sachgruppen", wert=w) for w, n in self._sachgruppen if any(g.startswith(n) for g in t.sachgruppen)]
        aus += [Regeltreffer(art="schlagworte", wert=w) for w, n in self._schlagworte if _muster([n], ganz=True).search(t.schlagworte)]
        aus += [Regeltreffer(art="titelwoerter", wert=w) for w, n in self._titelwoerter if _muster([n], ganz=False).search(t.titel)]
        aus += [Regeltreffer(art="verlage", wert=w) for w, n in self._verlage if n in t.verlag]
        return aus


@lru_cache(maxsize=4096)
def _muster_aus(werte: tuple[str, ...], ganz: bool) -> re.Pattern[str]:
    return re.compile(WORTANFANG + "(?:" + "|".join(map(re.escape, werte)) + ")" + (WORTENDE if ganz else ""))


def _muster(werte: list[str], ganz: bool) -> re.Pattern[str] | None:
    """Ein Muster für einen der Werte am Wortanfang; `ganz`: auch am Wortende."""
    return _muster_aus(tuple(werte), ganz) if werte else None


def sicherheit(treffer: list[Regeltreffer]) -> int:
    """Die Sicherheit der stärksten Regel, je weiterer etwas mehr, höchstens `HOECHSTENS`; 0 ohne Treffer."""
    if not treffer:
        return 0
    return min(HOECHSTENS, max(SICHERHEIT[t.art] for t in treffer) + JE_WEITERER * (len(treffer) - 1))
