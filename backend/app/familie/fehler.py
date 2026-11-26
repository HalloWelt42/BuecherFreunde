"""Fehler der Familie mit ihrem Status; die Schnittstelle macht daraus eine deutsche Antwort (api/familie.py)."""

from __future__ import annotations


class Familienfehler(Exception):
    status = 400

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


class Fehlt(Familienfehler):
    status = 404


class NichtErlaubt(Familienfehler):
    status = 403


class Falsch(Familienfehler):
    """PIN oder Bild-PIN stimmt nicht."""

    status = 403


class Konflikt(Familienfehler):
    status = 409


class Unpassend(Familienfehler):
    """Die Angaben passen nicht zusammen, etwa ein Kind ohne Stufe."""

    status = 422


class ZuVieleVersuche(Familienfehler):
    status = 429

    def __init__(self, nochmal_in: int) -> None:
        super().__init__(f"Zu viele Versuche, bitte {nochmal_in} Sekunden warten")
        self.nochmal_in = nochmal_in
