"""Umbau beim Start für die Dateien je Buch (BF-80): danach hat jedes Buch genau eine Datei in `buch_datei`, sein Original.
Wiederholbar ohne Schaden, nichts geht verloren.

1. Hat jedes Buch seine Zeile, geschieht nichts (auch keine Sicherung).
2. Sonst entsteht zuerst eine Sicherung der Datenbank neben ihr (`<name>.vor-dateien-<Zeit>.db`, wie familie/umbau.py).
3. Dann in einer Einheit: je Buch ohne Zeile eine Zeile aus `books` (Prüfsumme, Format, Name, Größe), danach zählen. Hat nicht
   jedes Buch genau ein Original, rollt alles zurück und der Start bricht ab.

Neue Bücher bekommen ihre Zeile von der Datenbank selbst (Trigger `buch_datei_neu` in core/database.py). Der Umbau läuft auf
einer eigenen Verbindung, während keine andere offen ist (core/database.py, `connect`)."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from backend.app.familie.umbau import UmbauFehler, sicherung_neben

logger = logging.getLogger("buecherfreunde.formate_umbau")
OHNE_ORIGINAL = "SELECT id, hash, file_format, file_name, file_size FROM books WHERE id NOT IN (SELECT buch_id FROM buch_datei WHERE haupt = 1)"


@dataclass(frozen=True)
class Bericht:
    sicherung: Path
    nachgetragen: int
    buecher: int


def _zahl(v: sqlite3.Connection, sql: str) -> int:
    return v.execute(sql).fetchone()[0]


def noetig(v: sqlite3.Connection) -> bool:
    return v.execute(OHNE_ORIGINAL + " LIMIT 1").fetchone() is not None


def _nachtragen(v: sqlite3.Connection) -> int:
    zeilen = v.execute(OHNE_ORIGINAL).fetchall()
    v.executemany("INSERT INTO buch_datei (id, buch_id, hash, format, name, groesse, haupt) VALUES (?, ?, ?, ?, ?, ?, 1)",
                  [(str(uuid.uuid4()), z[0], z[1], z[2] or "", z[3] or "", z[4] or 0) for z in zeilen])
    return len(zeilen)


def _pruefen(v: sqlite3.Connection) -> int:
    """Jedes Buch hat genau ein Original, und es ist seine Datei; sonst UmbauFehler."""
    buecher = _zahl(v, "SELECT COUNT(*) FROM books")
    gut = _zahl(v, """SELECT COUNT(*) FROM books b WHERE (SELECT COUNT(*) FROM buch_datei d WHERE d.buch_id = b.id AND d.haupt = 1) = 1
                      AND EXISTS (SELECT 1 FROM buch_datei d WHERE d.buch_id = b.id AND d.haupt = 1 AND d.hash = b.hash)""")
    if gut != buecher:
        raise UmbauFehler(f"Dateien je Buch: {buecher} Bücher, {gut} mit genau einem Original")
    return buecher


def umbauen(pfad: Path) -> Bericht | None:
    """Trägt die fehlenden Originale nach; None, wenn nichts zu tun war."""
    with closing(sqlite3.connect(pfad, isolation_level=None)) as v:
        v.execute("PRAGMA busy_timeout=5000")
        if not noetig(v):
            return None
        sicherung = sicherung_neben(pfad, "dateien")
        logger.info("Vor dem Umbau der Dateien je Buch gesichert: %s", sicherung.name)
        v.execute("BEGIN IMMEDIATE")
        try:
            nachgetragen = _nachtragen(v)
            buecher = _pruefen(v)
            v.execute("COMMIT")
        except BaseException:
            v.execute("ROLLBACK")
            raise
    logger.info("Dateien je Buch: %d Originale nachgetragen, %d Bücher mit je einer Datei", nachgetragen, buecher)
    return Bericht(sicherung=sicherung, nachgetragen=nachgetragen, buecher=buecher)
