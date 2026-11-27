"""Die Erkennungen eines Buchs als Begleiter `erkennung.jsonl` im Ort texte, neben fulltext.txt (services/storage.py): je
erkannter Seite eine Zeile (`Seitenerkennung`), nur angehängt; die jüngste Zeile einer Seite gilt. So bleibt jede Fassung
(etwa später eine Nachbesserung neben der klassischen Erkennung), und nichts muss neu erkannt werden, was eine Zeile hat.

Eine Zeile, die sich nicht lesen lässt (abgebrochen geschrieben), zählt nicht; die übrigen gelten weiter. Gelesen wird einmal je
Stand der Datei (Größe und Zeit), danach aus dem Speicher."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from backend.app.services.storage import get_sidecar_path
from backend.app.texterkennung.modelle import Erkennungen, Seitenerkennung

logger = logging.getLogger("buecherfreunde.texterkennung")
DATEI = "erkennung.jsonl"
GEMERKT = 8                                     # so viele Bücher bleiben gelesen im Speicher


def pfad(file_hash: str) -> Path:
    return get_sidecar_path(file_hash, DATEI)


def anhaengen(file_hash: str, erkennung: Seitenerkennung) -> None:
    """Eine erkannte Seite ans Ende der Datei, in einem Zug geschrieben."""
    ziel = pfad(file_hash)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("a", encoding="utf-8") as f:
        f.write(erkennung.model_dump_json() + "\n")


@lru_cache(maxsize=GEMERKT)
def _gelesen(datei: str, _groesse: int, _zeit: int) -> Erkennungen:
    aus: Erkennungen = {}
    with open(datei, encoding="utf-8") as f:
        for nr, zeile in enumerate(f, start=1):
            if not zeile.strip():
                continue
            try:
                e = Seitenerkennung.model_validate_json(zeile)
            except ValidationError:
                logger.info("%s: Zeile %d nicht lesbar, sie zählt nicht", datei, nr)
                continue
            aus[e.seite] = e
    return aus


def datei_lesen(datei: Path) -> Erkennungen:
    """Je Seite die jüngste Erkennung aus dieser Datei; ohne Datei leer."""
    try:
        stand = datei.stat()
    except OSError:
        return {}
    return dict(_gelesen(str(datei), stand.st_size, stand.st_mtime_ns))


def lesen(file_hash: str) -> Erkennungen:
    return datei_lesen(pfad(file_hash))
