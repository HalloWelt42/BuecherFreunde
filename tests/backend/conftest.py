"""Gemeinsame Fixtures fuer Backend-Tests.

Stellt eine in-memory SQLite-Datenbank und temporaere Verzeichnisse bereit,
damit alle Tests ohne laufendes Backend und ohne Netzwerk funktionieren.
"""

import asyncio
import hashlib
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
import pytest_asyncio

from backend.app.core.database import SCHEMA_SQL, Database


# ---------------------------------------------------------------------------
# Event-Loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Erstellt einen Event-Loop fuer die gesamte Testsitzung."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Temporaere Verzeichnisse
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_dir(tmp_path):
    """Stellt ein temporaeres Verzeichnis bereit."""
    return tmp_path


@pytest.fixture
def storage_dir(tmp_path):
    """Stellt ein temporaeres Storage-Verzeichnis bereit."""
    d = tmp_path / "storage"
    d.mkdir()
    return d


@pytest.fixture
def external_dir(tmp_path):
    """Stellt ein temporaeres External-Verzeichnis bereit."""
    d = tmp_path / "external"
    d.mkdir()
    return d


@pytest.fixture
def import_dir(tmp_path):
    """Stellt ein temporaeres Import-Verzeichnis bereit."""
    d = tmp_path / "import"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Settings-Override
# ---------------------------------------------------------------------------

@pytest.fixture
def test_settings(tmp_path, storage_dir, external_dir, import_dir):
    """Ueberschreibt die globalen Settings fuer Tests."""
    database_dir = tmp_path / "database"
    database_dir.mkdir()

    with patch("backend.app.core.config.settings") as mock_settings:
        mock_settings.storage_dir = storage_dir
        mock_settings.external_dir = external_dir
        mock_settings.import_dir = import_dir
        mock_settings.database_dir = database_dir
        mock_settings.database_path = database_dir / "test.db"
        mock_settings.api_token = "test-token"
        mock_settings.openlibrary_enabled = False
        mock_settings.lm_studio_enabled = False
        mock_settings.log_level = "debug"
        yield mock_settings


# ---------------------------------------------------------------------------
# In-Memory-Datenbank
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Erstellt eine SQLite-Testdatenbank mit dem vollstaendigen Schema."""
    db_path = tmp_path / "test.db"
    database = Database(db_path=db_path)
    await database.connect()
    yield database
    await database.disconnect()


@pytest_asyncio.fixture
async def test_db_mit_daten(test_db):
    """Datenbank mit Beispiel-Buechern fuer Such-Tests."""
    buecher = [
        {
            "hash": hashlib.sha256(b"buch1").hexdigest(),
            "title": "Python Grundlagen",
            "author": "Max Mustermann",
            "isbn": "9783000000001",
            "publisher": "Testverlag",
            "year": 2023,
            "language": "de",
            "description": "Ein Einfuehrungsbuch in Python",
            "file_format": ".pdf",
            "file_size": 1024000,
            "file_name": "python_grundlagen.pdf",
            "storage_path": "/storage/ab/cd/abcdef",
            "page_count": 350,
            "fts_content": "Python ist eine vielseitige Programmiersprache. "
                          "Variablen, Schleifen, Funktionen und Klassen bilden die Grundlagen.",
        },
        {
            "hash": hashlib.sha256(b"buch2").hexdigest(),
            "title": "Maschinelles Lernen mit Python",
            "author": "Erika Beispiel",
            "isbn": "9783000000002",
            "publisher": "Technikverlag",
            "year": 2024,
            "language": "de",
            "description": "Machine Learning Konzepte",
            "file_format": ".epub",
            "file_size": 2048000,
            "file_name": "ml_python.epub",
            "storage_path": "/storage/ef/gh/efghij",
            "page_count": 500,
            "fts_content": "Neuronale Netze und Deep Learning sind Teilgebiete des maschinellen Lernens. "
                          "Python bietet mit TensorFlow und PyTorch maechtige Werkzeuge.",
        },
        {
            "hash": hashlib.sha256(b"buch3").hexdigest(),
            "title": "Linux-Administration",
            "author": "Hans Systemmann",
            "isbn": "9783000000003",
            "publisher": "Adminverlag",
            "year": 2022,
            "language": "de",
            "description": "Systemverwaltung unter Linux",
            "file_format": ".pdf",
            "file_size": 3072000,
            "file_name": "linux_admin.pdf",
            "storage_path": "/storage/ij/kl/ijklmn",
            "page_count": 720,
            "fts_content": "Linux bietet eine stabile und sichere Plattform fuer Server. "
                          "Systemd, Netzwerkkonfiguration und Bash-Scripting gehoeren zum Alltag.",
        },
    ]

    for buch in buecher:
        sql = """
            INSERT INTO books (
                hash, title, author, isbn, publisher, year, language,
                description, file_format, file_size, file_name, storage_path,
                page_count, fts_content
            ) VALUES (
                :hash, :title, :author, :isbn, :publisher, :year, :language,
                :description, :file_format, :file_size, :file_name, :storage_path,
                :page_count, :fts_content
            )
        """
        await test_db.execute(sql, buch)

    await test_db.commit()
    yield test_db


# ---------------------------------------------------------------------------
# Hilfsfunktionen fuer Testdateien
# ---------------------------------------------------------------------------

@pytest.fixture
def erstelle_textdatei(tmp_path):
    """Factory-Fixture zum Erstellen von Textdateien."""
    def _erstelle(name: str, inhalt: str) -> Path:
        datei = tmp_path / name
        datei.write_text(inhalt, encoding="utf-8")
        return datei
    return _erstelle


@pytest.fixture
def erstelle_binaerdatei(tmp_path):
    """Factory-Fixture zum Erstellen von Binaerdateien."""
    def _erstelle(name: str, daten: bytes) -> Path:
        datei = tmp_path / name
        datei.write_bytes(daten)
        return datei
    return _erstelle


@pytest.fixture
def beispiel_text_datei(erstelle_textdatei):
    """Erstellt eine einfache Textdatei als Testbuch."""
    inhalt = """Dies ist ein Testbuch.

Kapitel 1: Einfuehrung
In diesem Kapitel geht es um die Grundlagen.
Wir behandeln verschiedene Themen der Programmierung.

Kapitel 2: Fortgeschrittene Konzepte
Hier vertiefen wir die Grundlagen.
Datenstrukturen und Algorithmen stehen im Fokus.

Kapitel 3: Praxis
Zum Abschluss setzen wir das Gelernte in die Praxis um.
"""
    return erstelle_textdatei("testbuch.txt", inhalt)


@pytest.fixture
def beispiel_markdown_datei(erstelle_textdatei):
    """Erstellt eine Markdown-Datei mit Ueberschrift."""
    inhalt = """# Mein Testbuch in Markdown

## Kapitel 1
Das ist der Inhalt des ersten Kapitels.

## Kapitel 2
Hier kommt der zweite Teil.
"""
    return erstelle_textdatei("testbuch.md", inhalt)
