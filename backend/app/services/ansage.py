"""Kurze Ansagen (BF-78): Hinweise und Tasten sprechen im Kinderbereich, ein Satz als WAV aus dem Sprechdienst
(services/vorlesen.py). Gemerkt wird jede Ansage im Zwischenspeicher (`zwischen/ansagen`), Schlüssel aus Stimme und Prüfsumme
des Texts; so kommt ein wiederholtes "Weiter" sofort. Der Speicher begrenzt sich selbst (`ANSAGEN_MB`): darüber gehen die
Ansagen, die am längsten keiner gehört hat. Ohne Sprechdienst kommt ein `VorlesenFehler`; die Oberfläche spricht dann mit der
Stimme des Geräts."""

from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from backend.app.core.config import settings
from backend.app.services import vorlesen

ORDNER = "ansagen"
TEXT_HOECHSTENS = 300


@dataclass(frozen=True)
class Ansage:
    ton: bytes
    gemerkt: bool                                    # kam aus dem Zwischenspeicher


def ordner() -> Path:
    return settings.zwischen_dir / ORDNER


def schluessel(text: str, stimme: str) -> str:
    """Die Stimme und die Prüfsumme des Texts; beides zusammen nennt genau eine Ansage."""
    return f"{hashlib.sha256(stimme.encode()).hexdigest()[:16]}-{hashlib.sha256(text.encode()).hexdigest()}"


def _lesen(datei: Path) -> bytes | None:
    try:
        ton = datei.read_bytes()
    except OSError:
        return None
    os.utime(datei)                                  # zuletzt gehört: bleibt beim Aufräumen am längsten
    return ton


def _merken(datei: Path, ton: bytes) -> None:
    datei.parent.mkdir(parents=True, exist_ok=True)
    teil = datei.with_name(f".{datei.name}.teil")
    teil.write_bytes(ton)
    os.replace(teil, datei)
    _aufraeumen(datei.parent)


def _aufraeumen(ort: Path) -> None:
    """Über der Grenze gehen die Ansagen, die am längsten keiner gehört hat."""
    dateien = sorted((d for d in ort.glob("*.wav")), key=lambda d: d.stat().st_mtime, reverse=True)
    erlaubt, belegt = settings.ansagen_mb * 1024 * 1024, 0
    for d in dateien:
        belegt += d.stat().st_size
        if belegt > erlaubt:
            d.unlink(missing_ok=True)


async def sprechen(text: str, stimme: str) -> Ansage:
    datei = ordner() / f"{schluessel(text, stimme)}.wav"
    if (ton := await asyncio.to_thread(_lesen, datei)) is not None:
        return Ansage(ton, True)
    ton = await vorlesen.satz(text, stimme)
    await asyncio.to_thread(_merken, datei, ton)
    return Ansage(ton, False)
