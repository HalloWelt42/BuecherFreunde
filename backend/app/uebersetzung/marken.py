"""Vorlagen mit Marken (BF-71, wie in Nachschlag): ans Modell geht nur Text. Auszeichnungen im Satz (kursiv, fett, Verweis)
stehen als nummerierte Klammermarken `<t1>..</t1>`, alles Unantastbare (Code, Formeln, Bilder, Fußnotenzeichen) als
Platzhalter `<x2/>`, dessen Inhalt nie zum Modell geht. Die Nummern zählen in der Tiefe: eine Marke schließt mit ihrer eigenen
Nummer, innere Marken tragen höhere Nummern als die äußere.

Eine Übersetzung taugt nur, wenn sie jede Marke der Vorlage genau einmal trägt, in derselben Schachtelung und ohne fremde
Auszeichnung; die Stellung im Satz darf sich ändern.

Text steht in den Vorlagen und den gespeicherten Übersetzungen mit &lt; &gt; &amp;. Das Modell sieht ihn als Zeichen
(`fuer_modell`: "if age < 18"), nur die Marken sind Auszeichnung; seine Antwort kommt mit `aus_modell` wieder in die
Schreibweise der Vorlagen, ein Text von Hand oder eine frühere Antwort mit `gesichert`. Was dabei wie eine Auszeichnung
aussieht (<b>, </p>) und nicht als Text im Original steht, bleibt roh, damit die Prüfung es als fremde Auszeichnung meldet."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape

MARKE = re.compile(r"<(/?)t(\d+)>|<x(\d+)/>")
LEERRAUM = re.compile(r"[ \t\r\n]+")
#: was in einer Antwort wie eine Auszeichnung aussieht: Elemente, Kommentare, Anweisungen
AUSZEICHNUNG = re.compile(r"</?[A-Za-z][\w:.-]*(?:\s[^<>]*)?/?>|<!--.*?-->|<![A-Za-z][^<>]*>|<\?[^<>]*\?>", re.S)


@dataclass(frozen=True)
class Marke:
    atom: bool                                       # Platzhalter <xN/>; sonst Klammer <tN>..</tN>
    oben: int                                        # Nummer der umgebenden Klammer, 0: keine


@dataclass
class Klammer:
    nr: int
    kinder: list[Teil] = field(default_factory=list)


@dataclass(frozen=True)
class Platz:
    nr: int


Teil = str | Klammer | Platz


class MarkenFehler(ValueError):
    """Die Marken einer Übersetzung passen nicht zur Vorlage; `stelle` ist das Stück, an dem es auffiel."""

    def __init__(self, grund: str, stelle: str = "") -> None:
        super().__init__(grund)
        self.grund, self.stelle = grund, stelle


def plan(vorlage: str) -> dict[int, Marke]:
    """Welche Marken eine Vorlage trägt, mit ihrer Art und Schachtelung."""
    aus: dict[int, Marke] = {}
    offen = [0]
    for m in MARKE.finditer(vorlage):
        zu, t, x = m.group(1), m.group(2), m.group(3)
        if zu:
            offen.pop()
            continue
        n = int(t or x)
        aus[n] = Marke(atom=bool(x), oben=offen[-1])
        if t:
            offen.append(n)
    return aus


def lesen(plan_: dict[int, Marke], text: str) -> list[Teil]:
    """Die Übersetzung als Baum aus Text, Klammern und Platzhaltern; wirft MarkenFehler, wenn eine Marke fehlt, fremd,
    doppelt, vertauscht oder falsch geschachtelt ist oder eine fremde Auszeichnung dasteht."""
    fremd = re.search(r"<[^>]*>?", MARKE.sub("", text))
    if fremd:
        raise MarkenFehler("Fremde Auszeichnung im Text", fremd.group(0))
    wurzel: list[Teil] = []
    stapel: list[tuple[int, list[Teil]]] = [(0, wurzel)]
    gesehen: dict[int, int] = {}
    pos = 0
    for m in MARKE.finditer(text):
        if m.start() > pos:
            stapel[-1][1].append(text[pos:m.start()])
        pos = m.end()
        zu, t, x = m.group(1), m.group(2), m.group(3)
        n = int(t or x)
        if n not in plan_:
            raise MarkenFehler(f"Die Marke {n} gibt es im Original nicht", m.group(0))
        if zu:
            if stapel[-1][0] != n:
                raise MarkenFehler(f"Die Marke {n} ist falsch geschlossen", m.group(0))
            stapel.pop()
            continue
        if n in gesehen:
            raise MarkenFehler(f"Die Marke {n} steht doppelt da", m.group(0))
        if bool(x) != plan_[n].atom:
            raise MarkenFehler(f"Die Marke {n} hat die falsche Art", m.group(0))
        gesehen[n] = stapel[-1][0]
        if x:
            stapel[-1][1].append(Platz(n))
        else:
            k = Klammer(n)
            stapel[-1][1].append(k)
            stapel.append((n, k.kinder))
    if pos < len(text):
        stapel[-1][1].append(text[pos:])
    if len(stapel) != 1:
        raise MarkenFehler(f"Die Marke {stapel[-1][0]} ist nicht geschlossen", f"<t{stapel[-1][0]}>")
    fehlt = sorted(set(plan_) - set(gesehen))
    if fehlt:
        n = fehlt[0]
        raise MarkenFehler(f"Die Marke {n} fehlt", f"<x{n}/>" if plan_[n].atom else f"<t{n}>")
    anders = sorted(n for n in gesehen if gesehen[n] != plan_[n].oben)
    if anders:
        raise MarkenFehler(f"Die Marke {anders[0]} ist anders geschachtelt", f"<t{anders[0]}>" if not plan_[anders[0]].atom else f"<x{anders[0]}/>")
    return wurzel


def klartext(text: str, platz: str = " ") -> str:
    """Der Text ohne Marken (Platzhalter werden `platz`), Zeichenreferenzen aufgelöst, Leerraum zu einem Leerzeichen."""
    ohne = MARKE.sub(lambda m: platz if m.group(3) else "", text)
    return LEERRAUM.sub(" ", unescape(ohne)).strip()


def _je_stueck(text: str, umwandeln) -> str:
    """Der Text mit umgewandelten Stücken zwischen den Marken; die Marken bleiben, wie sie sind."""
    aus, pos = [], 0
    for m in MARKE.finditer(text):
        aus += [umwandeln(text[pos:m.start()]), m.group(0)]
        pos = m.end()
    return "".join(aus) + umwandeln(text[pos:])


def fuer_modell(vorlage: str) -> str:
    """Die Vorlage, wie das Modell sie sieht: Text als Zeichen (&lt; wird <, &amp; wird &), nur die Marken sind
    Auszeichnung. Ein Stück, das als Zeichen selbst wie eine Marke aussähe, bleibt in Zeichenreferenzen."""
    def als_zeichen(stueck: str) -> str:
        klar = unescape(stueck)
        return stueck if MARKE.search(klar) else klar
    return _je_stueck(vorlage, als_zeichen)


def aus_modell(text: str, vorlage: str) -> str:
    """Eine Antwort des Modells in der Schreibweise der Vorlagen: das Modell schreibt Zeichen, also werden & < > im Text
    &amp; &lt; &gt; (auch ein & vor "lt;": steht das Original so, ist es dort Text). Die Marken bleiben; was wie eine
    Auszeichnung aussieht und nicht als Text im Original steht, bleibt roh, damit die Prüfung "Marken" es meldet."""
    return _je_stueck(text, lambda stueck: _gesichert(stueck, vorlage, _maskiert))


def gesichert(text: str, vorlage: str) -> str:
    """Ein Text in der Schreibweise der Vorlagen, der rohe Zeichen enthalten kann (eine frühere Antwort, ein Text von
    Hand): Zeichenreferenzen bleiben, ein rohes < oder > wird &lt; &gt;, ein & ohne Referenz &amp;. Was wie eine
    Auszeichnung aussieht und nicht als Text im Original steht, bleibt roh. Zweimal angewandt ändert sich nichts mehr."""
    return _je_stueck(text, lambda stueck: _gesichert(stueck, vorlage, _referenzen_bleiben))


def _gesichert(stueck: str, vorlage: str, maskieren) -> str:
    original = unescape(MARKE.sub(" ", vorlage))
    aus, pos = [], 0
    for m in AUSZEICHNUNG.finditer(stueck):
        if m.group(0) in original:                           # steht im Original als Text: bleibt Text
            continue
        aus += [maskieren(stueck[pos:m.start()]), m.group(0)]
        pos = m.end()
    return "".join(aus) + maskieren(stueck[pos:])


def _maskiert(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _referenzen_bleiben(text: str) -> str:
    return re.sub(r"&(?!(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);)", "&amp;", text).replace("<", "&lt;").replace(">", "&gt;")


def platzhalter(text: str) -> int:
    return sum(1 for m in MARKE.finditer(text) if m.group(3))
