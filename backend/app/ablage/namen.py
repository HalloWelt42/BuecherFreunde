"""Namen der Dateien in der Kellerwolke: lesbar für Menschen, eindeutig über die Nummer des Buchs."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

VERBOTEN = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')


def sauber(text: str | None, hoechstens: int) -> str:
    t = re.sub(r"\s+", " ", VERBOTEN.sub(" ", unicodedata.normalize("NFC", text or ""))).strip(" .")
    while len(t.encode()) > hoechstens:
        t = t[:-1].rstrip(" .")
    return t


def fach(titel: str) -> str:
    a = unicodedata.normalize("NFD", titel or "?")[0].upper()
    return a if "A" <= a <= "Z" else "0-9" if a.isdigit() else "Andere"


def ablageort(buch: int, titel: str, autor: str, dateiname: str, endung: str) -> tuple[str, str]:
    """Fach und Dateiname eines Buchs unterhalb von "Bücher"."""
    t = sauber(titel, 110) or sauber(Path(dateiname or "").stem, 110) or "Ohne Titel"
    a = sauber(autor, 60)
    return fach(t), f"{t}{' - ' + a if a else ''} [{buch}].{endung.lower().lstrip('.')}"
