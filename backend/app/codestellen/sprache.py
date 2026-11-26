"""Sprache einer Codestelle: zuerst, was das Buch sagt (Dateiname mit Endung, Kastentitel, Beschriftung), dann der Inhalt
nach Merkmalen. Das Ergebnis trägt eine Sicherheit von 0 bis 1 und woher es kommt. Kästen "Ausgabe" und "Terminal" sind
Sprachen wie andere auch (ausgabe, shell), nur keine zum Ausführen."""

from __future__ import annotations

import ast
import json
import re
import textwrap
from dataclasses import dataclass

from backend.app.codestellen.modelle import Quelle

ENDUNGEN = {
    "py": "python", "pyw": "python", "js": "javascript", "mjs": "javascript", "cjs": "javascript", "ts": "typescript",
    "tsx": "typescript", "php": "php", "sql": "sql", "sh": "shell", "bash": "shell", "zsh": "shell", "yml": "yaml",
    "yaml": "yaml", "json": "json", "xml": "xml", "xsd": "xml", "wsdl": "xml", "html": "html", "htm": "html", "css": "css",
    "toml": "toml", "c": "cpp", "h": "cpp", "cpp": "cpp", "hpp": "cpp", "ino": "cpp", "java": "java", "go": "go",
    "rs": "rust", "rb": "ruby", "ini": "ini", "cfg": "ini", "conf": "ini", "md": "markdown", "twig": "twig",
    "svelte": "svelte", "proto": "proto", "env": "dotenv",
}
DATEI = re.compile(r"(?<![\w.])([\w./-]*\w)\.(" + "|".join(sorted(ENDUNGEN, key=len, reverse=True)) + r")\b(?![.\w])", re.I)
SONDERDATEIEN = {"dockerfile": "docker", "makefile": "shell", ".env": "dotenv", "composer.json": "json"}

# Wörter in Titel und Beschriftung, in dieser Reihenfolge geprüft (Ausgabe und Terminal vor den Sprachen)
# Titel, die eine Ausgabe oder einen Befehl zeigen, auch wenn sie eine Datei nennen ("Ausgabe von schaetzer.py", "Lauf vom
# 12.10.", "python erp_rechner.py --tabelle")
AUSGABE_TITEL = re.compile(r"\b(ausgabe|output|ergebnis|meldung(en)?|selbsttest|protokoll)\b|^\s*lauf\b|\(lauf vom", re.I)
BEFEHL_TITEL = re.compile(r"^\s*((terminal|shell|konsole|kommandozeile|bash|zsh)\b|(\$\s*)?(python3?|php|node|npx|uv|pip3?)\s+"
                          r"(-\S|[\w./-]+\.\w+))", re.I)
WOERTER: list[tuple[re.Pattern[str], str]] = [(re.compile(m, re.I), s) for m, s in [
    (r"\btypescript\b", "typescript"), (r"\bjavascript\b|\bnode(\.js)?\b", "javascript"), (r"\bpython\b", "python"),
    (r"\bphp\b", "php"), (r"\bsql(ite)?\b", "sql"), (r"\byaml\b", "yaml"), (r"\bjson\b", "json"), (r"\bxml\b", "xml"),
    (r"\bhtml\b", "html"), (r"\bdocker(file)?\b", "docker"), (r"\b(terminal|shell|bash)\b", "shell"),
]]

# Merkmale je Sprache mit Gewicht (3: kennzeichnend, 1: Hinweis, negativ: spricht dagegen); je Zeile zählt jedes einmal
MERKMALE: dict[str, list[tuple[re.Pattern[str], int]]] = {s: [(re.compile(m), g) for m, g in ms] for s, ms in {
    "python": [(r"^\s*(async )?def \w+\(.*\)?\s*(->.*)?:\s*(#.*)?$", 3), (r"^\s*class \w+(\(.*\))?:\s*$", 3),
               (r"^\s*from [\w.]+ import [\w., ()*]+$", 3), (r"^\s*import [\w.]+( as \w+)?(, [\w.]+)*\s*$", 3),
               (r"^\s*(elif .*|else|try|finally|except\b.*)\s*:\s*(#.*)?$", 3), (r"\bprint\(", 3), (r"\bself\.", 3),
               (r"\b(None|True|False)\b", 2), (r"\bf\"[^\"]*\{|\bf'[^']*\{", 3), (r"^\s*@\w+", 1), (r"\blambda \w*:", 3),
               (r"^\s*(if|for|while|with) .*:\s*(#.*)?$", 2), (r"\b(len|range|enumerate|isinstance|dict|list)\(", 1),
               (r"^\s*#( |$)", 1), (r"[;{]\s*$", -2), (r"\$\w", -2), (r"===|=>|\bconst |\bvar |->\w+\(", -3)],
    "javascript": [(r"\b(const|let|var) [\w{}\[\], ]+\s*=", 3), (r"\bfunction\b\s*\w*\s*\(", 3), (r"=>", 2),
                   (r"\bconsole\.\w+\(", 3), (r"===|!==", 3), (r";\s*$", 1), (r"\b(undefined|null)\b", 1), (r"\brequire\(", 3),
                   (r"^\s*(import|export)\b.*\bfrom\s*['\"]", 3), (r"^\s*export (default |const |function |class )", 3),
                   (r"\bawait\b", 1), (r"\.then\(", 2), (r"^\s*//", 1), (r"\bthis\.", 2), (r"\bMath\.", 2), (r"\b(window|document)\.", 2),
                   (r"\bnew [A-Z]\w*\(", 1), (r"^\s*constructor\s*\(", 3), (r"\.(push|map|forEach|filter|reduce)\(", 1), (r"\{\s*$", 1), (r"\$\w+\s*=|->\w|<\?php|\becho\b", -3),
                   (r"^\s*(def|elif|import \w+$)", -3)],
    "typescript": [(r"[\w)]\s*:\s*(number|string|boolean|void|any|unknown|never)(\[\])?\b", 3), (r"\binterface \w+", 3),
                   (r"\btype \w+\s*=", 3), (r"\b(private|public|readonly) \w+\s*[:(]", 2), (r"\bas const\b", 2),
                   (r"\bimplements \w+", 1), (r"\$\w+|<\?php", -3)],
    "php": [(r"<\?php", 6), (r"\$[a-z_]\w*", 3), (r"^\s*#\[\w+", 3), (r"^\s*(enum \w+|case \w+ = .*;)", 2),
            (r"\bfunction \w+\(.*\)\s*:\s*\??[\w\\]+", 2), (r"\s\\$", -3), (r"->\w+", 2), (r"\becho\b", 3), (r"::\w+", 1), (r"\bfunction \w+\(.*\)", 1),
            (r";\s*$", 1), (r"\b(public|private|protected) (static )?(function|\??\w+ \$|\$)", 3), (r"^\s*namespace\b", 3),
            (r"^\s*use [A-Z][\w\\]+;", 3), (r"^\s*(def |import \w+$|elif )", -3)],
    "sql": [(r"(?i)^\s*(select|insert\s+into|create\s+(table|index|view|unique|virtual)|update\s+\w+\s+set|delete\s+from|"
             r"alter\s+table|drop\s+table|with\s+\w+\s+as|pragma)\b", 3),
            (r"(?i)\b(from|where|join|group\s+by|order\s+by|values|primary\s+key|not\s+null|references|integer|varchar)\b", 1),
            (r"^\s*(def|const|function|import)\b|\$\w", -3)],
    "shell": [(r"^\s*\$ \w", 3), (r"\$\{?[A-Z_][A-Z0-9_]*\b", 2), (r"\s\\$", 3), (r"^\s*echo\s+[\"'$]", 2), (r"^\s*(sudo|apt|apt-get|brew|pip3?|npm|npx|yarn|pnpm|git|docker|cd|ls|cat|curl|wget|python3?|php|"
              r"composer|make|ssh|scp|chmod|chown|mkdir|rm|cp|mv|export|source|systemctl|journalctl|kubectl|uv|node|deno|ollama|"
              r"mlx_lm\.\w+|huggingface-cli)( |$)", 3), (r"\s--?[a-zA-Z][\w-]*", 1), (r"\|\s*\w+", 1), (r"&&", 1),
              (r"^\s*(def|class|function|const|let)\b|[;{]\s*$|\(.*\)\s*:\s*$", -2)],
    "yaml": [(r"^\s*[\w.-]+:\s*(\S.*)?$", 1), (r"^\s*- \S", 1), (r"^---\s*$", 2), (r"[;{}()]\s*$|^\s*(def|import|from) ", -2)],
    "json": [(r"^\s*[\[{]\s*$", 1), (r"^\s*\"[^\"]+\"\s*:", 2), (r"^\s*[\]}],?\s*$", 1)],
    "xml": [(r"^\s*<[\w:.-]+[ >/]", 2), (r"</[\w:.-]+>", 2), (r"<\?xml", 6)],
    "html": [(r"<(html|head|body|div|span|p|a|ul|li|script|style|form|input|button|h[1-6])\b", 3)],
    "cpp": [(r"#include\s*[<\"]", 6), (r"\bstd::", 3), (r"\b(void|int|char|float|double|bool|uint\d+_t)\s+\w+\s*\(.*\)\s*\{?\s*$", 3),
            (r"\bSerial\.", 3), (r"\$\w|=>|\bdef ", -3)],
}.items()}

# Eindeutige Zeichen am Anfang, die ohne Abwägen entscheiden
ANFANG: list[tuple[re.Pattern[str], str]] = [(re.compile(m), s) for m, s in [
    (r"<\?php", "php"), (r"^#!.*\bpython", "python"), (r"^#!.*\b(ba|z)?sh\b", "shell"), (r"^#!.*\bnode\b", "javascript"),
    (r"^\s*<\?xml", "xml"), (r"(?i)^\s*<!doctype html", "html"),
]]

DATEI_SICHER, TITEL_SICHER, ANFANG_SICHER = 0.95, 0.9, 0.95
UNSICHER_TROTZ_TITEL = 0.4
INHALT_HOECHSTENS = 0.9
INHALT_VOLL = 1.2                    # ab so vielen Punkten je Zeile zählt der Inhalt voll


@dataclass(frozen=True)
class Befund:
    sprache: str | None
    sicherheit: float
    quelle: Quelle


KEINER = Befund(None, 0.0, "")


def aus_datei(name: str) -> str | None:
    """Sprache aus einem Dateinamen oder einem Text, der einen nennt ("kap01/schaetzer.py")."""
    klein = name.strip().lower()
    for sonder, sprache in SONDERDATEIEN.items():
        if klein.endswith(sonder):
            return sprache
    treffer = DATEI.findall(name)
    return ENDUNGEN.get(treffer[-1][1].lower()) if treffer else None


def dateiname(text: str) -> str:
    """Der letzte Dateiname mit bekannter Endung in einem Text, sonst leer."""
    treffer = list(DATEI.finditer(text))
    return treffer[-1].group(0) if treffer else ""


def aus_woertern(text: str) -> str | None:
    for muster, sprache in WOERTER:
        if muster.search(text):
            return sprache
    return None


def _punkte(zeilen: list[str]) -> dict[str, float]:
    """Je Sprache die Summe der Gewichte über alle Zeilen, geteilt durch die Zeilen (nie unter 0)."""
    return {s: max(0.0, sum(g for z in zeilen for m, g in ms if m.search(z)) / len(zeilen)) for s, ms in MERKMALE.items()}


def _python_kennzeichen(zeilen: list[str]) -> bool:
    """Mindestens ein kennzeichnendes Merkmal (TOML, Kommentare und Zuweisungen lesen sich auch als Python)."""
    return any(g >= 3 and m.search(z) for z in zeilen for m, g in MERKMALE["python"])


def _python_lesbar(code: str) -> bool:
    try:
        ast.parse(textwrap.dedent(code))
        return True
    except (SyntaxError, ValueError):
        return False


def aus_inhalt(code: str) -> Befund:
    """Merkmale gewichtet und gegeneinander abgewogen; JSON und Python, die sich lesen lassen, zählen mehr."""
    zeilen = [z for z in code.splitlines() if z.strip()]
    if not zeilen:
        return KEINER
    for muster, sprache in ANFANG:
        if muster.search(zeilen[0]) or (sprache == "php" and any(muster.search(z) for z in zeilen)):
            return Befund(sprache, ANFANG_SICHER, "inhalt")
    if zeilen[0].lstrip()[:1] in "[{" and _json_lesbar(code):
        return Befund("json", ANFANG_SICHER, "inhalt")
    punkte = _punkte(zeilen)
    if _python_kennzeichen(zeilen) and _python_lesbar(code):
        punkte["python"] += 1.5                       # Python liest sich (Shell, YAML und PHP fast nie)
    if punkte["typescript"] > 0:                      # TypeScript ist JavaScript mit Typen
        punkte["typescript"] += punkte["javascript"]
    (erste, p1), (_, p2) = sorted(punkte.items(), key=lambda kv: -kv[1])[:2]
    if p1 <= 0:
        return KEINER
    abstand = (p1 - p2) / p1
    staerke = min(1.0, p1 / INHALT_VOLL)              # wenig Merkmale: weniger sicher, auch ohne Gegenstimme
    return Befund(erste, round(min(INHALT_HOECHSTENS, abstand * staerke), 2), "inhalt")


def _json_lesbar(code: str) -> bool:
    try:
        json.loads(code)
        return True
    except ValueError:
        return all(_json_zeile(z) for z in code.splitlines() if z.strip())   # JSON Lines


def _json_zeile(zeile: str) -> bool:
    try:
        return isinstance(json.loads(zeile), (dict, list))
    except ValueError:
        return False


def bestimmen(code: str, titel: str = "", datei: str = "") -> Befund:
    """Ausgabe und Terminal nach dem Titel zuerst, dann Dateiname vor Titelwort vor Inhalt. Nennt das Buch eine Sprache zum
    Ausführen, der Inhalt zeigt aber kein einziges ihrer Merkmale (etwa die Ausgabe eines Programms unter dessen Namen),
    gilt der Befund als unsicher."""
    if titel and AUSGABE_TITEL.search(titel):
        return Befund("ausgabe", TITEL_SICHER, "titel")
    if titel and BEFEHL_TITEL.match(titel):
        return Befund("shell", TITEL_SICHER, "titel")
    sprache, quelle = (aus_datei(datei), "datei") if datei else (None, "")
    if sprache is None and titel:
        sprache, quelle = aus_woertern(titel), "titel"
    if sprache is None:
        return aus_inhalt(code)
    zeilen = [z for z in code.splitlines() if z.strip()]
    if (sprache in MERKMALE and len(zeilen) >= 2 and _punkte(zeilen)[sprache] <= 0
            and not (sprache == "python" and _python_lesbar(code))):
        return Befund(sprache, UNSICHER_TROTZ_TITEL, quelle)
    return Befund(sprache, DATEI_SICHER if quelle == "datei" else TITEL_SICHER, quelle)
