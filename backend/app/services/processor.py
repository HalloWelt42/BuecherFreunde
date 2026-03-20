"""Format-Dispatcher fuer Buchverarbeitung."""

import logging
from pathlib import Path

from backend.app.services.processors.base import BaseProcessor, BookProcessingResult
from backend.app.services.processors.epub_processor import EpubProcessor
from backend.app.services.processors.mobi_processor import MobiProcessor
from backend.app.services.processors.pdf_processor import PdfProcessor
from backend.app.services.processors.text_processor import TextProcessor

logger = logging.getLogger("buecherfreunde.processor")

PROCESSORS: dict[str, BaseProcessor] = {
    ".pdf": PdfProcessor(),
    ".epub": EpubProcessor(),
    ".mobi": MobiProcessor(),
    ".txt": TextProcessor(),
    ".md": TextProcessor(),
}


def get_processor(file_path: Path) -> BaseProcessor | None:
    """Gibt den passenden Prozessor fuer das Dateiformat zurueck."""
    suffix = file_path.suffix.lower()
    return PROCESSORS.get(suffix)


def process_book(file_path: Path) -> BookProcessingResult:
    """Verarbeitet eine Buchdatei und gibt das Ergebnis zurueck.

    Erkennt das Format automatisch und delegiert an den passenden Prozessor.
    """
    if not file_path.exists():
        result = BookProcessingResult()
        result.error = f"Datei nicht gefunden: {file_path}"
        return result

    processor = get_processor(file_path)
    if processor is None:
        result = BookProcessingResult()
        result.error = (
            f"Kein Prozessor fuer Format '{file_path.suffix}'. "
            f"Unterstuetzt: {', '.join(sorted(PROCESSORS.keys()))}"
        )
        return result

    logger.info("Verarbeite %s (%s)", file_path.name, file_path.suffix)
    result = processor.process(file_path)

    if result.error:
        logger.warning("Verarbeitung mit Fehler: %s", result.error)
    else:
        logger.info(
            "Verarbeitung erfolgreich: '%s' von '%s' (%d Seiten, %d Zeichen Text)",
            result.title,
            result.author,
            result.page_count,
            len(result.fulltext),
        )

    return result
