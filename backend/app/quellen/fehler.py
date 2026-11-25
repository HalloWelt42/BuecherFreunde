"""Warum eine Quelle gerade nichts liefert. `grund` ist ein Satz für die Oberfläche, ohne Punkt am Ende."""

from __future__ import annotations


class QuelleFehler(Exception):
    def __init__(self, grund: str, bis: float | None = None) -> None:
        super().__init__(grund)
        self.grund = grund
        self.bis = bis                  # Unix-Zeit, bis wann nicht gefragt wird


class Abgeschaltet(QuelleFehler):
    """In der Einrichtung aus, oder es fehlt ein Schlüssel."""


class Pausiert(QuelleFehler):
    """Die Quelle bat um Ruhe oder fiel mehrmals aus; bis `bis` wird sie nicht gefragt."""


class Tagesgrenze(QuelleFehler):
    """Hintergrundläufe haben für heute genug gefragt."""


class Ausgefallen(QuelleFehler):
    """Dieser eine Abruf ist gescheitert (Zeit, Netz, 5xx)."""


class Unlesbar(Ausgefallen):
    """Die Antwort kam, ist aber kaputt."""


class AnfrageFalsch(QuelleFehler):
    """Die Quelle versteht die Anfrage nicht (4xx); zählt nicht als Ausfall."""


class BitteWarten(Exception):
    """Aus einer Antwort gelesen: so viele Sekunden Ruhe, mit diesem Grund (wird zu `Pausiert`)."""

    def __init__(self, sekunden: float, grund: str) -> None:
        super().__init__(grund)
        self.sekunden = sekunden
        self.grund = grund


def ruhig(f: QuelleFehler) -> bool:
    """Weiterfragen hat heute keinen Sinn (Pause oder Tagesgrenze)."""
    return isinstance(f, Pausiert | Tagesgrenze)
