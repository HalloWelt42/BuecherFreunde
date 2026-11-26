"""Schritt Speicherorte (BF-82): die fünf Orte aus `ablage/orte.py` mit Platz, Lampe und Markerdatei. Weiter geht es nur, wenn
jeder dauerhafte Ort da und schreibbar ist und seine Markerdatei trägt (gesetzt beim ersten Start einer neuen Installation); fehlt
eine Platte, steht das rot da. Die Pfade selbst sind Einhängepunkte der Einrichtung (.env, Compose) und ändern sich nur mit einem
Neustart; der Schritt misst und bestätigt sie."""

from __future__ import annotations

import asyncio
import os

from backend.app.ablage import orte
from backend.app.einrichtung.modelle import Orte, Ortstand


def _mangel(ort: orte.Ort) -> str:
    """Warum ein Ort nicht bereit ist; leer, wenn er es ist."""
    if not ort.pfad.is_dir():
        return "Der Ordner fehlt; ist die Platte eingehängt?"
    if not os.access(ort.pfad, os.W_OK):
        return "Die App darf hier nicht schreiben"
    if ort.dauerhaft and not (ort.pfad / orte.MARKER).exists():
        return "Ohne Markerdatei; ist die Platte eingehängt?"
    return ""


def _einer(ort: orte.Ort, roh: dict) -> Ortstand:
    mangel = _mangel(ort)
    return Ortstand(kennung=ort.kennung, name=ort.name, pfad=roh["pfad"], belegt=roh.get("belegt", 0), frei=roh.get("frei", 0),
                    stand="schlecht" if mangel else roh["stand"], dauerhaft=ort.dauerhaft, marker=(ort.pfad / orte.MARKER).exists(),
                    text=mangel or roh.get("text", ""))


def _weiter(schlecht: list[str]) -> tuple[bool, str]:
    return not schlecht, f"Nicht bereit: {', '.join(schlecht)}" if schlecht else ""


def _messen() -> Orte:
    je = {r["kennung"]: r for r in orte.stand()}
    liste = [_einer(o, je[o.kennung]) for o in orte.alle()]
    weiter, grund = _weiter([o.name for o in liste if o.stand == "schlecht"])
    return Orte(orte=liste, weiter=weiter, grund=grund)


async def stand() -> Orte:
    """Misst jedes Mal neu ("Neu suchen"), mit Platz und Belegung."""
    return await asyncio.to_thread(_messen)


async def bereit() -> tuple[bool, str]:
    """Nur, ob Weiter geht, ohne die Belegung zu zählen (für den Zustand der Schritte)."""
    return _weiter([o.name for o in orte.alle() if await asyncio.to_thread(_mangel, o)])
