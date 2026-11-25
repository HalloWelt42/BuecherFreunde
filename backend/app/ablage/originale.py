"""Das Original eines Buchs, egal wo es liegt: auf dem Gerät (Entwicklung), im Zwischenspeicher oder in der Kellerwolke.

Im Betrieb liegen Originale nur in der Kellerwolke; gelesen werden sie über einen begrenzten Zwischenspeicher im
Arbeitsspeicher (ältester Zugriff fällt zuerst heraus). Welcher Knoten zu welchem Buch gehört, steht in der Tabelle
`ablage_datei` der Datenbank."""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import threading
from pathlib import Path

from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.originale")
_schloss = threading.Lock()
_je_buch: dict[str, threading.Lock] = {}


def eintrag(file_hash: str) -> dict | None:
    """Knoten, Name und Größe laut Datenbank (eigene kurze Leseverbindung, auch aus Fäden)."""
    if not settings.database_path.exists():
        return None
    c = sqlite3.connect(f"file:{settings.database_path}?mode=ro", uri=True, timeout=5)
    try:
        z = c.execute("SELECT knoten, name, groesse, begleiter FROM ablage_datei WHERE hash = ?", (file_hash,)).fetchone()
    except sqlite3.OperationalError:
        return None                                       # Datenbank noch ohne die Tabelle
    finally:
        c.close()
    return {"knoten": z[0], "name": z[1], "groesse": z[2], "begleiter": z[3]} if z else None


def _platz_schaffen(braucht: int) -> None:
    dateien = sorted((f for f in settings.zwischen_dir.glob("original/*/*") if f.is_file()), key=lambda f: f.stat().st_atime)
    summe = sum(f.stat().st_size for f in dateien)
    grenze = settings.zwischen_mb * 1024 * 1024
    for f in dateien:
        if summe + braucht <= grenze:
            return
        summe -= f.stat().st_size
        f.unlink(missing_ok=True)


def holen(file_hash: str) -> Path | None:
    """Pfad zum Original, bei Bedarf aus der Kellerwolke geholt und geprüft. Läuft in einem Faden."""
    ablage = eintrag(file_hash)
    if ablage is None or not wolke.bereit:
        return None
    ziel = settings.zwischen_dir / "original" / file_hash / Path(ablage["name"]).name
    if ziel.exists():
        os.utime(ziel)
        return ziel
    with _schloss:
        schloss = _je_buch.setdefault(file_hash, threading.Lock())
    with schloss:
        if ziel.exists():
            return ziel
        ziel.parent.mkdir(parents=True, exist_ok=True)
        _platz_schaffen(ablage["groesse"] or 0)
        halb = ziel.with_name(ziel.name + ".halb")
        try:
            wolke.holen(ablage["knoten"], halb)
            summe = hashlib.sha256()
            with halb.open("rb") as f:
                while stueck := f.read(1 << 20):
                    summe.update(stueck)
            if summe.hexdigest() != file_hash:
                raise WolkeFehler("Die Datei in der Kellerwolke hat eine andere Prüfsumme")
            halb.rename(ziel)
            return ziel
        except (WolkeFehler, OSError) as f:
            logger.warning("Original %s nicht geholt: %s", file_hash[:12], f)
            return None
        finally:
            halb.unlink(missing_ok=True)
