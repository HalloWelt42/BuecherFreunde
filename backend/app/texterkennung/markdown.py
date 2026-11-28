"""Die Nachbesserung einer Seite (BF-118) kommt als Markdown. Hier, und nur hier, wird es gelesen: zu Blöcken für die Textansicht
und zu schlichtem Text für Volltext, Suche und Vorlesen.

Was zählt: Überschriften (`#` bis `######`), Absätze (Zeilen bis zur Leerzeile), Aufzählungen (je Punkt ein Absatz mit seinem
Zeichen), Codeblöcke (drei Backticks, Zeichen für Zeichen), Tabellen (Kopf, Trennzeile, Reihen) und Bilder als eigene Zeile
`[Bild: Unterschrift]`. Hervorhebungen und Zeichen, die das Modell für Markdown maskiert, fallen weg; Trennlinien ebenso. Was ein
Modell um seine Antwort legt (Kästchenmarken, ein Codeblock um alles), nimmt `bereinigt` ab."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Blockart = Literal["ueberschrift", "absatz", "code", "tabelle", "bild"]

ZAUN = re.compile(r"^\s*(```|~~~)\s*([\w+#.-]*)\s*$")
UEBERSCHRIFT = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
PUNKT = re.compile(r"^\s*([-*+•])\s+(.*)$")
NUMMER = re.compile(r"^\s*(\d{1,3})[.)]\s+(.*)$")
BILD = re.compile(r"^\s*\[\s*Bild\s*(?::\s*(.*?))?\s*\]\s*$", re.IGNORECASE)
TRENNZEILE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
LINIE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
ZAHL = re.compile(r"^[-+]?[\d.,   ]*\d[\d.,   ]*\s*(%|€|m²|km|kg|s|min)?$")
MARKEN = re.compile(r"<\|(?:begin|end)_of_box\|>")
MASKE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~])")
FETT = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
SCHRAEG = re.compile(r"(?<![\w*])\*(?=\S)([^*]+?)(?<=\S)\*(?![\w*])")
INLINECODE = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class Block:
    art: Blockart
    text: str = ""
    zeilen: tuple[str, ...] = ()                   # Code: seine Zeilen, wie gedruckt
    sprache: str | None = None                     # Code: was der Zaun nennt
    kopf: tuple[str, ...] = ()                     # Tabelle: die Kopfzeile
    reihen: tuple[tuple[str, ...], ...] = ()       # Tabelle: die übrigen Zeilen, je so viele Zellen wie der Kopf
    zahlen: tuple[bool, ...] = ()                  # Tabelle: je Spalte, ob sie nur Zahlen trägt (rechtsbündig)


def bereinigt(antwort: str) -> str:
    """Die Antwort eines Modells ohne das, was es um das Markdown legt."""
    text = MARKEN.sub("", antwort).strip()
    zeilen = text.splitlines()
    if len(zeilen) >= 2 and (m := ZAUN.match(zeilen[0])) and m.group(2).lower() in ("markdown", "md") and ZAUN.match(zeilen[-1]):
        text = "\n".join(zeilen[1:-1]).strip()
    return text


def inline(text: str) -> str:
    """Ein Stück Fließtext ohne Markdown: Hervorhebungen und Masken weg, Leerraum einfach."""
    text = INLINECODE.sub(r"\1", text)
    text = FETT.sub(r"\2", text)
    text = SCHRAEG.sub(r"\1", text)
    text = MASKE.sub(r"\1", text)
    return " ".join(text.split())


def _zellen(zeile: str) -> list[str]:
    z = zeile.strip()
    if z.startswith("|"):
        z = z[1:]
    if z.endswith("|") and not z.endswith("\\|"):
        z = z[:-1]
    return [inline(c) for c in re.split(r"(?<!\\)\|", z)]


def _tabelle(kopfzeile: str, zeilen: list[str]) -> Block:
    kopf = _zellen(kopfzeile)
    breite = len(kopf)
    reihen = [(r + [""] * breite)[:breite] for r in (_zellen(z) for z in zeilen)]
    zahlen = tuple(bool(werte) and all(ZAHL.match(w) for w in werte)
                   for werte in ([r[i] for r in reihen if r[i]] for i in range(breite)))
    return Block("tabelle", kopf=tuple(kopf), reihen=tuple(tuple(r) for r in reihen), zahlen=zahlen)


def bloecke(md: str) -> list[Block]:
    """Die Blöcke der Seite in Lesereihenfolge."""
    zeilen = bereinigt(md).splitlines()
    aus: list[Block] = []
    absatz: list[str] = []

    def absatz_ende() -> None:
        if absatz and (text := inline(" ".join(absatz))):
            aus.append(Block("absatz", text))
        absatz.clear()

    i = 0
    while i < len(zeilen):
        z = zeilen[i]
        if m := ZAUN.match(z):
            absatz_ende()
            ende = next((j for j in range(i + 1, len(zeilen)) if ZAUN.match(zeilen[j]) and not ZAUN.match(zeilen[j]).group(2)), len(zeilen))
            code = zeilen[i + 1:ende]
            while code and not code[-1].strip():
                code.pop()
            if code:
                aus.append(Block("code", zeilen=tuple(code), sprache=m.group(2) or None))
            i = ende + 1
            continue
        if not z.strip() or LINIE.match(z):
            absatz_ende()
        elif m := UEBERSCHRIFT.match(z):
            absatz_ende()
            if text := inline(m.group(1)):
                aus.append(Block("ueberschrift", text))
        elif m := BILD.match(z):
            absatz_ende()
            aus.append(Block("bild", inline(m.group(1) or "")))
        elif z.lstrip().startswith("|") and i + 1 < len(zeilen) and TRENNZEILE.match(zeilen[i + 1]):
            absatz_ende()
            j = i + 2
            while j < len(zeilen) and zeilen[j].lstrip().startswith("|"):
                j += 1
            aus.append(_tabelle(z, zeilen[i + 2:j]))
            i = j
            continue
        elif m := PUNKT.match(z):
            absatz_ende()
            absatz.append(f"• {m.group(2)}")
        elif m := NUMMER.match(z):
            absatz_ende()
            absatz.append(f"{m.group(1)}. {m.group(2)}")
        else:
            absatz.append(z)
        i += 1
    absatz_ende()
    return aus


def schlichter_text(md: str) -> str:
    """Der Text der Seite ohne Gestalt, Block für Block auf eigenen Zeilen (wie die Textschicht einer Seite)."""
    teile: list[str] = []
    for b in bloecke(md):
        if b.art == "code":
            teile.extend(b.zeilen)
        elif b.art == "tabelle":
            teile.extend(" ".join(c for c in reihe if c) for reihe in (b.kopf, *b.reihen))
        elif b.text:
            teile.append(b.text)
    return "\n".join(teile)
