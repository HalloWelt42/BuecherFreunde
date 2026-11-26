"""Die Wortlisten aus vorgaben.json (BF-71), an einem Ort für die Regeln der Begriffsliste und die festen Prüfungen.

- `alltagswoerter`: gewöhnliche englische Wörter. Ein Vorschlag der KI "bleibt englisch" nur aus ihnen wird verworfen, die
  Regel für Namen nimmt sie nie, und ein Block, der mit einem von ihnen unverändert zurückkam, ist unübersetzt.
- `englisch_im_fach`: Fachwörter, die im deutschen Fachtext gebräuchlich englisch bleiben (Paging, Cache, Thread). Ein
  Vorschlag der KI, der ihnen eine deutsche Form gibt, wird verworfen; ein solcher Eintrag einer bestehenden Liste ist
  fragwürdig (begriffe.py).

Die allgemeine Begriffsliste derselben Datei spielt services/begriffsliste.py in die Datenbank ein."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATEI = Path(__file__).resolve().parent / "vorgaben.json"


@lru_cache(maxsize=1)
def daten() -> dict:
    return json.loads(DATEI.read_text(encoding="utf-8"))


def _woerter(schluessel: str) -> frozenset[str]:
    return frozenset(w.lower() for w in daten().get(schluessel, []))


def alltagswoerter() -> frozenset[str]:
    return _woerter("alltagswoerter")


def englisch_im_fach() -> frozenset[str]:
    return _woerter("englisch_im_fach")


def grundform(wort: str, liste: frozenset[str]) -> str | None:
    """Wie ein englisches Wort in der Liste steht (klein), auch aus der Mehrzahl auf -s oder -es; None, wenn es fehlt."""
    w = wort.lower()
    return next((g for g in (w, w[:-1] if w.endswith("s") else "", w[:-2] if w.endswith("es") else "") if g and g in liste), None)


def in_liste(wort: str, liste: frozenset[str]) -> bool:
    return grundform(wort, liste) is not None
