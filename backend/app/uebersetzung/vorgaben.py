"""Die Wortlisten aus vorgaben.json (BF-71), an einem Ort für die Regeln der Begriffsliste und die festen Prüfungen.

- `alltagswoerter`: gewöhnliche englische Wörter. Ein Vorschlag der KI "bleibt englisch" nur aus ihnen wird verworfen, die
  Regel für Namen nimmt sie nie, und ein Block, der mit einem von ihnen unverändert zurückkam, ist unübersetzt.
- `englisch_im_fach`: eingeführte Fachwörter und Wortgruppen, die im deutschen Fachtext gebräuchlich englisch bleiben
  (Paging, Cache, Thread, Game Loop). Ein Vorschlag der KI, der ihnen eine deutsche Form gibt, wird verworfen; ein solcher
  Eintrag einer bestehenden Liste ist fragwürdig (begriffe.py); englisch dastehend sind sie kein stehengebliebenes Englisch
  (pruefen.py, pruefer.py).
- `auch_deutsch`: Wörter, die es im Deutschen genauso gibt (in, so, null); sie zählen nie als stehengebliebenes Englisch.
- `zahlwoerter`: Zahlwörter eins bis zwölf, die für eine Zahl stehen, wenn die andere Seite sie als Ziffer schreibt
  (4-level: vierstufig; zahlen.py).

Die allgemeine Begriffsliste derselben Datei spielt services/begriffsliste.py in die Datenbank ein."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

DATEI = Path(__file__).resolve().parent / "vorgaben.json"


class Zahlwoerter(BaseModel):
    """Zahlwörter je Sprache mit ihrer Zahl, alles klein."""
    deutsch: dict[str, int]                          # auch vorn in einem Wort: vierstufig, zweifach, dreidimensional
    deutsch_allein: dict[str, int]                   # nur als ganzes Wort: ein, eine (sonst zählten einfach, Einheit)
    englisch: dict[str, int]                         # nur als ganzes Wort
    keine: tuple[str, ...]                           # deutsche Wörter, die so beginnen und keine Zahl sind: Zweig, Achtung
    groesser: tuple[str, ...]                        # was hinter einem Zahlwort eine größere Zahl macht: vierzehn, vierzig


@lru_cache(maxsize=1)
def daten() -> dict:
    return json.loads(DATEI.read_text(encoding="utf-8"))


def _woerter(schluessel: str) -> frozenset[str]:
    return frozenset(w.lower() for w in daten().get(schluessel, []))


def alltagswoerter() -> frozenset[str]:
    return _woerter("alltagswoerter")


def englisch_im_fach() -> frozenset[str]:
    return _woerter("englisch_im_fach")


def auch_deutsch() -> frozenset[str]:
    return _woerter("auch_deutsch")


@lru_cache(maxsize=1)
def zahlwoerter() -> Zahlwoerter:
    return Zahlwoerter(**daten()["zahlwoerter"])


def grundform(wort: str, liste: frozenset[str]) -> str | None:
    """Wie ein englisches Wort in der Liste steht (klein), auch aus der Mehrzahl auf -s oder -es; None, wenn es fehlt."""
    w = wort.lower()
    return next((g for g in (w, w[:-1] if w.endswith("s") else "", w[:-2] if w.endswith("es") else "") if g and g in liste), None)


def in_liste(wort: str, liste: frozenset[str]) -> bool:
    return grundform(wort, liste) is not None
