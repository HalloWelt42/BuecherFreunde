"""Ein Netz aus Mitschnitten für die Tests der Quellen: beantwortet Anfragen, zählt sie mit und kennt keinen Ausgang."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from backend.app.quellen.abruf import Abruf
from backend.app.quellen.fehler import Ausgefallen
from backend.app.quellen.regeln import Regel
from backend.app.quellen.takt import Takt
from backend.app.quellen.versand import Anfrage, Rohantwort

DATEN = Path(__file__).parent / "daten" / "quellen"
Antworter = Callable[[Anfrage], Rohantwort]


def mitschnitt(name: str) -> bytes:
    return (DATEN / name).read_bytes()


def antwort(inhalt: bytes | str | dict | list = b"", status: int = 200, **kopf: str) -> Rohantwort:
    roh = inhalt if isinstance(inhalt, bytes) else inhalt.encode() if isinstance(inhalt, str) else json.dumps(inhalt).encode()
    return Rohantwort(status, {k.replace("_", "-"): w for k, w in kopf.items()}, roh)


def feld(a: Anfrage, name: str) -> str:
    return dict(a.felder).get(name, "")


class Netz:
    """Antworten je Rechner; mehrere Antworten in einer Liste kommen nacheinander, die letzte bleibt."""

    def __init__(self) -> None:
        self.anfragen: list[Anfrage] = []
        self._antworten: dict[str, list[Any]] = {}

    def setze(self, rechner: str, *antworten: Rohantwort | Exception | Antworter) -> None:
        self._antworten[rechner] = list(antworten)

    def zahl(self, rechner: str = "") -> int:
        return sum(1 for a in self.anfragen if not rechner or urlsplit(a.adresse).hostname == rechner)

    async def __call__(self, a: Anfrage) -> Rohantwort:
        self.anfragen.append(a)
        liste = self._antworten.get(urlsplit(a.adresse).hostname or "")
        if not liste:
            raise AssertionError(f"Test fragt ungeplant: {a.adresse} {a.felder}")
        naechste = liste.pop(0) if len(liste) > 1 else liste[0]
        if isinstance(naechste, Exception):
            raise naechste
        return naechste(a) if callable(naechste) else naechste


class Uhr:
    def __init__(self, zeit: float = 1_800_000_000.0) -> None:
        self.zeit = zeit

    def __call__(self) -> float:
        return self.zeit


def ohne_takt(_regel: Regel) -> Takt:
    return Takt(lambda: 0.0, lambda: 100_000)


def abruf_mit(netz: Netz, uhr: Uhr | None = None) -> Abruf:
    return Abruf(netz, uhr, ohne_takt) if uhr else Abruf(netz, takt=ohne_takt)


AUSFALL = Ausgefallen("antwortet nicht rechtzeitig")
