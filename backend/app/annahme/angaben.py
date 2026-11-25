"""Bei der Aufnahme fehlende Angaben aus den Quellen ergänzen. Was in der Datei steht, bleibt; scheitert es oder dauert es zu
lange, geht die Aufnahme ohne weiter."""

from __future__ import annotations

import asyncio
import logging

from backend.app.annahme.auswertung import Ergebnis
from backend.app.quellen import auskunft
from backend.app.quellen.abgleich import norm
from backend.app.quellen.modelle import Angaben, Buchfrage
from backend.app.quellen.sprache import kuerzel
from backend.app.quellen.vorrang import hintergrund
from backend.app.services.autorennamen import zerlegen
from backend.app.services.data_cleaner import bereinige_autor, bereinige_text, bereinige_titel

logger = logging.getLogger("buecherfreunde.angaben")
ZEIT_S = 45.0


def _ist_dateiname(titel: str, stamm: str) -> bool:
    return not titel or norm(titel) == norm(stamm.replace("-", " "))


def _fehlt(e: Ergebnis, stamm: str) -> set[str]:
    felder = {"autoren": e.author, "verlag": e.publisher, "jahr": e.year, "sprache": e.language, "beschreibung": e.description, "isbn": e.isbn, "titel": "" if _ist_dateiname(e.title, stamm) else e.title}
    return {f for f, w in felder.items() if not w}


def _uebernimm(e: Ergebnis, a: Angaben, fehlt: set[str]) -> None:
    if "titel" in fehlt and a.titel:
        e.title = bereinige_titel(a.titel)
    if "autoren" in fehlt and a.autoren:
        e.author = bereinige_autor(", ".join(a.autoren))
    e.isbn = e.isbn or a.isbn
    e.publisher = e.publisher or bereinige_text(a.verlag, 200)
    e.year = e.year or a.jahr
    e.language = e.language or a.sprache
    e.description = e.description or bereinige_text(a.beschreibung)


async def ergaenzen(e: Ergebnis, stamm: str) -> None:
    """Füllt leere Felder eines ausgewerteten Buchs. `stamm` ist der Dateiname ohne Endung."""
    fehlt = _fehlt(e, stamm)
    frage = Buchfrage(isbn=e.isbn or "", titel=e.title, autoren=zerlegen(e.author or ""), jahr=e.year, sprache=kuerzel(e.language), seiten=e.page_count)
    if not fehlt:
        return
    try:
        with hintergrund():
            antwort = await asyncio.wait_for(auskunft.ergaenze(frage, fehlt), ZEIT_S)
    except Exception as f:                                   # noqa: BLE001 - ohne Ergänzung bleibt, was in der Datei steht
        logger.info("Angaben zu %s nicht ergänzt: %s", stamm, f or type(f).__name__)
        return
    if antwort.angaben:
        _uebernimm(e, antwort.angaben, fehlt)
