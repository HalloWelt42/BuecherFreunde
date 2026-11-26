"""Umbau der Datenbank für die Familie (BF-78): beim Start, wiederholbar ohne Schaden, nichts geht verloren.

1. Ist alles da (ein Profil Verwaltung, jede persönliche Tabelle mit `profil_id`), geschieht nichts.
2. Muss eine bestehende Tabelle umgebaut werden, entsteht zuerst eine Sicherung der Datenbank als Datei neben ihr
   (`<name>.vor-familie-<Zeit>.db`, über die Sicherung von SQLite, wie services/sicherung.py: erst fertig unter ihrem Namen).
3. Dann in einer Einheit: die Tabellen der Familie, das erste Profil Verwaltung (Name aus dem Konto des Geräts, ohne PIN), und je
   persönliche Tabelle: neu anlegen, alle Zeilen für dieses Profil hinein kopieren, beide zählen, erst bei gleicher Zahl die alte
   ersetzen. Stimmt eine Zahl nicht, rollt alles zurück und der Start bricht ab. Spalten, die eine alte Tabelle über die Form
   hinaus hat, kommen mit; Nummern (AUTOINCREMENT) bleiben, wie sie waren.

Der Umbau läuft auf einer eigenen Verbindung, während keine andere offen ist (core/database.py, `connect`)."""

from __future__ import annotations

import logging
import os
import sqlite3
import time
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from backend.app.familie.schema import FAMILIE_SQL, PERSOENLICH, Form
from backend.app.familie.stufen import stufenbuch

logger = logging.getLogger("buecherfreunde.familie.umbau")
NEU = "__familie"                                    # Endung der neuen Tabelle während des Umbaus


class UmbauFehler(RuntimeError):
    """Der Umbau stimmt nicht; nichts wurde geändert."""


@dataclass(frozen=True)
class Tabellenstand:
    tabelle: str
    art: str                                         # umgebaut, angelegt
    vorher: int
    nachher: int


@dataclass
class Bericht:
    profil_id: str
    profil_neu: bool
    sicherung: Path | None = None
    tabellen: list[Tabellenstand] = field(default_factory=list)


def anweisungen(sql: str) -> list[str]:
    """Die Anweisungen eines Skripts einzeln, auch Trigger mit Semikolon im Inneren."""
    fertig, teil = [], ""
    for zeile in sql.splitlines(keepends=True):
        teil += zeile
        if sqlite3.complete_statement(teil):
            if teil.strip():
                fertig.append(teil.strip())
            teil = ""
    return fertig


def _gibt_es(v: sqlite3.Connection, tabelle: str) -> bool:
    return v.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabelle,)).fetchone() is not None


def _spalten(v: sqlite3.Connection, tabelle: str) -> list[tuple]:
    """PRAGMA table_info: (Nummer, Name, Art, nicht leer, Vorgabe, Schlüssel)."""
    return v.execute(f"PRAGMA table_info({tabelle})").fetchall()


def _umzubauen(v: sqlite3.Connection) -> list[Form]:
    return [f for f in PERSOENLICH if _gibt_es(v, f.tabelle) and "profil_id" not in {s[1] for s in _spalten(v, f.tabelle)}]


def noetig(v: sqlite3.Connection) -> bool:
    if not _gibt_es(v, "profil") or v.execute("SELECT 1 FROM profil WHERE rolle = 'verwaltung' LIMIT 1").fetchone() is None:
        return True
    return any(not _gibt_es(v, f.tabelle) for f in PERSOENLICH) or bool(_umzubauen(v))


def sicherung_neben(pfad: Path) -> Path:
    """Geschlossene Kopie der Datenbank neben ihr; erst fertig bekommt sie ihren Namen."""
    ziel = pfad.with_name(f"{pfad.stem}.vor-familie-{datetime.now():%Y%m%d_%H%M%S}{pfad.suffix}")
    teil = ziel.with_name(f".{ziel.name}.teil")
    try:
        with closing(sqlite3.connect(pfad)) as quelle, closing(sqlite3.connect(teil)) as kopie:
            quelle.backup(kopie)
        os.replace(teil, ziel)
    finally:
        teil.unlink(missing_ok=True)
    return ziel


def _name_des_kontos(v: sqlite3.Connection) -> str | None:
    """Ohne Kellerwolke ist das Konto des Geräts das eigene Konto der App; sonst kommt der Name beim Anmelden."""
    if not _gibt_es(v, "nutzer"):
        return None
    z = v.execute("SELECT name FROM nutzer ORDER BY id LIMIT 1").fetchone()
    return z[0] if z else None


def _erstes_profil(v: sqlite3.Connection) -> tuple[str, bool]:
    """Das erste Profil Verwaltung; gibt es keins, entsteht es ohne PIN."""
    z = v.execute("SELECT id FROM profil WHERE rolle = 'verwaltung' ORDER BY sortierung, angelegt_am, id LIMIT 1").fetchone()
    if z:
        return z[0], False
    nr, name = str(uuid.uuid4()), _name_des_kontos(v)
    v.execute("INSERT INTO profil (id, name, zeichen, rolle, sortierung, name_vom_konto) VALUES (?, ?, 'user', 'verwaltung', 0, ?)",
              (nr, name or stufenbuch().rollen["verwaltung"].name, 0 if name else 1))
    return nr, True


def _zahl(v: sqlite3.Connection, tabelle: str) -> int:
    return v.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0]


def _weitere(alt: list[tuple], form: Form) -> tuple[str, ...]:
    """Spalten der alten Tabelle, die die Form nicht kennt: mit Art und Vorgabe, ohne Bindungen (nichts geht verloren)."""
    return tuple(f"{s[1]} {s[2] or ''}".strip() + (f" DEFAULT ({s[4]})" if s[4] is not None else "") for s in alt if s[1] not in form.namen)


def _folge(v: sqlite3.Connection, tabelle: str) -> int | None:
    if not _gibt_es(v, "sqlite_sequence"):
        return None
    z = v.execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (tabelle,)).fetchone()
    return z[0] if z else None


def _umbauen(v: sqlite3.Connection, form: Form, profil_id: str) -> Tabellenstand:
    alt = _spalten(v, form.tabelle)
    neu = form.tabelle + NEU
    v.execute(f"DROP TABLE IF EXISTS {neu}")
    v.execute(form.anlegen(neu, _weitere(alt, form)))
    namen = ", ".join(s[1] for s in alt)
    v.execute(f"INSERT INTO {neu} (profil_id, {namen}) SELECT ?, {namen} FROM {form.tabelle}", (profil_id,))
    vorher, nachher = _zahl(v, form.tabelle), _zahl(v, neu)
    if vorher != nachher:
        raise UmbauFehler(f"{form.tabelle}: {vorher} Zeilen vorher, {nachher} danach")
    folge = _folge(v, form.tabelle)
    v.execute(f"DROP TABLE {form.tabelle}")
    v.execute(f"ALTER TABLE {neu} RENAME TO {form.tabelle}")
    if folge is not None:
        v.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = ?", (folge, form.tabelle))
        v.execute("INSERT INTO sqlite_sequence (name, seq) SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name = ?)",
                  (form.tabelle, folge, form.tabelle))
    return Tabellenstand(form.tabelle, "umgebaut", vorher, _zahl(v, form.tabelle))


def _in_einer_einheit(v: sqlite3.Connection, bericht: Bericht) -> None:
    v.execute("BEGIN IMMEDIATE")
    try:
        for a in anweisungen(FAMILIE_SQL):
            v.execute(a)
        bericht.profil_id, bericht.profil_neu = _erstes_profil(v)
        umbauen = {f.tabelle for f in _umzubauen(v)}
        for form in PERSOENLICH:
            if form.tabelle in umbauen:
                bericht.tabellen.append(_umbauen(v, form, bericht.profil_id))
            elif not _gibt_es(v, form.tabelle):
                v.execute(form.anlegen())
                bericht.tabellen.append(Tabellenstand(form.tabelle, "angelegt", 0, 0))
            for index in form.indizes:
                v.execute(index)
        v.execute("COMMIT")
    except BaseException:
        v.execute("ROLLBACK")
        raise


def umbauen(pfad: Path) -> Bericht | None:
    """Bringt die Datenbank in die Form der Familie; None, wenn nichts zu tun war."""
    with closing(sqlite3.connect(pfad, isolation_level=None)) as v:
        v.execute("PRAGMA busy_timeout=5000")
        if not noetig(v):
            for a in anweisungen(FAMILIE_SQL):          # was eine spätere Fassung dazu bringt, ohne Umbau
                v.execute(a)
            return None
        beginn = time.monotonic()
        bericht = Bericht(profil_id="", profil_neu=False)
        if _umzubauen(v):
            bericht.sicherung = sicherung_neben(pfad)
            logger.info("Vor dem Umbau für die Familie gesichert: %s", bericht.sicherung.name)
        v.execute("PRAGMA foreign_keys=OFF")             # Tabellen tauschen, ohne dass Löschen nach Bindungen greift
        try:
            _in_einer_einheit(v, bericht)
        finally:
            v.execute("PRAGMA foreign_keys=ON")
        for t in bericht.tabellen:
            logger.info("Familie: %s %s, %d Zeilen vorher, %d danach", t.tabelle, t.art, t.vorher, t.nachher)
        logger.info("Umbau für die Familie fertig in %.1f s, erstes Profil %s", time.monotonic() - beginn, bericht.profil_id)
        return bericht
