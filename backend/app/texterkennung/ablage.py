"""Die Erkennungen eines Buchs als Begleiter `erkennung.jsonl` im Ort texte, neben fulltext.txt (services/storage.py): je
erkannter Seite und Fassung eine Zeile (`Seitenerkennung`), nur angehängt. So bleibt jede Fassung (die klassische Erkennung und
ihre Nachbesserung, BF-118), und nichts muss neu erkannt werden, was eine Zeile hat.

Welche Fassung einer Seite gilt: die gewählte (`Fassungswahl`, auch eine Zeile, die jüngste Wahl zählt), sonst die jüngste
Fassung. Die Wahl liegt mit den Fassungen in derselben Datei, so übersteht sie wie diese einen Neuaufbau.

Eine Zeile, die sich nicht lesen lässt (abgebrochen geschrieben), zählt nicht; die übrigen gelten weiter. Gelesen wird einmal je
Stand der Datei (Größe und Zeit), danach aus dem Speicher."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from backend.app.services.storage import get_sidecar_path
from backend.app.texterkennung.modelle import Erkennungen, Fassungsstand, Fassungswahl, Herkunft, Seitenerkennung

logger = logging.getLogger("buecherfreunde.texterkennung")
DATEI = "erkennung.jsonl"
GEMERKT = 8                                     # so viele Bücher bleiben gelesen im Speicher


def pfad(file_hash: str) -> Path:
    return get_sidecar_path(file_hash, DATEI)


def _anhaengen(file_hash: str, zeile: Seitenerkennung | Fassungswahl) -> None:
    ziel = pfad(file_hash)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("a", encoding="utf-8") as f:
        f.write(zeile.model_dump_json() + "\n")


def anhaengen(file_hash: str, erkennung: Seitenerkennung) -> None:
    """Eine erkannte Seite ans Ende der Datei, in einem Zug geschrieben."""
    _anhaengen(file_hash, erkennung)


def waehlen(file_hash: str, seite: int, gilt: Herkunft) -> None:
    """Diese Fassung der Seite soll gelten (die andere bleibt gespeichert)."""
    _anhaengen(file_hash, Fassungswahl(seite=seite, gilt=gilt, gewaehlt_am=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")))


@dataclass
class _Gelesen:
    jeweils: dict[int, dict[str, Seitenerkennung]] = field(default_factory=dict)   # je Seite die jüngste Zeile je Herkunft
    juengste: dict[int, Seitenerkennung] = field(default_factory=dict)
    wahl: dict[int, str] = field(default_factory=dict)

    def gilt(self, seite: int) -> Seitenerkennung | None:
        """Die gewählte Fassung, wenn es sie gibt; sonst die jüngste"""
        gewaehlt = self.wahl.get(seite)
        if gewaehlt and (e := self.jeweils.get(seite, {}).get(gewaehlt)) is not None:
            return e
        return self.juengste.get(seite)


def _zeile(text: str) -> Seitenerkennung | Fassungswahl | None:
    for art in (Seitenerkennung, Fassungswahl):
        try:
            return art.model_validate_json(text)
        except ValidationError:
            continue
    return None


@lru_cache(maxsize=GEMERKT)
def _gelesen(datei: str, _groesse: int, _zeit: int) -> _Gelesen:
    aus = _Gelesen()
    with open(datei, encoding="utf-8") as f:
        for nr, text in enumerate(f, start=1):
            if not text.strip():
                continue
            z = _zeile(text)
            if isinstance(z, Seitenerkennung):
                aus.jeweils.setdefault(z.seite, {})[z.herkunft] = z
                aus.juengste[z.seite] = z
            elif isinstance(z, Fassungswahl):
                aus.wahl[z.seite] = z.gilt
            else:
                logger.info("%s: Zeile %d nicht lesbar, sie zählt nicht", datei, nr)
    return aus


def _lesen(datei: Path) -> _Gelesen:
    try:
        stand = datei.stat()
    except OSError:
        return _Gelesen()
    return _gelesen(str(datei), stand.st_size, stand.st_mtime_ns)


def datei_lesen(datei: Path) -> Erkennungen:
    """Je Seite die geltende Erkennung aus dieser Datei (gewählt, sonst die jüngste); ohne Datei leer."""
    g = _lesen(datei)
    return {seite: e for seite in g.juengste if (e := g.gilt(seite)) is not None}


def lesen(file_hash: str) -> Erkennungen:
    return datei_lesen(pfad(file_hash))


def fassungen(file_hash: str) -> dict[int, Fassungsstand]:
    """Je erkannter Seite, welche Fassungen es gibt und welche gilt."""
    g = _lesen(pfad(file_hash))
    return {seite: Fassungsstand(klassisch="klassisch" in je, ki="ki" in je, gilt=e.herkunft)
            for seite, je in g.jeweils.items() if (e := g.gilt(seite)) is not None}


def fassung(file_hash: str, seite: int, herkunft: Herkunft) -> Seitenerkennung | None:
    """Die jüngste Fassung dieser Herkunft einer Seite, gleich ob sie gilt."""
    return _lesen(pfad(file_hash)).jeweils.get(seite, {}).get(herkunft)
