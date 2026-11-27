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
from backend.app.annahme.ki_vorschau import ki_vorschau
from backend.app.api.ai import router as ai_router
from backend.app.api.ausfuehren import router as ausfuehren_router
from backend.app.api.annahme import router as annahme_router
from backend.app.api.auth import router as auth_router
from backend.app.api.authors import router as authors_router
from backend.app.api.backup import router as backup_router
from backend.app.api.books import router as books_router
from backend.app.api.categories import router as categories_router
from backend.app.api.config import router as config_router
from backend.app.api.einordnung import router as einordnung_router
from backend.app.api.einrichtung import kellerwolke_router, router as einrichtung_router, umzug_router
from backend.app.api.familie import router as familie_router
from backend.app.api.katalog import router as katalog_router
from backend.app.api.gutenberg import router as gutenberg_router
from backend.app.api.imports import router as imports_router
from backend.app.api.metadata import router as metadata_router
from backend.app.api.search import router as search_router
from backend.app.api.collections import router as collections_router
from backend.app.api.fundus import router as fundus_router
from backend.app.api.helfer import router as helfer_router
from backend.app.api.highlights import router as highlights_router
from backend.app.api.labels import router as labels_router
from backend.app.api.luecken import router as luecken_router
from backend.app.api.material import router as material_router, stand_router as material_stand_router
from backend.app.api.neubau import router as neubau_router
from backend.app.api.notes import router as notes_router
from backend.app.api.uebersetzung import router as uebersetzung_router
from backend.app.api.user_data import router as user_data_router
from backend.app.api.vorlesen import router as vorlesen_router
from backend.app.api.wartung import router as wartung_router
from backend.app.core.anmeldung import eigener_zugang, schliessen as anmeldung_schliessen
from backend.app.core.config import settings
from backend.app.core import fehlerantworten
from backend.app.core.einheiten import Einheiten
from backend.app.core.database import db
from backend.app.familie.ansagelauf import ansagelauf
from backend.app.codestellen.dienst import codestellen
from backend.app.einrichtung import anschluesse as einrichtung_anschluesse, zustand as einrichtung_zustand
from backend.app.einrichtung.auftrag import auftraege as einrichtung_auftraege
from backend.app.einrichtung.nachfuehren import nachfuehren
from backend.app.codestellen.vorpruefung import vorpruefer
from backend.app.services import bedeutung, gespraech, nachschlagen, pflege
from backend.app.services.ausfuehren import sandbox
from backend.app.katalog.bestandslauf import bestandslauf
from backend.app.katalog.kategorien import anleitung_nachziehen
from backend.app.luecken.nachschlagen import nachschlagen as luecken_nachschlagen
from backend.app.material.erkennen import abgleich as material_abgleich
from backend.app.material.textlauf import textlauf as material_textlauf
from backend.app.katalog.einordnen import einordner as katalog_einordner
from backend.app.services.einordnung import einordner
from backend.app.services.ki import ki
from backend.app.vorlesen import zugang as vertonung
from backend.app.services.sammlungsfinder import sammlungsfinder
from backend.app.services.begriffsliste import vorgaben_einspielen
from backend.app.services.uebersetzungslauf import uebersetzungslauf
from backend.app.services.umschlagpruefung import umschlagpruefung

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialisierung beim Start, Aufräumen beim Herunterfahren."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S",
    )
    logger.info("BuecherFreunde v%s wird gestartet", settings.version)

    neu = orte.einrichten()                           # leerer Bestand ohne Markerdatei: die Ersteinrichtung erscheint (BF-82)
    _ensure_directories()
    await db.connect()
    await einrichtung_zustand.erkennen(neu)
    await einrichtung_anschluesse.anwenden()          # Adressen, die in der App eingetragen sind, gelten vor der .env (BF-82)
    if settings.kellerwolke_url and not await eigener_zugang.erfragen():
        logger.warning("Kein App-Zugang der Kellerwolke: Anmelden geht erst nach der Einrichtung "
                       "(KELLERWOLKE_URL, KELLERWOLKE_SCHLUESSEL_DATEI oder Ersteinrichtung)")
    await ki.wahl_laden()
    await anleitung_nachziehen()                      # einmal je Bestand: die Anleitung als Art neben dem Dokument (BF-80)
    annahme.starten()
    ki_vorschau.starten()                             # die KI ergänzt wartende Vorschauen, auch nach einem Neustart (BF-80)
    material_textlauf.starten()                       # lesbares Begleitmaterial in die Suche (BF-81)
    material_abgleich.starten()                       # Dateien neben den Originalen als Material anbieten (BF-81)
    codestellen.erkannt.append(vorpruefer.nach_erkennung)
    codestellen.starten()
    vorpruefer.starten()
    umschlagpruefung.nach_runde.append(einordner.anstossen)
    umschlagpruefung.starten()
    einordner.starten()
    await katalog_einordner.nach_neustart()           # ein laufendes Einordnen geht am letzten fertigen Stapel weiter
    await bestandslauf.nach_neustart()
    await vorgaben_einspielen()
    uebersetzungslauf.starten()
    ansagelauf.starten()                              # Ansagen erstellen: was fehlt, auch nach einem Neustart (BF-78)
    luecken_nachschlagen.starten()                    # Lücken nachschlagen: je Sammlung und Sprache einmal, mit dem Offenen weiter (BF-75)
    await nachfuehren.beim_start()
    nachfuehren.starten()                             # Persönliches im Auszug laufend nachführen (BF-82)
    for auftrag in einrichtung_auftraege().values():  # Prüfung, Neuaufbau, Kopieren gehen nach einem Neustart weiter (BF-82)
        await auftrag.nach_neustart()
    im_hintergrund = [asyncio.create_task(pflege.laufen()), asyncio.create_task(eingangsordner.laufen()), asyncio.create_task(nachschlagen.vorwaermen())]
    yield
    for lauf in im_hintergrund:
        lauf.cancel()
    await annahme.stoppen()
    await ki_vorschau.stoppen()
    await material_textlauf.stoppen()
    await material_abgleich.stoppen()
    await vorpruefer.stoppen()
    await einordner.stoppen()
    await katalog_einordner.stoppen()
    await bestandslauf.stoppen()
    await uebersetzungslauf.stoppen()
    await ansagelauf.stoppen()
    await luecken_nachschlagen.stoppen()
    await nachfuehren.stoppen()
    for auftrag in einrichtung_auftraege().values():
        await auftrag.stoppen()
    await sammlungsfinder.stoppen()
    await umschlagpruefung.stoppen()
    await codestellen.stoppen()
    await sandbox.schliessen()
    await ki.schliessen()
    await bedeutung.schliessen()
    await nachschlagen.schliessen()
    await gespraech.dienst.schliessen()
    await vertonung.verbund.schliessen()
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
app.add_middleware(Einheiten)                   # jede Anfrage eine Transaktion (BF-49)
fehlerantworten.einrichten(app)                 # eine Form für Fehler, deutsch (BF-50)

# Keine Freigabe für fremde Seiten: Oberfläche und Schnittstelle kommen von derselben Adresse (nginx davor).
app.include_router(neubau_router)
app.include_router(annahme_router)
app.include_router(ai_router)
app.include_router(ausfuehren_router)
app.include_router(auth_router)
app.include_router(authors_router)
app.include_router(backup_router)
app.include_router(books_router)
app.include_router(categories_router)
app.include_router(collections_router)
app.include_router(config_router)
app.include_router(einordnung_router)
app.include_router(einrichtung_router)
app.include_router(umzug_router)
app.include_router(kellerwolke_router)
app.include_router(familie_router)
app.include_router(katalog_router)
app.include_router(fundus_router)
app.include_router(gutenberg_router)
app.include_router(helfer_router)
app.include_router(imports_router)
app.include_router(highlights_router)
app.include_router(labels_router)
app.include_router(luecken_router)
app.include_router(material_router)
app.include_router(material_stand_router)
app.include_router(metadata_router)
app.include_router(notes_router)
app.include_router(search_router)
app.include_router(uebersetzung_router)
app.include_router(user_data_router)
app.include_router(wartung_router)
app.include_router(vorlesen_router)


@app.get("/api/health")
async def health() -> dict:
    """Health-Check-Endpunkt."""
    return {"status": "ok", "version": settings.version}
