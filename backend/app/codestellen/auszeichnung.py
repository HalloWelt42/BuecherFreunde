"""Codeblöcke in ausgezeichneten Formaten: EPUB (`<pre>`, Sprache aus `language-*` oder `lang-*`), Markdown und Text
(Zäune aus drei Backticks oder Tilden, Sprache aus dem Infotext). Die Lage ist im EPUB das Kapitel mit der Nummer des
Blocks darin, sonst die Zeile des Zauns."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup, Tag
from ebooklib import epub

from backend.app.codestellen.sprache import ENDUNGEN

ZAUN = re.compile(r"^(?P<einzug> {0,3})(?P<zaun>`{3,}|~{3,})\s*(?P<info>[^`\s]*)[^`]*$")
KLASSE = re.compile(r"^(?:language|lang|sourceCode|highlight-source)-?(?P<sprache>[\w+#-]+)$", re.I)
NAMEN = {"py": "python", "python3": "python", "js": "javascript", "node": "javascript", "jsx": "javascript", "ts": "typescript",
         "sh": "shell", "bash": "shell", "zsh": "shell", "console": "shell", "shell-session": "shell", "yml": "yaml",
         "text": "ausgabe", "output": "ausgabe", "plaintext": "ausgabe", "c++": "cpp", "c": "cpp"}


@dataclass
class Block:
    code: str
    sprache: str | None
    titel: str = ""
    zeile: int | None = None
    kapitel: str | None = None
    nr: int | None = None


def sprachname(wort: str) -> str | None:
    w = wort.strip().lower()
    if not w:
        return None
    return NAMEN.get(w) or ENDUNGEN.get(w) or (w if w in set(ENDUNGEN.values()) else None)


def text_bloecke(text: str) -> list[Block]:
    """Umzäunte Codeblöcke; ein Zaun ohne Ende reicht bis zum Schluss des Texts."""
    bloecke: list[Block] = []
    offen: tuple[str, str, int, int] | None = None          # (Zaun, Info, Zeile, Einzug)
    inhalt: list[str] = []
    for nr, zeile in enumerate(text.splitlines(), 1):
        m = ZAUN.match(zeile)
        if offen is None:
            if m:
                offen, inhalt = (m["zaun"], m["info"], nr, len(m["einzug"])), []
            continue
        if m and m["zaun"][0] == offen[0][0] and len(m["zaun"]) >= len(offen[0]) and not m["info"]:
            bloecke.append(_block(inhalt, offen))
            offen = None
            continue
        inhalt.append(zeile[offen[3]:] if zeile[:offen[3]].strip() == "" else zeile)
    if offen is not None:
        bloecke.append(_block(inhalt, offen))
    return [b for b in bloecke if b.code.strip()]


def _block(inhalt: list[str], offen: tuple[str, str, int, int]) -> Block:
    return Block(code="\n".join(inhalt).strip("\n"), sprache=sprachname(offen[1]), zeile=offen[2])


def _sprache_aus_klassen(*knoten: Tag | None) -> str | None:
    """`data-lang`, Klassen wie `language-python` und blanke Sprachnamen als Klasse (`sourceCode python`)."""
    for k in knoten:
        if k is None:
            continue
        for merkmal in ("data-lang", "data-language"):
            if (wert := k.get(merkmal)) and (s := sprachname(str(wert))):
                return s
        for klasse in k.get("class") or []:
            m = KLASSE.match(klasse)
            if m and (s := sprachname(m["sprache"])):
                return s
            if klasse.lower() not in ("text", "output", "plaintext") and (s := sprachname(klasse)):
                return s
    return None


def epub_bloecke(pfad: Path) -> list[Block]:
    """Die `<pre>`-Blöcke aller Dokumente in der Reihenfolge des Buchs."""
    buch = epub.read_epub(str(pfad), options={"ignore_ncx": True})
    reihe = [buch.get_item_with_id(i) for i, _ in buch.spine] or list(buch.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    bloecke: list[Block] = []
    for item in reihe:
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        roh = item.content if isinstance(item.content, bytes) else item.get_content()    # get_content setzt Leerraum neu
        seite = BeautifulSoup(roh.decode("utf-8", errors="replace"), "html.parser")
        for nr, pre in enumerate(seite.find_all("pre")):
            code = pre.get_text().strip("\n")
            if not code.strip():
                continue
            innen = pre.find("code")
            titel = ""
            vorher = pre.find_previous_sibling()
            if vorher is not None and len(vorher.get_text(strip=True)) <= 120 and re.match(r"^(Listing|Beispiel|Quelltext)\b",
                                                                                            vorher.get_text(strip=True), re.I):
                titel = vorher.get_text(" ", strip=True)
            bloecke.append(Block(code=code, sprache=_sprache_aus_klassen(innen, pre), titel=titel, kapitel=item.get_name(), nr=nr))
    return bloecke
