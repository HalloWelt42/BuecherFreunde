"""Testinfrastruktur fuer API-Integrationstests.

Stellt TestClient, Test-Datenbank und Authentifizierung bereit.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import settings
from backend.app.core.database import Database, db
from backend.app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Erstellt einen Event-Loop fuer die gesamte Test-Session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def api_token() -> str:
    """Gibt den konfigurierten API-Token zurueck."""
    return settings.api_token


@pytest.fixture(scope="session")
def auth_headers(api_token: str) -> dict[str, str]:
    """Standard-Header mit Bearer-Token fuer authentifizierte Requests."""
    return {"Authorization": f"Bearer {api_token}"}


@pytest_asyncio.fixture(scope="function")
async def test_db(tmp_path: Path):
    """Erstellt eine temporaere Test-Datenbank pro Testfunktion.

    Ueberschreibt die globale db-Instanz mit einer frischen Datenbank,
    damit Tests isoliert voneinander laufen.
    """
    db_path = tmp_path / "test_buecherfreunde.db"
    test_database = Database(db_path=db_path)
    await test_database.connect()

    # Globale db-Instanz temporaer ersetzen
    original_connection = db._connection
    original_path = db.db_path
    db._connection = test_database._connection
    db.db_path = test_database.db_path

    yield test_database

    # Wiederherstellen und aufraeuemen
    db._connection = original_connection
    db.db_path = original_path
    await test_database.disconnect()


@pytest_asyncio.fixture(scope="function")
async def client(test_db: Database, auth_headers: dict[str, str]):
    """Erstellt einen AsyncClient fuer HTTP-Requests gegen die App.

    Die App nutzt automatisch die Test-Datenbank ueber die ersetzte
    globale db-Instanz.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers=auth_headers,
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def client_ohne_auth(test_db: Database):
    """AsyncClient ohne Authentifizierung fuer Fehlertests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as ac:
        yield ac


async def buch_erstellen(test_db: Database, **kwargs) -> int:
    """Hilfsfunktion: Legt ein Testbuch in der Datenbank an.

    Gibt die Buch-ID zurueck.
    """
    defaults = {
        "hash": "testhash123",
        "title": "Testbuch",
        "author": "Testautor",
        "isbn": "978-3-16-148410-0",
        "publisher": "Testverlag",
        "year": 2024,
        "language": "de",
        "description": "Ein Testbuch fuer die API-Tests",
        "file_format": "pdf",
        "file_size": 1024000,
        "file_name": "testbuch.pdf",
        "storage_path": "/storage/te/testhash123",
        "cover_path": "",
        "page_count": 200,
        "fts_content": "Dies ist der Inhalt des Testbuchs ueber Python Programmierung",
    }
    defaults.update(kwargs)

    cursor = await test_db.execute(
        """INSERT INTO books (hash, title, author, isbn, publisher, year, language,
           description, file_format, file_size, file_name, storage_path, cover_path,
           page_count, fts_content)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            defaults["hash"],
            defaults["title"],
            defaults["author"],
            defaults["isbn"],
            defaults["publisher"],
            defaults["year"],
            defaults["language"],
            defaults["description"],
            defaults["file_format"],
            defaults["file_size"],
            defaults["file_name"],
            defaults["storage_path"],
            defaults["cover_path"],
            defaults["page_count"],
            defaults["fts_content"],
        ),
    )
    await test_db.commit()
    return cursor.lastrowid


async def kategorie_erstellen(test_db: Database, name: str = "Testkategorie",
                               parent_id: int | None = None,
                               sort_order: int = 0) -> int:
    """Hilfsfunktion: Legt eine Testkategorie an. Gibt die ID zurueck."""
    import re
    slug = re.sub(r"[^\w\s-]", "", name.lower().strip())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")

    cursor = await test_db.execute(
        "INSERT INTO categories (name, slug, parent_id, sort_order) VALUES (?, ?, ?, ?)",
        (name, slug, parent_id, sort_order),
    )
    await test_db.commit()
    return cursor.lastrowid


async def tag_erstellen(test_db: Database, name: str = "Testtag",
                         color: str = "#ff0000") -> int:
    """Hilfsfunktion: Legt einen Testtag an. Gibt die ID zurueck."""
    import re
    slug = re.sub(r"[^\w\s-]", "", name.lower().strip())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")

    cursor = await test_db.execute(
        "INSERT INTO tags (name, slug, color) VALUES (?, ?, ?)",
        (name, slug, color),
    )
    await test_db.commit()
    return cursor.lastrowid
