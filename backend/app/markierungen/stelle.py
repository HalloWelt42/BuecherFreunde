"""Die Stelle einer Markierung als Rechteck auf einer PDF-Seite (BF-123): `page:N:bereich:x0,y0,x1,y1`, die Ecken in Anteilen der
Seite mit vier Stellen. Der Anfang `page:N` ist derselbe wie bei Markierungen im Text des PDF, so nennen Liste, Randmarken und
Sprünge die Seite wie immer; das Rechteck findet die Stelle wieder, ohne Wortlaut und unabhängig vom Zoom. Die Oberfläche liest
und schreibt dasselbe Format (frontend/src/lib/leser/pdf/bereich.ts)."""

from __future__ import annotations

import re

from pydantic import ValidationError

from backend.app.texterkennung.ausschnitt import Bereich

MUSTER = re.compile(r"^page:(\d+):bereich:(\d(?:\.\d+)?),(\d(?:\.\d+)?),(\d(?:\.\d+)?),(\d(?:\.\d+)?)$")


def bereich_aus(stelle: str) -> tuple[int, Bereich] | None:
    """Seite und Rechteck einer Stelle; None, wenn sie kein (gültiges) Rechteck nennt."""
    m = MUSTER.match(stelle)
    if not m or int(m.group(1)) < 1:
        return None
    try:
        return int(m.group(1)), Bereich(x0=float(m.group(2)), y0=float(m.group(3)), x1=float(m.group(4)), y1=float(m.group(5)))
    except ValidationError:
        return None


def stelle_von(seite: int, b: Bereich) -> str:
    return f"page:{seite}:bereich:{b.x0:.4f},{b.y0:.4f},{b.x1:.4f},{b.y1:.4f}"
