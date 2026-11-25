"""BuecherFreunde Backend - FastAPI Hauptanwendung."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from backend.app.ablage import orte
from backend.app.ablage.wolke import wolke
from backend.app.annahme import eingangsordner
from backend.app.annahme.dienst import annahme
from backend.app.api.ai import router as ai_router
from backend.app.api.annahme import router as annahme_router
from backend.app.api.auth import router as auth_router
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
from backend.app.api.fundus import router as fundus_router
from backend.app.api.highlights import router as highlights_router
from backend.app.api.labels import router as labels_router
from backend.app.api.neubau import router as neubau_router
from backend.app.api.notes import router as notes_router
from backend.app.api.user_data import router as user_data_router
from backend.app.api.vorlesen import router as vorlesen_router
from backend.app.api.wartung import router as wartung_router
from backend.app.core.anmeldung import eigener_zugang, schliessen as anmeldung_schliessen
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services import bedeutung, pflege, vorlesen

logger = logging.getLogger("buecherfreunde")


def _ensure_directories() -> None:
    """Erstellt alle benötigten Verzeichnisse beim Start."""
    dirs = [
        settings.storage_dir,
        settings.import_dir,
        settings.database_dir,
        settings.backup_dir,
    ]
    # Die externe Sammlung gehört der App nicht: nur benutzen, wenn es sie gibt, nie anlegen
    if not settings.external_dir.exists():
        logger.info("Keine externe Sammlung unter %s", settings.external_dir)

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        logger.info("Verzeichnis bereit: %s", d)


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

    orte.einrichten()
    if settings.kellerwolke_url and not await eigener_zugang.erfragen():
        logger.warning("Kein App-Zugang der Kellerwolke: Anmelden geht erst nach der Einrichtung "
                       "(KELLERWOLKE_URL, KELLERWOLKE_SCHLUESSEL_DATEI)")
    _ensure_directories()
    await db.connect()
    annahme.starten()
    im_hintergrund = [asyncio.create_task(pflege.laufen()), asyncio.create_task(eingangsordner.laufen())]
    # Verwaiste Tasks aufräumen (vom letzten Lauf übrig geblieben)
    await _cleanup_stale_tasks()
    yield
    for lauf in im_hintergrund:
        lauf.cancel()
    await annahme.stoppen()
    await bedeutung.schliessen()
    await vorlesen.schliessen()
    await wolke.schliessen()
    await anmeldung_schliessen()
    await db.disconnect()
    logger.info("BuecherFreunde wird heruntergefahren")


app = FastAPI(
    title="BuecherFreunde",
    version=settings.version,
    description="Selbst gehostete Buchverwaltung",
    lifespan=lifespan,
)

# Keine Freigabe für fremde Seiten: Oberfläche und Schnittstelle kommen von derselben Adresse (nginx davor).
app.include_router(neubau_router)
app.include_router(annahme_router)
app.include_router(ai_router)
app.include_router(auth_router)
app.include_router(authors_router)
app.include_router(backup_router)
app.include_router(books_router)
app.include_router(categories_router)
app.include_router(collections_router)
app.include_router(config_router)
app.include_router(fundus_router)
app.include_router(gutenberg_router)
app.include_router(imports_router)
app.include_router(highlights_router)
app.include_router(labels_router)
app.include_router(metadata_router)
app.include_router(notes_router)
app.include_router(search_router)
app.include_router(user_data_router)
app.include_router(wartung_router)
app.include_router(vorlesen_router)


@app.get("/api/health")
async def health() -> dict:
    """Health-Check-Endpunkt."""
    return {"status": "ok", "version": settings.version}
