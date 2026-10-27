"""Sicherung der Datenbank nach der Sicherungsregel des Hauses.

Eine Sicherung ist ein ZIP im Ordner `settings.backup_dir`: die Datenbank als geschlossene Kopie (über die Sicherung
von SQLite, vollständig auch mit WAL), die Fassung und die metadata.json je Buch. Ob eine neue entsteht, entscheidet
die Regel selbst über das Alter der jüngsten, nicht der Takt des Aufrufs:

- regelmäßig (cron): nur, wenn die jüngste älter ist als `sicherung_abstand_tage`;
- vor dem Aktualisieren (update.sh): nur, wenn die jüngste älter ist als `sicherung_vor_ausrollen_ab_stunden`;
- von Hand (Einstellungen): sofort;
- nie ohne Änderung: sind Datenbankdatei und -wal beide älter als die jüngste Sicherung, entsteht keine neue.

Die Kopie entsteht unter einem Namen mit Punkt vorn, der nicht zum Muster passt, und bekommt erst fertig ihren Namen
und als Änderungszeit den Beginn der Kopie. Bei jedem Lauf bleiben höchstens `sicherung_behalten` Stände; angefasst
werden nur Dateien nach `MUSTER`.

Aufruf: python -m backend.app.services.sicherung regelmaessig|aktualisieren|hand
"""

import argparse
import logging
import os
import sqlite3
import sys
import time
import zipfile
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.sicherung")

MUSTER = "buecherfreunde_backup_*.zip"


class Anlass(StrEnum):
    REGELMAESSIG = "regelmaessig"
    AKTUALISIEREN = "aktualisieren"
    HAND = "hand"


@dataclass(frozen=True)
class Lauf:
    """Ergebnis eines Laufs: die neue Sicherung oder, wenn keine nötig war, die jüngste und der Grund."""

    neu: bool
    grund: str
    datei: Path
    entfernt: list[str] = field(default_factory=list)


def staende() -> list[Path]:
    """Alle Sicherungen, jüngste zuerst (nach Änderungszeit, also nach dem Beginn ihrer Kopie)."""
    ordner = settings.backup_dir
    if not ordner.is_dir():
        return []
    return sorted(ordner.glob(MUSTER), key=lambda p: p.stat().st_mtime, reverse=True)


def mindestalter(anlass: Anlass) -> timedelta:
    """So alt muss die jüngste Sicherung sein, damit dieser Anlass eine neue anlegt."""
    if anlass is Anlass.REGELMAESSIG:
        return timedelta(days=settings.sicherung_abstand_tage)
    if anlass is Anlass.AKTUALISIEREN:
        return timedelta(hours=settings.sicherung_vor_ausrollen_ab_stunden)
    return timedelta(0)


def unveraendert_seit(sicherung: Path) -> bool:
    """Datenbankdatei und -wal (falls vorhanden) sind beide älter als die Sicherung."""
    grenze = sicherung.stat().st_mtime
    datenbank = settings.database_path
    dateien = (datenbank, datenbank.with_name(datenbank.name + "-wal"))
    return all(d.stat().st_mtime < grenze for d in dateien if d.exists())


def aufraeumen() -> list[str]:
    """Höchstens `sicherung_behalten` Stände; die älteren gehen."""
    weg = staende()[settings.sicherung_behalten:]
    for datei in weg:
        datei.unlink()
        logger.info("Alte Sicherung entfernt: %s", datei.name)
    return [d.name for d in weg]


def sichern(anlass: Anlass) -> Lauf:
    """Ein Lauf nach der Sicherungsregel; aufgeräumt wird bei jedem Lauf, auch wenn keine neue entsteht."""
    juengste = next(iter(staende()), None)
    if juengste is not None:
        alter = timedelta(seconds=time.time() - juengste.stat().st_mtime)
        if alter < mindestalter(anlass):
            return Lauf(False, f"die jüngste ({juengste.name}) ist noch zu jung", juengste, aufraeumen())
        if unveraendert_seit(juengste):
            return Lauf(False, f"seit {juengste.name} unverändert", juengste, aufraeumen())
    datei = _erstellen()
    logger.info("Sicherung erstellt (%s): %s (%d Bytes)", anlass.value, datei.name, datei.stat().st_size)
    return Lauf(True, "", datei, aufraeumen())


def _erstellen() -> Path:
    if not settings.database_path.is_file():
        raise FileNotFoundError(f"Keine Datenbank unter {settings.database_path}")
    beginn = time.time()
    name = f"buecherfreunde_backup_{datetime.fromtimestamp(beginn):%Y%m%d_%H%M%S}.zip"
    ordner = settings.backup_dir
    ordner.mkdir(parents=True, exist_ok=True)
    teil = ordner / f".{name}.teil"
    kopie = ordner / f".{name}.db.teil"
    try:
        _datenbank_kopieren(kopie)
        _packen(teil, kopie)
        ziel = ordner / name
        teil.rename(ziel)
        os.utime(ziel, (beginn, beginn))
        return ziel
    finally:
        kopie.unlink(missing_ok=True)
        teil.unlink(missing_ok=True)


def _datenbank_kopieren(ziel: Path) -> None:
    """Geschlossene Kopie, ohne die laufende App anzuhalten."""
    with closing(sqlite3.connect(settings.database_path)) as quelle, closing(sqlite3.connect(ziel)) as kopie:
        quelle.backup(kopie)


def _packen(ziel: Path, datenbank: Path) -> None:
    """Aufbau wie gehabt, damit das Zurückspielen in den Einstellungen jede Sicherung versteht."""
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(datenbank, "database/buecherfreunde.db")
        zf.writestr("VERSION", settings.version + "\n")
        speicher = settings.storage_dir
        if speicher.exists():
            for meta in speicher.rglob("metadata.json"):
                zf.write(meta, f"metadata/{meta.relative_to(speicher)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.app.services.sicherung", description=__doc__.splitlines()[0])
    parser.add_argument("anlass", choices=[a.value for a in Anlass])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    lauf = sichern(Anlass(args.anlass))
    print(f"Gesichert: {lauf.datei.name}" if lauf.neu else f"Keine neue Sicherung nötig: {lauf.grund}")
    for name in lauf.entfernt:
        print(f"Entfernt: {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
