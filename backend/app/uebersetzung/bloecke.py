"""Die Textläufe eines Dokuments als Blöcke (BF-71, nach Nachschlag zerlegen.py).

Ein Lauf ist, was in einem Element zwischen zwei Blockgrenzen steht: Text samt Auszeichnungen im Satz, bis zum nächsten
Element, das selbst Blöcke enthält (Absatz, Liste, Tabelle ...). Jeder Lauf mit Buchstaben darin wird ein Block; seine
Vorlage trägt Auszeichnungen als Klammermarken und alles Unantastbare als Platzhalter (marken.py). Code, Formeln, Bilder und
Verweise wie Fußnotenzeichen gehen so nie ans Modell, ebenso Code in Backticks (`print`) und Auszeichnungen in
Festbreitenschrift, die Code tragen (codeabsaetze.py). Ganz draußen bleiben `pre`, `script`, `style`, `math`, `svg`, alles mit
`translate="no"`, die Klassen, die nie übersetzt werden (Einstellung `UEBERSETZEN_NIE_KLASSEN`), und Absätze, die Code sind
(codeabsaetze.py: Zäune aus Markdown, Zeilen wie `pip install pygame`).

Ein Lauf kennt seine Stelle in der Quelle (ohne den Leerraum am Rand); setzen.py ersetzt genau dieses Stück. Die
Auszeichnungen einer Übersetzung kommen mit ihrem Kopf und Fuß aus der Quelle zurück, Platzhalter Zeichen für Zeichen."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from typing import Literal

from backend.app.uebersetzung import codeabsaetze, marken
from backend.app.uebersetzung.xhtml import Element, Knoten, Sonst, Text, entschluesseln, verschluesseln

Art = Literal["ueberschrift", "absatz", "listenpunkt", "tabellenzelle", "bildunterschrift", "fussnote"]

#: Ganze Teile, die nie übersetzt werden
NIE = frozenset({"head", "pre", "script", "style", "template", "textarea", "math", "svg", "object", "iframe", "audio", "video",
                 "canvas", "noscript"})
#: Unantastbar im Satz: geht als Platzhalter durch und kommt Zeichen für Zeichen zurück
ATOM = frozenset({"code", "kbd", "samp", "var", "tt", "math", "img", "image", "svg", "br", "wbr", "input", "button", "select",
                  "object", "embed", "audio", "video", "canvas", "iframe"})
#: Auszeichnungen im Satz: ihr Text wird übersetzt, die Auszeichnung bleibt
INLINE = frozenset({"a", "abbr", "acronym", "b", "bdi", "bdo", "big", "cite", "data", "del", "dfn", "em", "font", "i", "ins",
                    "label", "mark", "q", "s", "small", "span", "strike", "strong", "sub", "sup", "time", "u"})
#: Verweise, die nur ein Zeichen oder eine Nummer sind (Fußnotenzeichen, Seitenmarken, Rückverweise)
VERWEIS_ARTEN = frozenset({"noteref", "pagebreak", "backlink", "biblioref", "glossref", "annoref"})
VERWEIS_ROLLEN = frozenset({"doc-noteref", "doc-pagebreak", "doc-backlink", "doc-biblioref", "doc-glossref"})
FUSSNOTE_ARTEN = frozenset({"footnote", "footnotes", "endnote", "endnotes", "rearnote", "rearnotes", "note"})
FUSSNOTE_ROLLEN = frozenset({"doc-footnote", "doc-endnote", "doc-endnotes"})
FUSSNOTE_KLASSEN = frozenset({"footnote", "footnotes", "endnote", "endnotes"})
ART_NACH_ELEMENT: dict[str, Art] = {"li": "listenpunkt", "dt": "listenpunkt", "dd": "listenpunkt", "navlabel": "listenpunkt",
                                    "td": "tabellenzelle", "th": "tabellenzelle", "caption": "bildunterschrift",
                                    "figcaption": "bildunterschrift"}
UEBERSCHRIFT = re.compile(r"h([1-6])")
#: Arten von Läufen, die Code sein können (Absätze und Listenpunkte; nie Überschriften, Zellen, Unterschriften, Fußnoten)
CODE_KANDIDATEN: frozenset[Art] = frozenset({"absatz", "listenpunkt"})
BUCHSTABE = re.compile(r"[^\W\d_]")
INHALT = re.compile(r"[^\W_]")                                # Buchstabe oder Ziffer
ADRESSE = re.compile(r"\s*(?:[a-z][a-z0-9+.-]*://\S+|www\.\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+)\s*", re.I)
LEERRAUM = re.compile(r"[ \t\r\n]+")
#: Code in Backticks wie in Markdown (`print`, ``a`b``): Inhalt ohne Leerraum am Rand und ohne Zeilenwechsel
BACKTICKS = re.compile(r"(?<!`)(`{1,2})(?!`)(?=\S)([^\n]*?\S)(?<!`)\1(?!`)")


@dataclass(frozen=True)
class Woertlich:
    """Ein Stück Text der Quelle, das wörtlich bleibt (Code in Backticks); geht als Platzhalter durch."""
    anfang: int
    ende: int


@dataclass(frozen=True)
class Regeln:
    """Was in einem Dokument Block, Auszeichnung und unantastbar ist."""
    nie_klassen: frozenset[str] = frozenset()
    nur_verzeichnis: bool = False                    # NCX: nur die Einträge des Inhaltsverzeichnisses (navLabel)
    festbreit_klassen: frozenset[str] = frozenset()  # Klassen mit Festbreitenschrift aus dem CSS des Dokuments
    code_absaetze: bool = True                       # Absätze, die Code sind, bleiben draußen (nicht im Verzeichnis)

    def nie(self, el: Element) -> bool:
        return el.lokal in NIE or el.attr("translate") == "no" or bool(el.klassen() & self.nie_klassen)

    def festbreit(self, el: Element) -> bool:
        """In Festbreitenschrift gesetzt: Klasse aus dem CSS, Schrift im Stil am Element, oder eine Klasse für Code."""
        klassen = el.klassen()
        return (bool(klassen & self.festbreit_klassen or klassen & codeabsaetze.CODE_KLASSEN)
                or codeabsaetze.festbreit_im_stil(el.attr("style")))

    def verweis(self, el: Element) -> bool:
        if el.woerter("epub:type") & VERWEIS_ARTEN or el.woerter("role") & VERWEIS_ROLLEN:
            return True
        return el.lokal == "a" and bool(ADRESSE.fullmatch(_reiner_text(el)))      # eine Adresse als Text bleibt Adresse

    def atom(self, k: Knoten) -> bool:
        if isinstance(k, Sonst):
            return True
        if not isinstance(k, Element):
            return False
        if k.lokal in ATOM:
            return True
        return k.lokal in INLINE and (self.nie(k) or self.verweis(k) or not self._mit_inhalt(k) or self._code_im_satz(k))

    def _code_im_satz(self, el: Element) -> bool:
        """Eine Auszeichnung mit einer Klasse für Code ist Code; eine in Festbreitenschrift nur, wenn ihr Text danach aussieht."""
        if el.klassen() & codeabsaetze.CODE_KLASSEN:
            return True
        return self.festbreit(el) and codeabsaetze.code_im_satz(_reiner_text(el))

    def fliesstext(self, k: Knoten) -> bool:
        """Gehört zum Lauf: Text, ein Platzhalter oder eine Auszeichnung, die nur Fließtext enthält."""
        if isinstance(k, (Text, Sonst)) or self.atom(k):
            return True
        return isinstance(k, Element) and k.lokal in INLINE and all(self.fliesstext(c) for c in k.kinder)

    def _mit_inhalt(self, el: Element) -> bool:
        """Ob eine Auszeichnung Text trägt (Buchstaben oder Ziffern außerhalb von Unantastbarem); sonst ist sie selbst
        unantastbar, etwa ein leerer Anker oder ein Zeichen aus einem Bild."""
        for k in el.kinder:
            if isinstance(k, Text) and INHALT.search(entschluesseln(k.roh)):
                return True
            if isinstance(k, Element) and not self.atom(k) and self._mit_inhalt(k):
                return True
        return False

    def nimmt(self, eltern: Element, vorfahren: list[Element]) -> bool:
        if not self.nur_verzeichnis:
            return True
        return eltern.lokal == "text" and any(v.lokal == "navlabel" for v in vorfahren)


def _reiner_text(el: Element) -> str:
    teile = []
    for k in el.kinder:
        if isinstance(k, Text):
            teile.append(entschluesseln(k.roh))
        elif isinstance(k, Element):
            teile.append(_reiner_text(k))
    return "".join(teile)


@dataclass(eq=False)
class Lauf:
    eltern: Element
    anfang: int                                      # Stelle in der Quelle, ohne Leerraum am Rand
    ende: int
    vorlage: str
    teile: dict[int, Element | Sonst | Woertlich] = field(default_factory=dict)
    art: Art = "absatz"
    stufe: int = 0                                   # bei Überschriften 1 bis 6
    festbreit: bool = False                          # in Festbreitenschrift gesetzt (das Element oder ein Vorfahr)
    nur_zaun: bool = False                           # ein Zaun ohne Buchstaben ("```"): kein Block, nur für die Erkennung von Code

    def zeilentext(self) -> str:
        """Der Klartext für die Erkennung von Code: Zeilenwechsel (br) als \\n, andere Platzhalter als Leerzeichen."""
        def platz(m: re.Match) -> str:
            if m.group(3) is None:
                return ""
            teil = self.teile.get(int(m.group(3)))
            return "\n" if isinstance(teil, Element) and teil.lokal == "br" else " "
        return re.sub(r"[ \t\r]+", " ", unescape(marken.MARKE.sub(platz, self.vorlage))).strip()


def _vorlagentext(roh: str) -> str:
    return verschluesseln(LEERRAUM.sub(" ", entschluesseln(roh)))


def _vorlage(knoten: list[Knoten], regeln: Regeln) -> tuple[str, dict[int, Element | Sonst | Woertlich]]:
    n = 0
    teile: dict[int, Element | Sonst | Woertlich] = {}

    def text(k: Text) -> str:
        """Text mit Code in Backticks als Platzhalter."""
        nonlocal n
        s, pos = "", 0
        for m in BACKTICKS.finditer(k.roh):
            n += 1
            teile[n] = Woertlich(k.anfang + m.start(), k.anfang + m.end())
            s += _vorlagentext(k.roh[pos:m.start()]) + f"<x{n}/>"
            pos = m.end()
        return s + _vorlagentext(k.roh[pos:])

    def innen(liste: list[Knoten]) -> str:
        nonlocal n
        s = ""
        for k in liste:
            if isinstance(k, Text):
                s += text(k)
                continue
            n += 1
            nr = n                                   # n zählt in der Tiefe weiter, die Klammer schließt mit ihrer Nummer
            teile[nr] = k
            if regeln.atom(k):
                s += f"<x{nr}/>"
            else:
                assert isinstance(k, Element)
                s += f"<t{nr}>{innen(k.kinder)}</t{nr}>"
        return s

    return innen(knoten), teile


def _art(eltern: Element, vorfahren: list[Element]) -> tuple[Art, int]:
    kette = [eltern, *reversed(vorfahren)]
    if any(el.woerter("epub:type") & FUSSNOTE_ARTEN or el.woerter("role") & FUSSNOTE_ROLLEN or el.klassen() & FUSSNOTE_KLASSEN
           for el in kette):
        return "fussnote", 0
    for el in kette:
        if t := UEBERSCHRIFT.fullmatch(el.lokal):
            return "ueberschrift", int(t.group(1))
        if el.lokal in ART_NACH_ELEMENT:
            return ART_NACH_ELEMENT[el.lokal], 0
    return "absatz", 0


def _nur_leerraum(k: Knoten) -> bool:
    return isinstance(k, Text) and not k.roh.strip(" \t\r\n")


def _ohne_rand(folge: list[Knoten]) -> list[Knoten]:
    """Die Knoten eines Laufs ohne Leerraum am Rand: leere Texte fallen weg, Text am Rand verliert seinen Leerraum."""
    innen = list(folge)
    while innen and _nur_leerraum(innen[0]):
        innen.pop(0)
    while innen and _nur_leerraum(innen[-1]):
        innen.pop()
    if innen and isinstance(erst := innen[0], Text):
        roh = erst.roh.lstrip(" \t\r\n")
        innen[0] = Text(erst.ende - len(roh), erst.ende, roh)
    if innen and isinstance(letzt := innen[-1], Text):
        roh = letzt.roh.rstrip(" \t\r\n")
        innen[-1] = Text(letzt.anfang, letzt.anfang + len(roh), roh)
    return innen


def laeufe(dokument: Element, regeln: Regeln) -> list[Lauf]:
    """Alle Läufe mit Buchstaben darin, in der Reihenfolge der Quelle, ohne die Absätze, die Code sind."""
    gefunden: list[Lauf] = []

    def abschliessen(eltern: Element, folge: list[Knoten], vorfahren: list[Element]) -> None:
        innen = _ohne_rand(folge)
        if not innen or not regeln.nimmt(eltern, vorfahren):
            return
        vorlage, teile = _vorlage(innen, regeln)
        klar = marken.klartext(vorlage)
        mit_text = bool(BUCHSTABE.search(klar))
        if mit_text or (regeln.code_absaetze and codeabsaetze.zaun(klar)):
            art, stufe = _art(eltern, vorfahren)
            gefunden.append(Lauf(eltern=eltern, anfang=innen[0].anfang, ende=innen[-1].ende, vorlage=vorlage, teile=teile, art=art,
                                 stufe=stufe, festbreit=any(regeln.festbreit(e) for e in (eltern, *vorfahren)), nur_zaun=not mit_text))

    def besuchen(el: Element, vorfahren: list[Element]) -> None:
        if regeln.nie(el):
            return
        folge: list[Knoten] = []
        for k in el.kinder:
            if regeln.fliesstext(k):
                folge.append(k)
                continue
            abschliessen(el, folge, vorfahren)
            folge = []
            if isinstance(k, Element):
                besuchen(k, [*vorfahren, el])
        abschliessen(el, folge, vorfahren)

    besuchen(dokument, [])
    if not regeln.code_absaetze:
        return gefunden
    code = codeabsaetze.erkennen([codeabsaetze.Absatz(text=l.zeilentext(), kandidat=l.art in CODE_KANDIDATEN, festbreit=l.festbreit)
                                  for l in gefunden])
    return [l for i, l in enumerate(gefunden) if i not in code and not l.nur_zaun]


def darstellen(lauf: Lauf, quelle: str, baum: list[marken.Teil]) -> str:
    """Eine geprüfte Übersetzung als Stück Quelle: Text mit Zeichenreferenzen für & < >, Auszeichnungen mit Kopf und Fuß aus
    der Quelle, Platzhalter Zeichen für Zeichen."""
    s = ""
    for k in baum:
        if isinstance(k, str):
            s += verschluesseln(entschluesseln(k))
        elif isinstance(k, marken.Platz):
            teil = lauf.teile[k.nr]
            s += quelle[teil.anfang:teil.ende]
        else:
            el = lauf.teile[k.nr]
            assert isinstance(el, Element)
            s += quelle[el.anfang:el.kopf_ende] + darstellen(lauf, quelle, k.kinder) + quelle[el.fuss_anfang:el.ende]
    return s
