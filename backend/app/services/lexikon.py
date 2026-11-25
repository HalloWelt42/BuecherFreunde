"""Vertrag des Nachschlagens: was ein Lexikon liefert (Treffer, Artikel zum Lesen im kleinen Fenster, Bilder) und wie fremdes HTML
lesbar und harmlos wird. Zwei Anschlüsse erfüllen ihn: Nachschlag aus den Hausdiensten (lexikon_nachschlag) und das öffentliche
Lexikon im Netz (lexikon_netz); welcher gilt, entscheidet nachschlagen."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal, Protocol

from bs4 import BeautifulSoup, NavigableString, Tag
from pydantic import BaseModel

Art = Literal["nachschlag", "netz"]
ERLAUBT = {"p", "h2", "h3", "h4", "ul", "ol", "li", "b", "strong", "i", "em", "sub", "sup", "code", "pre", "blockquote", "dl", "dt", "dd", "br"}
WEG = ["script", "style", "table", "figure", "img", "svg", "math", "video", "audio", "iframe", "form", "button", "input", "nav"]
KENNUNG = re.compile(r"[\w()., -]{1,120}")


class Nachschlagtreffer(BaseModel):
    buch: str
    buchtitel: str
    pfad: str
    titel: str
    auszug: str = ""
    anker: str = ""
    bild: str = ""


class Abschnitt(BaseModel):
    anker: str
    titel: str


class Nachschlagartikel(BaseModel):
    buch: str
    buchtitel: str
    pfad: str
    titel: str
    html: str
    anker: str = ""
    bild: str = ""
    abschnitte: list[Abschnitt] = []
    adresse: str                                   # dieselbe Seite im Lexikon selbst


class Lexikon(Protocol):
    art: Art

    @property
    def adresse(self) -> str:
        """Wo das Lexikon selbst zu finden ist."""

    async def suche(self, frage: str, anzahl: int, sitzung: str, nur_titel: bool) -> list[Nachschlagtreffer]:
        """`nur_titel`: schnell, nur nach Titeln; sonst auch im Text."""

    async def artikel(self, buch: str, pfad: str, frage: str, anker: str, sitzung: str) -> Nachschlagartikel: ...

    async def bild(self, buch: str, pfad: str) -> tuple[bytes, str]:
        """Inhalt und Art eines Bildes; nur Rasterbilder."""

    async def vorwaermen(self) -> None: ...

    async def schliessen(self) -> None: ...


def klartext(auszug: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(auszug or "", "html.parser").get_text()).strip()


def ordnen(frage: str, treffer: list[Nachschlagtreffer], vorziehen: Callable[[Nachschlagtreffer], bool] = lambda _t: False) -> list[Nachschlagtreffer]:
    """Genauer Titel zuerst, dann Titel, die so beginnen, darin die vorgezogenen; sonst bleibt die Reihenfolge der Suche."""
    f = frage.casefold().strip()

    def rang(nr_t: tuple[int, Nachschlagtreffer]) -> tuple:
        nr, t = nr_t
        titel = t.titel.casefold()
        return (0 if titel == f else 1 if titel.startswith(f) else 2, 0 if vorziehen(t) else 1, nr)

    return [t for _, t in sorted(enumerate(treffer), key=rang)]


def ist_bild(art: str) -> bool:
    """Nur Rasterbilder; SVG kann Skript tragen."""
    return art.startswith("image/") and art != "image/svg+xml"


def zum_lesen(html: str, verweis: Callable[[str], str | None], weg_klassen: frozenset[str] = frozenset()) -> str:
    """Nur Text, Überschriften, Listen und Verweise ins selbe Lexikon (`verweis`: Ziel eines Verweises als Pfad, sonst None);
    alles andere fällt weg, kein fremdes HTML kommt durch. `weg_klassen`: Bausteine mit diesen Klassen fallen samt Inhalt weg."""
    quelle = BeautifulSoup(html, "html.parser")
    for t in quelle.find_all(WEG):
        t.decompose()
    if weg_klassen:
        for t in quelle.find_all(class_=lambda k: bool(k) and k in weg_klassen):
            if not t.decomposed:
                t.decompose()
    ziel = BeautifulSoup("", "html.parser")
    _uebernehmen(quelle, ziel, ziel, verweis)
    return str(ziel)


def _uebernehmen(von: Tag, nach: Tag, doc: BeautifulSoup, verweis: Callable[[str], str | None]) -> None:
    for kind in list(von.children):
        if isinstance(kind, Tag):
            neu = _neues(kind, doc, verweis)
            _uebernehmen(kind, nach if neu is None else neu, doc, verweis)
            if neu is not None:
                nach.append(neu)
        elif type(kind) is NavigableString:                # keine Kommentare, keine Anweisungen
            nach.append(NavigableString(str(kind)))


def _neues(alt: Tag, doc: BeautifulSoup, verweis: Callable[[str], str | None]) -> Tag | None:
    if alt.name == "a":
        pfad = verweis(alt.get("href", ""))
        return doc.new_tag("a", attrs={"href": "#", "data-pfad": pfad}) if pfad else None
    if alt.name not in ERLAUBT:
        return None
    neu = doc.new_tag(alt.name)
    if alt.name in ("h2", "h3", "h4") and KENNUNG.fullmatch(alt.get("id") or ""):
        neu["id"] = "ns-" + alt["id"]
    return neu
