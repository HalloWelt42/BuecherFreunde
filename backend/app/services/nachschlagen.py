"""Nachschlagen beim Lesen: Treffer, ein Artikel zum Lesen im kleinen Fenster und der Verweis an die Stelle im Lexikon. Welches
Lexikon gilt, steht nur hier: Nachschlag aus den Hausdiensten, wenn eingetragen (`NACHSCHLAG_URL`), sonst das öffentliche Lexikon
im Netz, solange es eingeschaltet ist (`WIKIPEDIA_ENABLED`); ohne beide fehlt die Fähigkeit."""

from __future__ import annotations

from backend.app.core.config import settings
from backend.app.services.hausdienst import DienstFehler
from backend.app.services.lexikon import Lexikon, Nachschlagartikel, Nachschlagtreffer
from backend.app.services.lexikon_nachschlag import Nachschlag
from backend.app.services.lexikon_netz import Netzlexikon

__all__ = ["Nachschlagartikel", "Nachschlagtreffer", "artikel", "bild", "lexikon", "schliessen", "suche", "vorwaermen"]

_nachschlag, _netz = Nachschlag(), Netzlexikon()


def lexikon() -> Lexikon | None:
    if settings.nachschlag_url:
        return _nachschlag
    if settings.wikipedia_enabled:
        return _netz
    return None


def _gewaehlt() -> Lexikon:
    gewaehlt = lexikon()
    if gewaehlt is None:
        raise DienstFehler("Nachschlagen ist nicht angeschlossen", 503)
    return gewaehlt


async def vorwaermen() -> None:
    if gewaehlt := lexikon():
        await gewaehlt.vorwaermen()


async def schliessen() -> None:
    await _nachschlag.schliessen()
    await _netz.schliessen()


async def suche(frage: str, anzahl: int = 12, sitzung: str = "", nur_titel: bool = False) -> list[Nachschlagtreffer]:
    return await _gewaehlt().suche(frage, anzahl, sitzung, nur_titel)


async def artikel(buch: str, pfad: str, frage: str = "", anker: str = "", sitzung: str = "") -> Nachschlagartikel:
    return await _gewaehlt().artikel(buch, pfad, frage, anker, sitzung)


async def bild(buch: str, pfad: str) -> tuple[bytes, str]:
    return await _gewaehlt().bild(buch, pfad)
