"""BuecherFreunde Backend - FastAPI Hauptanwendung."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.books import router as books_router
from backend.app.api.categories import router as categories_router
from backend.app.api.config import router as config_router
from backend.app.api.tags import router as tags_router
from backend.app.core.config import settings
from backend.app.core.database import db

logger = logging.getLogger("buecherfreunde")


def _ensure_directories() -> None:
    """Erstellt alle benoetigten Verzeichnisse beim Start."""
    dirs = [
        settings.storage_dir,
        settings.external_dir,
        settings.import_dir,
        settings.database_dir,
        settings.backup_dir,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        logger.info("Verzeichnis bereit: %s", d)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialisierung beim Start, Aufraeuemen beim Herunterfahren."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S",
    )
    logger.info("BuecherFreunde v%s wird gestartet", settings.version)
    _ensure_directories()
    await db.connect()
    yield
    await db.disconnect()
    logger.info("BuecherFreunde wird heruntergefahren")


app = FastAPI(
    title="BuecherFreunde",
    version=settings.version,
    description="Selbst gehostete Buchverwaltung",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books_router)
app.include_router(categories_router)
app.include_router(config_router)
app.include_router(tags_router)


@app.get("/api/health")
async def health() -> dict:
    """Health-Check-Endpunkt."""
    return {"status": "ok", "version": settings.version}
