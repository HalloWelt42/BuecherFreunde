"""Vorlagen mit Marken (BF-71, wie in Nachschlag): ans Modell geht nur Text. Auszeichnungen im Satz (kursiv, fett, Verweis)
stehen als nummerierte Klammermarken `<t1>..</t1>`, alles Unantastbare (Code, Formeln, Bilder, Fußnotenzeichen) als
Platzhalter `<x2/>`, dessen Inhalt nie zum Modell geht. Die Nummern zählen in der Tiefe: eine Marke schließt mit ihrer eigenen
Nummer, innere Marken tragen höhere Nummern als die äußere.

Eine Übersetzung taugt nur, wenn sie jede Marke der Vorlage genau einmal trägt, in derselben Schachtelung und ohne fremde
Auszeichnung; die Stellung im Satz darf sich ändern. Was dabei eindeutig und verlustfrei zu berichtigen ist, berichtigt
`reparieren`: eine Klammermarke, die doppelt steht, behält nur das Vorkommen, das am besten zum Original passt (gleicher
umschlossener Text, sonst das erste), die übrigen und jedes Stück von ihr ohne Gegenstück verlieren die Marke; eine
Klammermarke, die es im Original nicht gibt, verliert sie auch. Der Text bleibt immer. Platzhalter fasst das nie an: einer,
der fehlt oder fremd ist, bleibt ein Befund.

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
    """Die Marken einer Übersetzung passen nicht zur Vorlage; `stelle` ist das Stück, an dem es auffiel, `nr` die Marke."""

    def __init__(self, grund: str, stelle: str = "", nr: int = 0) -> None:
        super().__init__(grund)
        self.grund, self.stelle, self.nr = grund, stelle, nr


@dataclass(frozen=True)
class Berichtigung:
    """Eine Marke, die `reparieren` weggenommen hat: warum, und der Text, der sie trug (oder das Stück ohne Gegenstück)."""
    grund: str
    stelle: str


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
            raise MarkenFehler(f"Die Marke {n} gibt es im Original nicht", m.group(0), n)
        if zu:
            if stapel[-1][0] != n:
                raise MarkenFehler(f"Die Marke {n} ist falsch geschlossen", m.group(0), n)
            stapel.pop()
            continue
        if n in gesehen:
            raise MarkenFehler(f"Die Marke {n} steht doppelt da", m.group(0), n)
        if bool(x) != plan_[n].atom:
            raise MarkenFehler(f"Die Marke {n} hat die falsche Art", m.group(0), n)
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
        raise MarkenFehler(f"Die Marke {stapel[-1][0]} ist nicht geschlossen", f"<t{stapel[-1][0]}>", stapel[-1][0])
    fehlt = sorted(set(plan_) - set(gesehen))
    if fehlt:
        n = fehlt[0]
        raise MarkenFehler(f"Die Marke {n} fehlt", f"<x{n}/>" if plan_[n].atom else f"<t{n}>", n)
    anders = sorted(n for n in gesehen if gesehen[n] != plan_[n].oben)
    if anders:
        n = anders[0]
        raise MarkenFehler(f"Die Marke {n} ist anders geschachtelt", f"<t{n}>" if not plan_[n].atom else f"<x{n}/>", n)
    return wurzel


def _klammern(stuecke: list[re.Match[str]], nr: int) -> tuple[list[tuple[int, int]], list[int]]:
    """Die Vorkommen einer Klammermarke als Paare (Stelle von Anfang und Ende in `stuecke`), jedes Ende zum letzten offenen
    Anfang; dazu die Stücke ohne Gegenstück."""
    paare: list[tuple[int, int]] = []
    offen: list[int] = []
    allein: list[int] = []
    for i, m in enumerate(stuecke):
        if m.group(2) is None or int(m.group(2)) != nr:
            continue
        if not m.group(1):
            offen.append(i)
        elif offen:
            paare.append((offen.pop(), i))
        else:
            allein.append(i)
    return sorted(paare), sorted(allein + offen)


def _umschlossen(text: str, stuecke: list[re.Match[str]], paar: tuple[int, int]) -> str:
    return klartext(text[stuecke[paar[0]].end():stuecke[paar[1]].start()])


def _am_besten(text: str, stuecke: list[re.Match[str]], paare: list[tuple[int, int]], original: str) -> tuple[int, int]:
    """Das Vorkommen, das zum Original passt: derselbe umschlossene Text, dann ohne Unterschied von Groß und Klein, sonst das
    erste."""
    for gleich in (lambda a: a == original, lambda a: a.casefold() == original.casefold()):
        treffer = next((p for p in paare if gleich(_umschlossen(text, stuecke, p))), None)
        if treffer is not None:
            return treffer
    return paare[0]


def reparieren(vorlage: str, text: str) -> tuple[str, list[Berichtigung]]:
    """Die Übersetzung mit berichtigten Klammermarken (siehe oben) und was weggenommen wurde; unverändert, wenn die Marken
    passen oder nichts eindeutig zu berichtigen ist. Was danach noch nicht passt, meldet die Prüfung."""
    plan_ = plan(vorlage)
    try:
        lesen(plan_, text)
        return text, []
    except MarkenFehler:
        pass
    stuecke = list(MARKE.finditer(text))
    weg: set[int] = set()                              # Stellen in `stuecke`, die wegfallen
    berichtigt: list[tuple[int, Berichtigung]] = []     # je weggenommenes Vorkommen, mit der Stelle seines Anfangs
    for nr in sorted({int(m.group(2)) for m in stuecke if m.group(2)}):
        paare, allein = _klammern(stuecke, nr)
        if nr not in plan_ or plan_[nr].atom:
            grund, bleibt = f"Die Marke {nr} gibt es im Original nicht: entfernt, der Text bleibt", None
        elif paare and len(paare) + len(allein) > 1:
            grund = (f"Die Marke {nr} stand doppelt da: sie bleibt nur an der Stelle, die zum Original passt; hier fiel sie weg, "
                     "der Text bleibt")
            umschlossen = re.search(rf"<t{nr}>(.*?)</t{nr}>", vorlage, re.S)
            bleibt = _am_besten(text, stuecke, paare, klartext(umschlossen.group(1)) if umschlossen else "")
        else:
            continue
        for paar in paare:
            if paar != bleibt:
                weg.update(paar)
                berichtigt.append((paar[0], Berichtigung(grund, _umschlossen(text, stuecke, paar))))
        weg.update(allein)
        berichtigt += [(i, Berichtigung(grund, stuecke[i].group(0))) for i in allein]
    if not weg:
        return text, []
    aus, pos = [], 0
    for i in sorted(weg):
        aus.append(text[pos:stuecke[i].start()])
        pos = stuecke[i].end()
    return "".join(aus) + text[pos:], [b for _, b in sorted(berichtigt, key=lambda e: e[0])]


def umgebung(vorlage: str, nr: int, woerter: int = 3) -> str:
    """Wo ein Platzhalter im Original steht, mit ein paar Wörtern davor und dahinter, wie das Modell es sieht."""
    m = re.search(rf"<x{nr}/>", vorlage)
    if m is None:
        return ""
    vor = re.search(rf"(?:\S+\s*){{0,{woerter}}}$", fuer_modell(vorlage[:m.start()]))
    nach = re.match(rf"(?:\s*\S+){{0,{woerter}}}", fuer_modell(vorlage[m.end():]))
    return ((vor.group(0) if vor else "") + m.group(0) + (nach.group(0) if nach else "")).strip()


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
