"""Die Stimmen der Vertonung, bei jedem Aufruf neu (`GET /api/v1/stimmen` je Bereich, mit dem App-Zugang der Kellerwolke): private
Stimmen, die sie BücherFreunde freigibt, fremde Klonstimmen und ihr Katalog. Nie aus einer festen Liste. Gibt sie keine privaten
frei (401 oder 403 nur für diesen Bereich), steht das mit Grund und dem Weg zur Freigabe am Bereich; sonst fehlten sie ohne Grund.
Die Bereiche und ihre Folge stehen im Baustein des Appkerns (`appkern.vorlesen.BEREICHE`)."""

from __future__ import annotations

import asyncio
import logging

from appkern.verbund import ABFRAGE, VerbundFehler
from appkern.vorlesen import BEREICHE
from pydantic import BaseModel, ValidationError

from backend.app.vorlesen import zugang
from backend.app.vorlesen.modelle import Bereich, Bereichsstand, Stimme, Stimmenliste

logger = logging.getLogger("buecherfreunde.vorlesen")
STIMMEN = "/api/v1/stimmen"
WEG_ZUR_FREIGABE = "Freigabe in der Vertonung unter Private Stimmen für"


class _Angaben(BaseModel):
    sprache: str | None = None


class _Vertonungsstimme(BaseModel):
    """Eine Stimme, wie die Vertonung sie liefert; was BücherFreunde nicht braucht, bleibt dort."""

    id: str
    name: str
    angaben: _Angaben | None = None


async def _bereich(adresse: str, bereich: Bereich) -> list[Stimme]:
    antwort = await zugang.verbund.anfrage("GET", adresse, STIMMEN, timeout=ABFRAGE, params={"bereich": bereich})
    try:
        roh = [_Vertonungsstimme.model_validate(s) for s in antwort.json()]
    except (ValueError, TypeError, ValidationError) as f:
        raise VerbundFehler(f"unerwartete Antwort auf {STIMMEN} ({type(f).__name__})", antwort.status_code) from f
    return [Stimme(id=s.id, name=s.name, bereich=bereich, sprache=s.angaben.sprache if s.angaben else None) for s in roh]


async def liste(adresse: str | None = None) -> Stimmenliste:
    """Alle Stimmen, die die Vertonung BücherFreunde gerade anbietet; mit `adresse` die einer anderen (Prüfung vor dem
    Eintragen). Ohne Vertonung leer und ohne Hinweis: dann gilt nur die Stimme des Geräts."""
    ziel = (adresse or zugang.adresse()).rstrip("/")
    if not ziel or (adresse is None and not zugang.bereit()):
        return Stimmenliste(da=False, stimmen=[], bereiche=[])
    antworten = await asyncio.gather(*(_bereich(ziel, b) for b, _ in BEREICHE), return_exceptions=True)
    stimmen: list[Stimme] = []
    bereiche: list[Bereichsstand] = []
    hinweis = ""
    for (bereich, _), a in zip(BEREICHE, antworten, strict=True):
        if isinstance(a, VerbundFehler) and bereich == "privat" and a.status in (401, 403):
            bereiche.append(Bereichsstand(bereich=bereich, frei=False, hinweis=f"{a.meldung.rstrip('.')}. {WEG_ZUR_FREIGABE}"))
        elif isinstance(a, VerbundFehler):
            logger.info("Stimmen der Vertonung (%s) nicht geholt: %s", bereich, a.meldung)
            hinweis = hinweis or zugang.fehler(a).meldung
        elif isinstance(a, BaseException):
            raise a
        else:
            stimmen += a
            bereiche.append(Bereichsstand(bereich=bereich, frei=True))
    da = bool(stimmen) or (bool(bereiche) and not hinweis)          # geantwortet, auch wenn ein Bereich leer ist
    return Stimmenliste(da=da, stimmen=stimmen, bereiche=bereiche, hinweis=hinweis)
