"""Der Entwurf eines Katalogs (BF-69): ein Katalog, der noch nicht gilt, als JSON in `app_settings` (`katalog_entwurf`),
bis er angenommen (katalog/kategorien.py) oder verworfen wird.

Wege zum Entwurf: der Standard, eine geladene Datei, leer, oder der Standard nach dem Bestand (`aus_bestand`, im Lauf von
katalog/bestandslauf.py): Kategorien ohne Treffer der Regeln sind verborgen (Herkunft bleibt standard), große mit Teilen
werden durch die Teile ersetzt (Herkunft geteilt), Bereiche ohne sichtbare Kategorie verborgen, die Zahlen sind die
Treffer der Regeln.

Gespeichert erbt eine Kategorie ohne eigene Farbe die ihres Bereichs (leer); gezeigt wird die Farbe, die gilt."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from pydantic import ValidationError

from backend.app.core import einstellungen
from backend.app.core.database import db
from backend.app.katalog import datei
from backend.app.katalog.modelle import Katalog, Katalogbereich, Katalogkategorie, Teil, eigene_farbe

logger = logging.getLogger("buecherfreunde.katalog")
SCHLUESSEL = "katalog_entwurf"


async def lesen() -> Katalog | None:
    roh = await einstellungen.lesen(SCHLUESSEL)
    if not roh:
        return None
    try:
        return Katalog.model_validate_json(roh)
    except ValidationError:
        logger.warning("Der gemerkte Entwurf des Katalogs ist nicht lesbar und gilt als keiner")
        return None


async def speichern(k: Katalog) -> Katalog:
    k = gespeichert(k)
    await einstellungen.schreiben(SCHLUESSEL, k.model_dump_json())
    return k


async def verwerfen() -> None:
    await db.execute("DELETE FROM app_settings WHERE key = ?", (SCHLUESSEL,))


def gespeichert(k: Katalog) -> Katalog:
    """Wie der Entwurf gespeichert wird: Kategorien mit der Farbe ihres Bereichs erben sie (leer)."""
    k = k.model_copy(deep=True)
    for b in k.bereiche:
        for kat in b.kategorien:
            kat.farbe = eigene_farbe(kat.farbe, b.farbe)
    return k


def gezeigt(k: Katalog) -> Katalog:
    """Wie der Entwurf gezeigt wird: jede Kategorie mit der Farbe, die für sie gilt."""
    k = k.model_copy(deep=True)
    for b in k.bereiche:
        for kat in b.kategorien:
            kat.farbe = kat.farbe or b.farbe
    return k


def aus_standard() -> Katalog:
    return datei.herkunft_ergaenzen(datei.standard())


def leer() -> Katalog:
    return Katalog()


def _aus_teil(t: Teil, treffer: set[int]) -> Katalogkategorie:
    return Katalogkategorie(**t.model_dump(), herkunft="geteilt", anzahl=len(treffer), verborgen=not treffer)


def _kategorien_nach_bestand(b: Katalogbereich, treffer: dict[str, set[int]], teilen_ab: int) -> list[Katalogkategorie]:
    aus = []
    for k in b.kategorien:
        getroffen = treffer.get(k.schluessel, set())
        if k.teile and len(getroffen) > teilen_ab:
            aus += [_aus_teil(t, treffer.get(t.schluessel, set())) for t in k.teile]
        else:
            aus.append(k.model_copy(update={"anzahl": len(getroffen), "verborgen": not getroffen, "herkunft": "standard"}))
    return aus


def aus_bestand(standard: Katalog, treffer: dict[str, set[int]], teilen_ab: int,
                neue: Iterable[tuple[str, Katalogkategorie]] = ()) -> Katalog:
    """Der Standard nach den Treffern der Regeln (je Schlüssel die getroffenen Bücher); `neue` sind Kategorien, die die KI
    aus dem Bestand vorschlägt, je mit dem Schlüssel ihres Bereichs."""
    neue = [(s, k.model_copy(update={"anzahl": len(treffer.get(k.schluessel, ())), "verborgen": not treffer.get(k.schluessel)}))
            for s, k in neue]
    bereiche = []
    for b in standard.bereiche:
        kategorien = _kategorien_nach_bestand(b, treffer, teilen_ab) + [k for s, k in neue if s == b.schluessel]
        buecher = set().union(*(treffer.get(k.schluessel, set()) for k in kategorien))
        bereiche.append(b.model_copy(update={"kategorien": kategorien, "anzahl": len(buecher), "herkunft": "standard",
                                             "verborgen": all(k.verborgen for k in kategorien)}))
    return Katalog(bereiche=bereiche)
