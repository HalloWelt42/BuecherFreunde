"""Der Stand der Quellen für die Einstellungen, aus dem Gemerkten. Eine echte Probe gibt es nur auf Wunsch, je Quelle höchstens
einmal in der Minute."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel

from backend.app.quellen import gnd, gutenberg
from backend.app.quellen.abruf import abruf
from backend.app.quellen.auskunft import QUELLEN
from backend.app.quellen.fehler import QuelleFehler
from backend.app.quellen.regeln import GND, GUTENBERG, REGELN, Regel
from backend.app.quellen.vorrat import Bestand
from backend.app.quellen.zustand import Quellenzustand, uhrzeit

PROBE_ABSTAND_S = 60.0
PROBEN: dict[str, Callable[[], Awaitable[None]]] = {**{k: q.probe for k, q in QUELLEN.items()}, GND.kennung: gnd.probe, GUTENBERG.kennung: gutenberg.probe}


class Quellenstand(BaseModel):
    kennung: str
    name: str
    anbieter: str
    art: Literal["buch", "autor", "bestand"]
    adresse: str
    aktiv: bool
    bereit: bool                        # eingeschaltet und, falls nötig, mit Schlüssel
    erreichbar: bool
    stand: Literal["gut", "warn", "schlecht", "aus"]
    wort: str
    grund: str = ""
    anfragen_heute: int = 0
    hintergrund_heute: int = 0
    tagesgrenze: int = 0
    gemerkt: int = 0                    # Antworten im Vorrat
    gemerkt_bytes: int = 0


def _lage(regel: Regel, z: Quellenzustand, jetzt: float) -> tuple[Literal["gut", "warn", "schlecht", "aus"], str, str]:
    """Farbe, Wort und Grund."""
    if not regel.aktiv:
        return "aus", "Aus", ""
    if regel.hindernis:
        return "aus", "Schlüssel fehlt", regel.hindernis
    if z.pause_bis and z.pause_bis > jetzt:
        return "warn", f"Pause bis {uhrzeit(z.pause_bis, jetzt)}", z.pause_grund
    if z.erfolg_am and z.erfolg_am >= (z.fehler_am or 0):
        return "gut", f"Zuletzt gut {uhrzeit(z.erfolg_am, jetzt)}", ""
    if z.fehler_am:
        return "schlecht", f"Zuletzt gescheitert {uhrzeit(z.fehler_am, jetzt)}", z.fehler
    return "aus", "Noch nicht gefragt", ""


async def einer(kennung: str, bestand: dict[str, Bestand] | None = None) -> Quellenstand:
    regel = REGELN[kennung]
    z = await abruf().zustaende.von(kennung)
    farbe, wort, grund = _lage(regel, z, time.time())
    gemerkt = (bestand if bestand is not None else await abruf().vorrat.zahlen()).get(kennung, Bestand())
    return Quellenstand(kennung=kennung, name=regel.name, anbieter=regel.anbieter, art=regel.art, adresse=regel.adresse, aktiv=regel.aktiv, bereit=not regel.hindernis, erreichbar=farbe == "gut", stand=farbe, wort=wort, grund=grund,
                        anfragen_heute=z.anfragen, hintergrund_heute=z.hintergrund, tagesgrenze=regel.tagesgrenze, gemerkt=gemerkt.antworten, gemerkt_bytes=gemerkt.bytes)


async def alle() -> list[Quellenstand]:
    bestand = await abruf().vorrat.zahlen()
    return [await einer(k, bestand) for k in REGELN]


async def pruefe(kennung: str) -> Quellenstand:
    """Eine echte Probe, wenn die letzte eine Minute her ist; danach der neue Stand."""
    z = await abruf().zustaende.von(kennung)
    if not REGELN[kennung].hindernis and time.time() - (z.geprueft_am or 0) >= PROBE_ABSTAND_S:
        try:
            await PROBEN[kennung]()
        except QuelleFehler:
            pass                                            # steht im Stand
    return await einer(kennung)
