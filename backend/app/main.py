"""BuecherFreunde Backend - FastAPI Hauptanwendung."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.ai import router as ai_router
from backend.app.api.authors import router as authors_router
from backend.app.api.backup import router as backup_router
from backend.app.api.books import router as books_router
from backend.app.api.categories import router as categories_router
from backend.app.api.config import router as config_router
from backend.app.api.gutenberg import router as gutenberg_router
from backend.app.api.imports import router as imports_router
from backend.app.api.metadata import router as metadata_router
from backend.app.api.search import router as search_router
from backend.app.api.collections import router as collections_router
from backend.app.api.highlights import router as highlights_router
from backend.app.api.labels import router as labels_router
from backend.app.api.notes import router as notes_router
from backend.app.api.user_data import router as user_data_router
from backend.app.core.config import settings
from backend.app.core.database import db

logger = logging.getLogger("buecherfreunde")


MARKER_FILE = ".buecherfreunde"


def _check_storage_mount() -> None:
    """Prüft ob das Storage-Verzeichnis erreichbar ist.

    Beim ersten Start wird eine Marker-Datei angelegt. Bei jedem weiteren
    Start muss diese Datei existieren - fehlt sie (z.B. weil die externe
    Festplatte nicht gemountet ist), wird der Start abgebrochen statt eine
    neue leere DB auf der SD-Karte anzulegen.
    """
    marker = settings.storage_dir / MARKER_FILE

    if not settings.storage_dir.exists():
        raise RuntimeError(
            f"ABBRUCH: Storage-Verzeichnis {settings.storage_dir} nicht erreichbar. "
            "Ist die externe Festplatte gemountet?"
        )

    # Marker anlegen falls noch nicht vorhanden
    if not marker.exists():
        try:
            marker.touch()
            logger.info("Marker-Datei angelegt: %s", marker)
        except OSError as e:
            raise RuntimeError(
                f"ABBRUCH: Kann Marker-Datei {marker} nicht erstellen: {e}. "
                "Sind die Schreibrechte korrekt?"
            ) from e


def _ensure_directories() -> None:
    """Erstellt alle benötigten Verzeichnisse beim Start."""
    dirs = [
        settings.storage_dir,
        settings.import_dir,
        settings.database_dir,
        settings.backup_dir,
    ]
    # external_dir nur erstellen wenn konfiguriert und erreichbar
    ext = settings.external_dir
    if ext.exists() or ext.parent.exists():
        dirs.append(ext)
    else:
        logger.warning(
            "External-Verzeichnis %s nicht erreichbar - wird übersprungen", ext
        )

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        logger.info("Verzeichnis bereit: %s", d)

    # Marker-Dateien anlegen falls noch nicht vorhanden
    for marker_dir in [settings.storage_dir, settings.database_dir]:
        marker = marker_dir / MARKER_FILE
        if not marker.exists():
            marker.write_text(
                "BuecherFreunde Marker - diese Datei nicht löschen!\n"
                "Sie verhindert Datenverlust wenn die Festplatte nicht gemountet ist.\n"
            )
            logger.info("Marker-Datei angelegt: %s", marker)


async def _cleanup_stale_tasks() -> None:
    """Räumt verwaiste Import-Tasks auf die vom letzten Lauf übrig sind."""
    stale = await db.fetch_one(
        "SELECT COUNT(*) as n FROM import_tasks WHERE status IN ('verarbeite', 'wartend')"
    )
    if stale and stale["n"] > 0:
        await db.execute(
            """UPDATE import_tasks SET status = 'fehler',
               error = 'Beim Neustart abgebrochen', updated_at = datetime('now')
               WHERE status = 'verarbeite'"""
        )
        await db.execute(
            "DELETE FROM import_tasks WHERE status = 'wartend'"
        )
        await db.commit()
        logger.info("%d verwaiste Import-Tasks beim Start aufgeräumt", stale["n"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialisierung beim Start, Aufräumen beim Herunterfahren."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S",
    )
    logger.info("BuecherFreunde v%s wird gestartet", settings.version)

    # Sicherheitscheck: Default-Token darf nicht verwendet werden
    if settings.api_token == "bitte-aendern-sicherer-token-hier":
        import secrets
        generated = secrets.token_urlsafe(32)
        logger.critical(
            "SICHERHEITSWARNUNG: Standard-API-Token aktiv! "
            "Bitte API_TOKEN in .env setzen. "
            "Generierter Vorschlag: API_TOKEN=%s", generated
        )

    _check_storage_mount()
    _ensure_directories()
    await db.connect()
    # Verwaiste Tasks aufräumen (vom letzten Lauf übrig geblieben)
    await _cleanup_stale_tasks()
    yield
    await db.disconnect()
    logger.info("BuecherFreunde wird heruntergefahren")


app = FastAPI(
    title="BuecherFreunde",
    version=settings.version,
    description="Selbst gehostete Buchverwaltung",
    lifespan=lifespan,
)

# CORS: Nur lokale Zugriffe erlauben (Backend sitzt hinter nginx)
_cors_origins = [
    f"http://localhost:{settings.external_port}",
    f"http://127.0.0.1:{settings.external_port}",
    "http://localhost",
    "http://127.0.0.1",
]
# Im Docker-Netzwerk kommen Requests vom nginx-Container (kein CORS noetig),
# aber fuer Entwicklung und direkte Zugriffe erlauben wir lokale Origins.

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_router)
app.include_router(authors_router)
app.include_router(backup_router)
app.include_router(books_router)
app.include_router(categories_router)
app.include_router(collections_router)
app.include_router(config_router)
app.include_router(gutenberg_router)
app.include_router(imports_router)
app.include_router(highlights_router)
app.include_router(labels_router)
app.include_router(metadata_router)
app.include_router(notes_router)
app.include_router(search_router)
app.include_router(user_data_router)


@app.get("/api/health")
async def health() -> dict:
    """Health-Check-Endpunkt."""
    return {"status": "ok", "version": settings.version}
