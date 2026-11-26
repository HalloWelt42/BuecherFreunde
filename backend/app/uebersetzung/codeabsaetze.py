"""Code in einfachen Absätzen erkennen (BF-71). Manche Bücher setzen Code nicht in `pre` oder `code`, sondern als gewöhnliche
Absätze, Zeile für Zeile ("pip install pygame", "for fruit in fruits:"), oft zwischen Zäunen aus Markdown ("```python" bis
"```"). Solche Absätze sind kein Text zum Übersetzen: sie werden keine Blöcke und bleiben Zeichen für Zeichen im Original,
wie `pre`. Die Merkmale kommen aus der Erkennung der Codestellen (codestellen/sprache.py, codestellen/auszeichnung.py), dazu
was Code in einem Absatz von Prosa unterscheidet.

Ein Absatz (oder Listenpunkt) ist Code, wenn
1. er ein Zaun ist oder zwischen einem Zaun und seinem Ende steht. Ein Ende ist ein Zaun ohne Sprache ("```"); ein Zaun mit
   Sprache ("```python") beginnt immer einen neuen Block, auch wenn dem vorigen das Ende fehlt. Zwischen Zaun und Ende muss
   überwiegend Code stehen, sonst gelten nur die Zäune selbst als Code. Ein Zaun ohne Ende reicht bis zum ersten Absatz mit
   Prosa oder zur ersten Zwischenzeile ohne Merkmal von Code ("2. Creating a Window:", ein nummerierter Punkt oder eine Zeile
   mit Doppelpunkt am Ende). Zäune ohne Buchstaben ("```") sind selbst keine Blöcke, zählen hier aber mit (bloecke.py).
2. er stark wie Code gebaut ist: eine Zeile von vorn bis hinten Code (Zuweisung, Aufruf, Kopf eines Blocks, import, Befehl in
   der Kommandozeile, Pfad, Zeile aus JSON, die Merkmale der Codestellen mit Anker am Zeilenanfang).
3. er nur schwache Merkmale hat (ein Aufruf mitten in der Zeile, ein Vergleich, return) und zwischen zwei Absätzen mit Code
   steht, oder in Festbreitenschrift gesetzt ist (Klasse mit Festbreitenschrift im CSS des Buchs, Schrift im Stil am Element,
   Klassen wie code oder literal) und ein Merkmal hat oder neben Code steht. Setzt ein Dokument mindestens die Hälfte seiner
   Absätze in Festbreitenschrift, ist das seine Grundschrift und kein Zeichen für Code.

Prosa ist nie Code, auch nicht mit einzelnen Codewörtern: ein Satz mit Satzzeichen am Ende, viele kleine englische Wörter
(ohne die Schlüsselwörter, wo die Zeile Satzzeichen von Code trägt) oder eine lange Folge gewöhnlicher Wörter. Nur zwischen
zwei Zäunen zählt auch Prosa als Code (Kommentare, denen das Zeichen fehlt)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from backend.app.codestellen.auszeichnung import ZAUN
from backend.app.codestellen.sprache import MERKMALE
from backend.app.uebersetzung.sprache import STOPP_EN

STARK = 3                                            # so viele Punkte macht eine Zeile allein zu Code
SCHWACH = 1                                          # so viele braucht sie neben Code oder in Festbreitenschrift
GRUNDSCHRIFT_AB = 8                                  # ab so vielen Absätzen sagt der Anteil in Festbreitenschrift etwas
GRUNDSCHRIFT_ANTEIL = 0.5

#: Merkmale der Codestellen, die eine Zeile von vorn bestimmen (Gewicht ab 2). Ohne Shell (die Befehle stehen hier mit
#: Argumenten), ohne SQL (Wörter wie select beginnen auch Sätze) und ohne YAML (jede Zeile "Wort:" wäre sonst Code).
ANKER: tuple[tuple[re.Pattern[str], int], ...] = tuple(
    (m, g) for sprache, ms in MERKMALE.items() if sprache not in ("shell", "sql", "yaml")
    for m, g in ms if g >= 2 and m.pattern.replace("(?i)", "").startswith("^"))
#: dieselben ohne Anker: zeigen Code mitten in einer Zeile, darum nur ein schwaches Merkmal
IM_SATZ: tuple[re.Pattern[str], ...] = tuple(
    m for sprache, ms in MERKMALE.items() if sprache not in ("shell", "yaml") for m, g in ms
    if g >= 2 and not m.pattern.replace("(?i)", "").startswith("^"))

EINDEUTIGE_BEFEHLE = ("sudo|apt|apt-get|brew|pip|pip3|pipx|npm|npx|yarn|pnpm|git|docker|kubectl|curl|wget|python|python3|py|"
                      "node|deno|bun|ssh|scp|chmod|chown|mkdir|rmdir|systemctl|journalctl|composer|cargo|rustc|gcc|g\\+\\+|"
                      "clang|javac|dotnet|conda|virtualenv|uv|pytest|ollama|php|ruby|gem|bundle|go|java")
MEHRDEUTIGE_BEFEHLE = "cd|ls|cat|rm|cp|mv|make|source|export|echo|touch|grep|sed|awk|find|tar|unzip|less|head|tail|man|open|set"

#: Zeilen, die von vorn bis hinten Code sind: (Muster, Punkte)
ZEILE: tuple[tuple[re.Pattern[str], int], ...] = tuple((re.compile(m), g) for m, g in (
    (r"^\s*[A-Za-z_][\w.]*(?:\[[^\]]*\])?(?:\s*,\s*[A-Za-z_][\w.]*)*\s*(?:[-+*/%&|^]|//|\*\*|<<|>>)?=(?!=)\s*\S", 3),  # Zuweisung
    (r"^\s*(?:await\s+|return\s+|yield\s+)?(?:[a-z_]\w*|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\(.*\)\s*;?\s*(?:(?:#|//).*)?$", 3),  # Aufruf
    (r"^\s*(?:if|elif|while)\s+.+:\s*(?:#.*)?$", 3),                                  # Kopf eines Blocks (Python)
    (r"^\s*for\s+[\w, ()\[\]]+\s+in\s+.+:\s*(?:#.*)?$", 3),
    (r"^\s*with\s+.+\s+as\s+\w+\s*:\s*(?:#.*)?$", 3),
    (r"^\s*(?:if|for|while|switch|catch)\s*\(.*\)\s*\{?\s*$", 3),                     # Kopf eines Blocks (C, Java, JS)
    (r"^\s*\}\s*(?:else\b.*|catch\b.*|finally\b.*|while\b.*)?\{?\s*;?\s*$", 3),
    (r"^\s*(?:function|fn|func|fun|sub|proc)\s+\w+\s*\(.*\)\s*(?:[:{]|->.*)?\s*$", 3),
    (r"^\s*(?:const|let|var)\s+[\w{}\[\], ]+\s*=", 3),
    (r"^\s*@[A-Za-z_][\w.]*(?:\(.*\))?\s*$", 3),                                      # Dekorator
    (r"^\s*#include\b", 3),
    (r"^\s*(?:SELECT|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|CREATE\s+(?:TABLE|INDEX|VIEW|UNIQUE)|ALTER\s+TABLE|DROP\s+TABLE)\b", 3),
    (r"(?i)^\s*select\s+.+\s+from\s+\w+", 3),
    (r'^\s*"[^"]+"\s*:\s*(?:"[^"]*"|-?\d[\d.]*|true|false|null|\[|\{)\s*,?\s*$', 3),  # Zeile aus JSON
    (r"^\s*(?:\$|%|>|PS>|[A-Za-z]:\\[^>]*>)\s+\S", 3),                               # Eingabe nach einer Aufforderung
    (rf"^\s*(?:{EINDEUTIGE_BEFEHLE})\s+\S", 3),                                       # Befehl mit Argument
    (rf"^\s*(?:{MEHRDEUTIGE_BEFEHLE})\s+(?:\S*[-/.=~$\\*_]\S*|\S+\s+\S*[-/.=~$\\*_])", 3),  # Befehl, der nur mit Pfad oder Option einer ist
    (r"^\s*(?:\.{0,2}/|~/|[A-Za-z]:\\|[\w.-]+\\)[\w.\\/ -]*$", 3),                    # Pfad als ganze Zeile
    (r"^\s*(?:return|yield|raise|pass|break|continue|del|assert|throw)\b", 2),
    (r"^\s*(?:#|//|--)\s?\S", 1),                                                     # Kommentar
))
#: Zeichen von Code mitten in einer Zeile, je ein Punkt
HINWEISE: tuple[re.Pattern[str], ...] = tuple(re.compile(m) for m in (
    r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\(",                                            # gepunkteter Aufruf
    r"[\w)\]\"']\s*(?:==|!=|<=|>=|&&|\|\||<|>)\s*[\w(\"'\[-]",                          # Vergleich
    r"\b[a-z_]\w*\[[^\]]+\]",                                                          # Zugriff mit Index
    r"\[\s*(?:\"[^\"]*\"|'[^']*'|\d+)\s*(?:,\s*(?:\"[^\"]*\"|'[^']*'|\d+)\s*)+\]",      # Liste aus Werten
    r"(?<![\w-])--?[A-Za-z][\w-]*",                                                    # Option (--dry, -m)
))

ZEICHENKETTE = re.compile(r'"(?:[^"\\\n]|\\.)*"|(?<![\w])\'(?:[^\'\\\n]|\\.)*\'(?![\w])')
WORT = re.compile(r"[A-Za-z][a-z]*")                 # ein gewöhnliches Wort: Buchstaben, nur der erste darf groß sein
RAND = "\"'()[]{}.,:;!?"
SATZENDE = re.compile(r"[.!?][\"')\]]*\s*$")
CODEZEICHEN = re.compile(r"[=(){}\[\];]|:\s*$|\w\.\w|_|->|=>|::")
NUMMERIERT = re.compile(r"^\s*\d+[.)]\s")
#: Code mit einem Kommentar dahinter, getrennt durch mindestens zwei Leerzeichen, auch geschützte
NACHGESTELLT = re.compile(r"^(.*?\S)[ \t\u00a0]{2,}(?:#\s*)?\S.*$")
#: kleine englische Wörter, die zugleich Schlüsselwörter sind; in Zeilen mit Satzzeichen von Code zählen sie nicht als Prosa
SCHLUESSELWOERTER = frozenset("if else elif for while in not and or is as from import with def class return".split())

#: Schriften mit fester Breite, wie sie im CSS stehen
FESTBREIT = re.compile(r"font-family\s*:[^;}]*(?:mono|courier|consol|menlo|monaco|inconsolata|cascadia|iosevka|\bhack\b|source code)",
                       re.I)
#: Klassen, die Code auszeichnen (DocBook, Konverter); ihr Inhalt ist auch im Satz Code
CODE_KLASSEN = frozenset({"code", "literal", "filename", "command", "computeroutput",
                          "userinput", "varname", "classname", "methodname", "envar", "sourcecode", "source-code", "codeblock",
                          "code-block", "verbatim", "preformatted", "terminal", "console"})
CSS_REGEL = re.compile(r"([^{}]+)\{([^{}]*)\}")
CSS_KOMMENTAR = re.compile(r"/\*.*?\*/", re.S)
CSS_KLASSE = re.compile(r"\.(-?[A-Za-z_][\w-]*)")


@dataclass(frozen=True)
class Absatz:
    """Was die Erkennung von einem Lauf wissen muss."""
    text: str                                        # Klartext, Zeilenwechsel (br) als \n
    kandidat: bool                                   # Absatz oder Listenpunkt; Überschriften, Zellen, Fußnoten nie
    festbreit: bool = False


# -- Festbreitenschrift -------------------------------------------------------------------------------------------------------

def festbreit_klassen(css: str) -> frozenset[str]:
    """Die Klassen, denen ein Stylesheet eine Schrift mit fester Breite gibt."""
    klassen: set[str] = set()
    for selektor, regeln in CSS_REGEL.findall(CSS_KOMMENTAR.sub(" ", css)):
        if FESTBREIT.search(regeln):
            klassen.update(CSS_KLASSE.findall(selektor))
    return frozenset(klassen)


def festbreit_im_stil(stil: str) -> bool:
    """Ob ein Stil am Element (style="...") eine Schrift mit fester Breite setzt."""
    return bool(FESTBREIT.search(stil))


# -- Zeilen -------------------------------------------------------------------------------------------------------------------

def punkte(zeile: str) -> int:
    """Wie sehr eine Zeile Code ist: die Zeilenform (stark), dazu je ein Punkt für Zeichen von Code mitten in der Zeile."""
    form = max([g for m, g in ZEILE if m.search(zeile)] + [g for m, g in ANKER if m.search(zeile)] + [0])
    hinweise = sum(1 for m in HINWEISE if m.search(zeile)) + (1 if any(m.search(zeile) for m in IM_SATZ) else 0)
    return form + hinweise


def prosa(zeile: str) -> bool:
    """Ob eine Zeile ein Satz ist: Satzzeichen am Ende, viele kleine englische Wörter oder lange Wortfolgen. Was in
    Anführungszeichen steht, zählt nicht mit (Zeichenketten im Code)."""
    ohne = ZEICHENKETTE.sub(" ", zeile)
    teile = ohne.split()
    woerter = [w for t in teile if (w := t.strip(RAND)) and WORT.fullmatch(w)]
    if not woerter:
        return False
    code = bool(CODEZEICHEN.search(ohne))
    klein = [w.lower() for w in woerter]
    stopp = sum(1 for w in klein if w in STOPP_EN and not (code and w in SCHLUESSELWOERTER))
    if len(woerter) >= 3 and SATZENDE.search(ohne):
        return True
    if stopp >= 2 and stopp >= 0.3 * len(woerter):
        return True
    return len(woerter) >= 10 and len(woerter) >= 0.7 * len(teile)


def bewertet(zeile: str) -> tuple[int, bool]:
    """Punkte einer Zeile und ob sie Prosa ist; Code mit einem nachgestellten Kommentar, dem das Zeichen fehlt
    ("clock.tick(FPS)   Limit the frame rate", mit mindestens zwei Leerzeichen davor), zählt als Code."""
    m = NACHGESTELLT.match(zeile)
    if m and (p := punkte(m.group(1))) >= STARK:
        return p, False
    return punkte(zeile), prosa(zeile)


def _zeilen(text: str) -> list[str]:
    return [z for z in text.split("\n") if z.strip()]


def zaun(text: str) -> bool:
    """Ob ein Absatz mit einem Zaun aus Markdown beginnt (```python, ~~~)."""
    zeilen = _zeilen(text)
    return bool(zeilen) and bool(ZAUN.match(zeilen[0]))


def ende(text: str) -> bool:
    """Ob ein Absatz ein Zaun ohne Sprache ist, der einen Block schließen kann ("```")."""
    zeilen = _zeilen(text)
    m = ZAUN.match(zeilen[0]) if zeilen else None
    return m is not None and not m.group("info")


def ist_prosa(text: str) -> bool:
    return any(bewertet(z)[1] for z in _zeilen(text))


def zwischenzeile(text: str) -> bool:
    """Eine Zeile zwischen Code und Text ohne Merkmal von Code: ein nummerierter Punkt oder ein Doppelpunkt am Ende."""
    return staerke(text) == 0 and (text.rstrip().endswith(":") or bool(NUMMERIERT.match(text)))


def staerke(text: str) -> int:
    """Wie sehr ein Absatz Code ist: STARK, wenn mindestens die Hälfte seiner Zeilen stark ist; SCHWACH, wenn eine Zeile ein
    Merkmal hat; 0 sonst und immer, wenn eine Zeile Prosa ist."""
    zeilen = [bewertet(z) for z in _zeilen(text)]
    if not zeilen or any(ist for _, ist in zeilen):
        return 0
    je = [p for p, _ in zeilen]
    if 2 * sum(p >= STARK for p in je) >= len(je):
        return STARK
    return SCHWACH if max(je) >= SCHWACH else 0


def code_im_satz(text: str) -> bool:
    """Ob ein Stück in Festbreitenschrift mitten im Satz Code ist: ein einzelnes Wort ohne Leerraum, oder ein Merkmal von
    Code und keine Prosa ("ACCESS DENIED" in einem Roman bleibt Text)."""
    t = text.strip()
    if not t:
        return False
    if not re.search(r"\s", t) and len(t) <= 80:
        return True
    return staerke(t) >= SCHWACH


# -- Absätze eines Dokuments --------------------------------------------------------------------------------------------------

def _zaeune(absaetze: list[Absatz]) -> set[int]:
    code: set[int] = set()
    n, i = len(absaetze), 0
    while i < n:
        if not (absaetze[i].kandidat and zaun(absaetze[i].text)):
            i += 1
            continue
        j = i + 1
        while j < n and absaetze[j].kandidat and not zaun(absaetze[j].text):
            j += 1
        innen = range(i + 1, j)
        if j < n and absaetze[j].kandidat and ende(absaetze[j].text):     # geschlossen
            prosa_n = sum(ist_prosa(absaetze[k].text) for k in innen)
            code.update(range(i, j + 1) if 2 * prosa_n <= len(innen) else (i, j))
            i = j + 1
            continue
        code.add(i)                                              # ohne Ende: bis zur ersten Prosa
        k = i + 1
        while k < j and not ist_prosa(absaetze[k].text) and not zwischenzeile(absaetze[k].text):
            code.add(k)
            k += 1
        i = max(k, i + 1)                                        # ein Zaun mit Sprache bei k beginnt den nächsten Block
    return code


def erkennen(absaetze: list[Absatz]) -> set[int]:
    """Die Stellen der Absätze, die Code sind."""
    n = len(absaetze)
    grundschrift = n >= GRUNDSCHRIFT_AB and sum(a.festbreit for a in absaetze) >= GRUNDSCHRIFT_ANTEIL * n
    festbreit = [a.festbreit and a.kandidat and not grundschrift for a in absaetze]
    code = _zaeune(absaetze)
    je = [staerke(a.text) if a.kandidat and i not in code else 0 for i, a in enumerate(absaetze)]
    code.update(i for i in range(n) if je[i] >= STARK)

    def nachbarn(i: int) -> tuple[bool, bool]:
        return i > 0 and i - 1 in code, i + 1 < n and i + 1 in code

    for i, a in enumerate(absaetze):                           # schwache Merkmale: nur neben Code oder in Festbreitenschrift
        if i in code or not a.kandidat or ist_prosa(a.text):
            continue
        vorn, hinten = nachbarn(i)
        if (je[i] >= SCHWACH and (vorn and hinten or festbreit[i])) or (festbreit[i] and (vorn or hinten)):
            code.add(i)
    return code


def klassen_aus(stylesheets: Iterable[str]) -> frozenset[str]:
    return frozenset().union(*(festbreit_klassen(css) for css in stylesheets))
