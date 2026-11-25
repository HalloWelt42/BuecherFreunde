"""Das Autorenfeld eines Buchs in einzelne Namen zerlegen. Eine Stelle für Aufnahme, Übernahme und Abgleich."""

from __future__ import annotations

import re

_VORSILBEN = {"le", "la", "de", "del", "di", "du", "von", "van", "der", "den", "el", "al", "bin", "ibn", "mc", "mac", "st", "saint", "o'"}


def _ist_nachname(teil: str) -> bool:
    worte = teil.split()
    return len(worte) == 1 or (len(worte) == 2 and worte[0].lower() in _VORSILBEN)


def zerlegen(text: str) -> list[str]:
    """Trennt an Semikolon, "und" und "&"; ein Komma trennt Autoren oder dreht "Nachname, Vorname" um."""
    text = (text or "").strip()
    if not text:
        return []
    teile = re.split(r"\s*;\s*|\s+und\s+|\s+&\s+", text)
    if len(teile) > 1:
        return [n for t in teile for n in zerlegen(t)]
    stuecke = [s.strip() for s in text.split(",") if s.strip()]
    if len(stuecke) == 2 and _ist_nachname(stuecke[0]) and len(stuecke[1].split()) <= 2:
        return [f"{stuecke[1]} {stuecke[0]}"]
    if len(stuecke) > 2 and len(stuecke) % 2 == 0 and all(len(s.split()) == 1 for s in stuecke):
        return [f"{vor} {nach}" for nach, vor in zip(stuecke[::2], stuecke[1::2], strict=True)]
    return stuecke
