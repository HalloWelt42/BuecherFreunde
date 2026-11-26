"""XHTML und XML so lesen, dass jede Stelle ihren Ort in der Quelle behält (BF-71).

Beim Übersetzen tauscht nur der Text; alles andere bleibt Zeichen für Zeichen, wie es in der Datei steht. Darum gibt es hier
keinen Parser, der einen Baum neu schreibt, sondern ein schlichtes Lesen der Marken samt ihrer Stellen: Anfang und Ende des
Kopfs (`<p class="x">`) und des Fußes (`</p>`) in der Quelle. Wer etwas ändert, ersetzt genau diese Stücke der Quelle.

Nicht Wohlgeformtes wird geduldet wie im Browser: ein Ende, zu dem ein äußeres Element passt, schließt die inneren mit; ein
Ende ohne Anfang bleibt als eigenes Stück stehen (nichts geht verloren); die leeren Elemente aus HTML (br, img ...) brauchen
keinen Schrägstrich. Zeichenreferenzen (&amp;, &#8217;, auch die Namen aus HTML wie &nbsp;) werden erst beim Lesen von Text
aufgelöst, nie in der Quelle."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from html import unescape

#: Elemente aus HTML, die nie einen Inhalt haben, auch ohne Schrägstrich
LEERE = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})

TOKEN = re.compile(r"""
    (?P<kommentar><!--.*?-->)
  | (?P<cdata><!\[CDATA\[.*?\]\]>)
  | (?P<anweisung><\?.*?\?>)
  | (?P<doctype><!DOCTYPE(?:[^\[>]|\[.*?\])*>)
  | </(?P<zu>[A-Za-z_][^\s>]*)\s*>
  | <(?P<auf>[A-Za-z_][^\s/>]*)(?P<attribute>(?:\s+[^\s=/>]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>"']+))?)*)\s*(?P<leer>/?)>
""", re.S | re.X | re.I)
ATTRIBUT = re.compile(r"""([^\s=/>]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>"']+))?""")
LEERRAUM = re.compile(r"[ \t\r\n]+")                 # Leerraum in XML; das geschützte Leerzeichen gehört nicht dazu


@dataclass(eq=False)
class Text:
    anfang: int
    ende: int
    roh: str                                         # wie in der Quelle, mit Zeichenreferenzen


@dataclass(eq=False)
class Sonst:
    """Kommentar, Verarbeitungsanweisung, CDATA, Dokumenttyp oder ein Ende ohne Anfang: bleibt, wie es ist."""
    anfang: int
    ende: int
    roh: str


@dataclass(eq=False)
class Element:
    name: str                                        # wie geschrieben, etwa "epub:switch"
    attribute: dict[str, str]                        # Werte mit aufgelösten Zeichenreferenzen
    anfang: int                                      # Anfang des Kopfs
    kopf_ende: int
    fuss_anfang: int                                 # Anfang des Fußes; ohne Fuß gleich `ende`
    ende: int
    leer: bool = False
    kinder: list[Knoten] = field(default_factory=list)

    @property
    def lokal(self) -> str:
        """Der Name ohne Vorsilbe, klein: "epub:switch" ist "switch"."""
        return self.name.rsplit(":", 1)[-1].lower()

    def attr(self, name: str) -> str:
        return self.attribute.get(name, "")

    def klassen(self) -> set[str]:
        return set(self.attr("class").split())

    def woerter(self, name: str) -> set[str]:
        """Die Wörter eines Attributs, das eine Liste ist (class, epub:type, role)."""
        return set(self.attr(name).split())

    def elemente(self) -> Iterator[Element]:
        return (k for k in self.kinder if isinstance(k, Element))

    def alle(self, lokal: str | None = None) -> Iterator[Element]:
        """Alle Nachfahren in der Reihenfolge der Quelle, auf Wunsch nur die mit diesem Namen."""
        for k in self.elemente():
            if lokal is None or k.lokal == lokal:
                yield k
            yield from k.alle(lokal)

    def erstes(self, lokal: str) -> Element | None:
        return next(self.alle(lokal), None)


Knoten = Text | Sonst | Element


def _attribute(roh: str) -> dict[str, str]:
    aus: dict[str, str] = {}
    for name, wert in ATTRIBUT.findall(roh):
        if wert[:1] in ('"', "'"):
            wert = wert[1:-1]
        aus.setdefault(name, unescape(wert))
    return aus


def lesen(quelle: str) -> Element:
    """Das ganze Dokument unter einer Wurzel ohne Namen ("#dokument"), die die Quelle von vorn bis hinten umfasst."""
    wurzel = Element("#dokument", {}, 0, 0, len(quelle), len(quelle))
    stapel = [wurzel]
    pos = 0
    for m in TOKEN.finditer(quelle):
        if m.start() > pos:
            stapel[-1].kinder.append(Text(pos, m.start(), quelle[pos:m.start()]))
        pos = m.end()
        if m.group("zu"):
            _schliessen(stapel, m)
        elif m.group("auf"):
            name = m.group("auf")
            leer = bool(m.group("leer")) or name.lower() in LEERE
            el = Element(name, _attribute(m.group("attribute")), m.start(), m.end(), m.end(), m.end(), leer)
            stapel[-1].kinder.append(el)
            if not leer:
                stapel.append(el)
        else:
            stapel[-1].kinder.append(Sonst(m.start(), m.end(), m.group(0)))
    if pos < len(quelle):
        stapel[-1].kinder.append(Text(pos, len(quelle), quelle[pos:]))
    for el in stapel[1:]:                                    # nie geschlossen: endet mit der Quelle
        el.fuss_anfang = el.ende = len(quelle)
    return wurzel


def _schliessen(stapel: list[Element], m: re.Match) -> None:
    name = m.group("zu")
    tiefe = next((i for i in range(len(stapel) - 1, 0, -1) if stapel[i].name == name), None)
    if tiefe is None:                                        # Ende ohne Anfang: bleibt als eigenes Stück
        stapel[-1].kinder.append(Sonst(m.start(), m.end(), m.group(0)))
        return
    for inneres in stapel[tiefe + 1:]:                       # vom äußeren Ende mit geschlossen, ohne eigenen Fuß
        inneres.fuss_anfang = inneres.ende = m.start()
    el = stapel[tiefe]
    el.fuss_anfang, el.ende = m.start(), m.end()
    del stapel[tiefe:]


def wurzelelement(dokument: Element) -> Element | None:
    """Das erste Element des Dokuments (html, package, ncx)."""
    return next(dokument.elemente(), None)


def entschluesseln(roh: str) -> str:
    """Text aus der Quelle mit aufgelösten Zeichenreferenzen."""
    return unescape(roh)


def verschluesseln(text: str) -> str:
    """Text für die Quelle: nur &, < und > werden Zeichenreferenzen."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text_von(el: Element) -> str:
    """Der Text eines Elements wie für Menschen: Zeichenreferenzen aufgelöst, Leerraum zu einem Leerzeichen."""
    teile: list[str] = []

    def sammeln(k: Knoten) -> None:
        if isinstance(k, Text):
            teile.append(entschluesseln(k.roh))
        elif isinstance(k, Element):
            for kind in k.kinder:
                sammeln(kind)

    sammeln(el)
    return LEERRAUM.sub(" ", "".join(teile)).strip()


def kodierung(daten: bytes) -> tuple[str, bytes]:
    """Kodierung einer XML-Datei und ein Vorspann (Byte-Order-Mark), der beim Schreiben wieder davor gehört."""
    if daten.startswith(b"\xef\xbb\xbf"):
        return "utf-8", b"\xef\xbb\xbf"
    if daten.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16", b""                                 # utf-16 schreibt seine Markierung selbst
    kopf = re.match(rb"""<\?xml[^>]*encoding\s*=\s*["']([A-Za-z0-9._-]+)["']""", daten[:200])
    return (kopf.group(1).decode("ascii").lower() if kopf else "utf-8"), b""
