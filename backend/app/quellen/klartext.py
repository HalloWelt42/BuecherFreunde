"""Warum eine Quelle gerade nichts liefert, als Satz für eine Meldung in der Oberfläche: mit dem Namen, den der Nutzer kennt, und
ohne Fehlernummer (BF-98). Die Gründe selbst (quellen/fehler.py, versand.py) bleiben, wie sie sind, für Protokoll und den Stand
der Quellen in den Einstellungen."""

from __future__ import annotations

import re
import time

from backend.app.quellen.fehler import Abgeschaltet, AnfrageFalsch, Ausgefallen, Pausiert, QuelleFehler, Tagesgrenze
from backend.app.quellen.versand import NICHT_ERREICHBAR
from backend.app.quellen.zustand import uhrzeit


def klartext(f: QuelleFehler, wer: str, jetzt: float | None = None) -> str:
    """Ein Satz ohne Punkt am Ende, etwa "Gutendex antwortet gerade nicht, der Dienst ist überlastet"."""
    if isinstance(f, Abgeschaltet):
        return f"{wer} ist in der Einrichtung abgeschaltet"
    if isinstance(f, Tagesgrenze):
        return f"{wer} wird heute im Hintergrund nicht mehr gefragt"
    if isinstance(f, Pausiert):
        bis = f" bis {uhrzeit(f.bis, jetzt or time.time())}" if f.bis else ""
        return f"{wer} ist gerade gestört und wird{bis} nicht gefragt"
    if isinstance(f, Ausgefallen):
        if f.grund.endswith(NICHT_ERREICHBAR):
            return f"{wer} ist gerade nicht erreichbar"
        return f"{wer} antwortet gerade nicht, der Dienst ist überlastet"
    if isinstance(f, AnfrageFalsch):
        return f"{wer}: {f.grund}" if f.grund and not re.search(r"\d", f.grund) else f"{wer} versteht die Anfrage nicht"
    return f"{wer} ist gerade gestört"
