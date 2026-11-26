"""Gehört eine Datei nach ihrem Namen zu einem Buch (BF-80, BF-81)? Ja, wenn ihr Name mit dem Stamm des Buchs beginnt und
danach ein Trenner kommt: "Sensoren - Beispielcode.zip" zu "Sensoren.pdf", "Titel [12].material.x" zu "Titel [12].pdf",
aber nicht "Kriegsbericht.pdf" zu "Krieg.pdf". Groß und klein zählen nicht. Für ZIP (annahme/entpacken.py) und den Abgleich
in der Kellerwolke (material/erkennen.py)."""

from __future__ import annotations

import posixpath
import re
import unicodedata

TRENNER = re.compile(r"^\s*(?:[-_\u2013\u2014]+|[.(\[])")
RAND = " -_.()[]\u2013\u2014"
NUMMER = re.compile(r"\s*\[\d+\]$")              # die Nummer des Buchs, die die Ablage an den Namen hängt


def _vergleich(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").casefold()


def stamm(name: str) -> str:
    return posixpath.splitext(name)[0]


def stamm_ohne_nummer(name: str) -> str:
    return NUMMER.sub("", stamm(name))


def rest_hinter(name: str, buchstamm: str) -> str | None:
    """Was hinter dem Stamm des Buchs steht, oder None, wenn die Datei nach dem Namen nicht dazugehört."""
    s, b = _vergleich(stamm(name)), _vergleich(buchstamm)
    if not b or not s.startswith(b) or len(s) == len(b):
        return None
    rest = stamm(name)[len(buchstamm):]
    return rest if TRENNER.match(rest) else None


def gehoert_zu(name: str, buchstamm: str) -> bool:
    return rest_hinter(name, buchstamm) is not None


def kurzname(name: str, buchstamm: str) -> str:
    """Der Name als Material, ohne den Teil des Buchs: "Sensoren - Beispielcode.zip" wird "Beispielcode.zip". Bleibt nichts
    übrig, der ganze Name."""
    rest = rest_hinter(name, buchstamm)
    kurz = (rest or "").strip(RAND)
    return f"{kurz}{posixpath.splitext(name)[1]}" if kurz else name


def als_material(name: str, original: str) -> str:
    """Der Name einer Datei als Material zum Original `original` (sein Name in der Ablage, mit oder ohne Nummer davor)."""
    for s in (stamm(original), stamm_ohne_nummer(original)):
        if gehoert_zu(name, s):
            return kurzname(name, s)
    return name
