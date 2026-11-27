"""Vorab gesprochene Töne je Stimme, dauerhaft im Ort texte: die festen Ansagen (familie/ansagen.py) und die Stimmproben
(vorlesen/proben.py). Je Art ein Ort, darin je Stimme ein Ordner und je Ton eine Datei. Der Name der Datei trägt eine
Prüfsumme über alles, was den Ton ausmacht (Fassung, Text, Werte): ein geänderter Text gibt einen neuen Ton, ein Ton ändert
sich nie und darf lange im Speicher des Browsers bleiben."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path

from backend.app.vorlesen.modelle import name_im_katalog

#: so sehen Ordner und Dateien aus, die ein Weg nach außen annimmt (vor jedem Pfad geprüft)
ORDNERFORM = r"^[a-z0-9-]{1,60}$"
DATEIFORM = r"^[a-z0-9-]{1,120}-[0-9a-f]{16}\.wav$"
_ZEICHEN = re.compile(r"[^a-z0-9]+")


def _lesbar(text: str, laenge: int, sonst: str) -> str:
    return _ZEICHEN.sub("-", text.lower()).strip("-")[:laenge] or sonst


def ordner(stimme: str) -> str:
    """Der Ordner einer Stimme: lesbar und eindeutig. Für eine eingebaute Stimme ihr Name, für eine Klonstimme ihre Kennung;
    die Stimme ab Werk der Vertonung (leer) heißt "stimme"."""
    return f"{_lesbar(name_im_katalog(stimme), 40, 'stimme')}-{hashlib.sha256(stimme.encode()).hexdigest()[:8]}"


def dateiname(schluessel: str, *was: str) -> str:
    """Schlüssel (lesbar) und die Prüfsumme über alles, was den Ton ausmacht."""
    pruefsumme = hashlib.sha256("\n".join(was).encode()).hexdigest()[:16]
    return f"{_lesbar(schluessel, 100, 'ton')}-{pruefsumme}.wav"


def ablegen(datei: Path, ton: bytes) -> None:
    """Erst fertig bekommt die Datei ihren Namen; eine halbe gibt es nie, auch nicht, wenn zwei denselben Ton zugleich ablegen."""
    datei.parent.mkdir(parents=True, exist_ok=True)
    teil = datei.with_name(f".{datei.name}.{uuid.uuid4().hex[:8]}.teil")
    teil.write_bytes(ton)
    os.replace(teil, datei)
