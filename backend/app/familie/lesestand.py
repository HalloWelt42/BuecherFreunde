"""Der Lesestand eines Buchs (BF-78): wie weit gelesen ist und wann ein Buch fertig gelesen ist, an einer Stelle für den Filter
Gelesen, den Rückblick des Kindes und den Einblick der Eltern.

Fertig ist ein Buch, sobald der Lesestand `lesestand.fertig_ab` aus stufen.json erreicht (0,99: das Ende oder fast), oder wenn
man es als gelesen markiert (`PATCH /api/books/{id}/gelesen`); es bleibt fertig, auch wenn man darin zurückblättert.
Gelesen werden alle Formen, die die Oberfläche speichert (frontend/src/lib/lesestand.ts): pdf:, epub:, txt: mit JSON,
txt:<Prozent>, percent:, page:. Ein Stand nur mit Stelle (CFI) sagt nichts über den Anteil."""

from __future__ import annotations

import json
import re

from backend.app.familie.stufen import stufenbuch


def werte(position: str | None) -> dict:
    roh = position or ""
    rest = roh[roh.find(":") + 1:]
    if re.match(r"^(pdf|epub|txt):\{", roh):
        try:
            gelesen = json.loads(rest)
            return gelesen if isinstance(gelesen, dict) else {}
        except ValueError:
            return {}
    if roh.startswith("txt:"):
        return {"scrollPct": _zahl(rest)}
    if roh.startswith("percent:"):
        return {"percent": _zahl(rest)}
    m = re.search(r"page:(\d+)", roh)
    return {"page": int(m.group(1))} if m else {}


def _zahl(text: str) -> float:
    try:
        return float(text)
    except ValueError:
        return 0.0


def anteil(position: str | None, seiten: int) -> float:
    """0 bis 1, wie die Oberfläche ihn rechnet: Seite durch Seiten, sonst Prozent, sonst Anteil des Rollens."""
    w = werte(position)
    roh = 0.0
    if w.get("page"):
        roh = w["page"] / seiten if seiten else 0.0
    elif w.get("percent"):
        roh = w["percent"] / 100
    elif w.get("scrollPct"):
        roh = w["scrollPct"] / 100
    return min(1.0, max(0.0, float(roh)))


def fertig(position: str | None, seiten: int) -> bool:
    return anteil(position, seiten) >= stufenbuch().lesestand.fertig_ab
