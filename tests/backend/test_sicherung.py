"""Sicherungsregel: regelmäßig nach sieben Tagen, vor dem Aktualisieren nach 24 Stunden, von Hand sofort, nie ohne
Änderung, höchstens drei Stände. Alles in Wegwerf-Ordnern; die Datenbank hält wie im Betrieb eine offene Verbindung im
WAL-Modus, damit Änderungen zuerst nur in der -wal stehen."""

import os
import sqlite3
import zipfile
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from backend.app.core.config import settings
from backend.app.services import sicherung
from backend.app.services.sicherung import Anlass


@pytest.fixture
def datenbank(tmp_path, monkeypatch):
    """Offene Verbindung wie die der laufenden App; liefert eine Funktion, die eine Zeile schreibt."""
    monkeypatch.setattr(settings, "database_dir", tmp_path / "database")
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    settings.database_dir.mkdir()
    (settings.storage_dir / "ab" / "abc").mkdir(parents=True)
    (settings.storage_dir / "ab" / "abc" / "metadata.json").write_text("{}")
    verbindung = sqlite3.connect(settings.database_path)
    verbindung.execute("PRAGMA journal_mode=WAL")
    verbindung.execute("PRAGMA wal_autocheckpoint=0")
    verbindung.execute("CREATE TABLE buch (titel TEXT)")
    verbindung.commit()

    def schreiben(titel: str) -> None:
        verbindung.execute("INSERT INTO buch VALUES (?)", (titel,))
        verbindung.commit()

    yield schreiben
    verbindung.close()


def _alles_aelter(dauer: timedelta) -> None:
    """Als wäre seitdem `dauer` vergangen: Datenbank und Sicherungen um sie zurück, Namen passend zur neuen Zeit."""
    db = settings.database_path
    for datei in (db, db.with_name(db.name + "-wal")):
        if datei.exists():
            zeit = datei.stat().st_mtime - dauer.total_seconds()
            os.utime(datei, (zeit, zeit))
    for stand in sicherung.staende():
        zeit = stand.stat().st_mtime - dauer.total_seconds()
        neu = stand.with_name(f"buecherfreunde_backup_{datetime.fromtimestamp(zeit):%Y%m%d_%H%M%S}.zip")
        stand.rename(neu)
        os.utime(neu, (zeit, zeit))


def test_erste_sicherung_ist_geschlossen_auch_mit_wal(datenbank, monkeypatch):
    datenbank("Steppenwolf")
    beginn = datetime.now().timestamp() - 30
    monkeypatch.setattr(sicherung, "time", SimpleNamespace(time=lambda: beginn))
    lauf = sicherung.sichern(Anlass.HAND)

    assert lauf.neu and lauf.datei.name == f"buecherfreunde_backup_{datetime.fromtimestamp(beginn):%Y%m%d_%H%M%S}.zip"
    # Änderungszeit ist der Beginn der Kopie, nicht ihr Ende: was währenddessen geschrieben wird, gilt als Änderung.
    assert abs(lauf.datei.stat().st_mtime - beginn) < 0.01
    with zipfile.ZipFile(lauf.datei) as zf:
        assert set(zf.namelist()) == {"database/buecherfreunde.db", "VERSION", "metadata/ab/abc/metadata.json"}
        kopie = settings.database_dir / "kopie.db"
        kopie.write_bytes(zf.read("database/buecherfreunde.db"))
    with sqlite3.connect(kopie) as v:
        assert v.execute("SELECT titel FROM buch").fetchall() == [("Steppenwolf",)]
    # Keine Teil- oder Begleitdateien im Ordner der Sicherungen.
    assert [p.name for p in settings.backup_dir.iterdir()] == [lauf.datei.name]


def test_ohne_aenderung_entsteht_keine_neue(datenbank):
    erste = sicherung.sichern(Anlass.HAND)
    gleich = sicherung.sichern(Anlass.HAND)
    assert not gleich.neu and gleich.datei == erste.datei and "unverändert" in gleich.grund

    _alles_aelter(timedelta(minutes=1))
    datenbank("Siddhartha")
    geaendert = sicherung.sichern(Anlass.HAND)
    assert geaendert.neu and len(sicherung.staende()) == 2


def test_regelmaessig_erst_nach_sieben_tagen(datenbank):
    sicherung.sichern(Anlass.HAND)
    datenbank("Demian")
    _alles_aelter(timedelta(days=6))
    zu_jung = sicherung.sichern(Anlass.REGELMAESSIG)
    assert not zu_jung.neu and "zu jung" in zu_jung.grund

    _alles_aelter(timedelta(days=1, minutes=1))
    assert sicherung.sichern(Anlass.REGELMAESSIG).neu


def test_vor_dem_aktualisieren_erst_nach_24_stunden(datenbank):
    sicherung.sichern(Anlass.HAND)
    datenbank("Narziss und Goldmund")
    _alles_aelter(timedelta(hours=23))
    assert not sicherung.sichern(Anlass.AKTUALISIEREN).neu

    _alles_aelter(timedelta(hours=1, minutes=1))
    assert sicherung.sichern(Anlass.AKTUALISIEREN).neu


def test_jeder_lauf_raeumt_auf_drei_auf_und_fasst_nur_das_eigene_muster_an(datenbank):
    settings.backup_dir.mkdir()
    for tag in range(1, 6):
        alt = settings.backup_dir / f"buecherfreunde_backup_202603{tag:02d}_030000.zip"
        alt.write_bytes(b"alt")
        zeit = datetime(2026, 3, tag, 3, 0).timestamp()
        os.utime(alt, (zeit, zeit))
    fremd = [settings.backup_dir / "pre-update-0.4.6-20260301_030000.db", settings.backup_dir / ".etwas.teil"]
    for datei in fremd:
        datei.write_bytes(b"fremd")
    # Die Datenbank ist älter als die jüngste Sicherung: unverändert, keine neue, aber aufgeräumt wird trotzdem.
    zeit = datetime(2026, 3, 4, 12, 0).timestamp()
    for datei in settings.database_dir.glob("buecherfreunde.db*"):
        os.utime(datei, (zeit, zeit))

    lauf = sicherung.sichern(Anlass.REGELMAESSIG)

    assert not lauf.neu
    assert [p.name for p in sicherung.staende()] == [
        "buecherfreunde_backup_20260305_030000.zip",
        "buecherfreunde_backup_20260304_030000.zip",
        "buecherfreunde_backup_20260303_030000.zip",
    ]
    assert sorted(lauf.entfernt) == ["buecherfreunde_backup_20260301_030000.zip", "buecherfreunde_backup_20260302_030000.zip"]
    assert all(datei.exists() for datei in fremd)


def test_werte_stehen_in_den_einstellungen():
    assert (settings.sicherung_abstand_tage, settings.sicherung_vor_ausrollen_ab_stunden, settings.sicherung_behalten) == (7, 24, 3)
    assert sicherung.mindestalter(Anlass.HAND) == timedelta(0)
