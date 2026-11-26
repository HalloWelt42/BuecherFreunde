"""Die Sprache eines Bands (BF-75): jede Sprache hat ihre eigene Zählung. Was die Bücher nennen, gilt als Kürzel ("ger",
"Deutsch" und "de-DE" sind "de"). Ein Buch ohne Angabe zählt zur Hauptsprache seiner Sammlung, der Sprache, die ihre Bücher am
häufigsten nennen (bei Gleichstand die zuerst genannte); leer bleibt sie nur, wenn kein Buch eine nennt."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from backend.app.quellen.sprache import kuerzel, name

OHNE = "Sprache unbekannt"


def hauptsprache(angaben: Iterable[str | None]) -> str:
    zahlen = Counter(k for a in angaben if (k := kuerzel(a)))
    return zahlen.most_common(1)[0][0] if zahlen else ""


def sprache_von(angabe: str | None, haupt: str) -> str:
    return kuerzel(angabe) or haupt


def sprachname(k: str) -> str:
    """Zum Anzeigen: "de" -> "Deutsch"; ein unbekanntes Kürzel bleibt, wie es ist."""
    if not k:
        return OHNE
    n = name(k)
    return n.capitalize() if n != k else k


def folge(sprachen: Iterable[str], haupt: str) -> list[str]:
    """Die Reihen im Regal: die Hauptsprache zuerst, dann nach Namen."""
    return sorted(set(sprachen), key=lambda s: (s != haupt, sprachname(s).casefold()))
