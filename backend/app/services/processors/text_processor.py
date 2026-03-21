"""Text- und Markdown-Verarbeitung."""

import logging
from pathlib import Path

from backend.app.services.processors.base import BaseProcessor, BookProcessingResult
from backend.app.services.isbn_extractor import extract_isbn_from_fulltext

logger = logging.getLogger("buecherfreunde.processor.text")

MAX_TEXT_SIZE = 50 * 1024 * 1024  # 50 MB


class TextProcessor(BaseProcessor):
    """Verarbeitet .txt und .md Dateien."""

    def process(self, file_path: Path) -> BookProcessingResult:
        result = BookProcessingResult()

        try:
            file_size = file_path.stat().st_size
            if file_size > MAX_TEXT_SIZE:
                result.error = f"Datei zu groß: {file_size / 1024 / 1024:.1f} MB"
                logger.error(result.error)
                return result

            text = file_path.read_text(encoding="utf-8", errors="replace")
            result.fulltext = text
            result.title = file_path.stem.replace("_", " ").replace("-", " ")

            # ISBN aus Text extrahieren
            isbn = extract_isbn_from_fulltext(text)
            if isbn:
                result.isbn = isbn
                logger.info("ISBN aus Text extrahiert: %s", isbn)

            # Zeilenanzahl als Seitennäherung (ca. 40 Zeilen pro Seite)
            lines = text.count("\n") + 1
            result.page_count = max(1, lines // 40)

            # Erste Zeile als Titel wenn Markdown-Überschrift
            if file_path.suffix.lower() == ".md":
                for line in text.split("\n"):
                    line = line.strip()
                    if line.startswith("# "):
                        result.title = line[2:].strip()
                        break

        except Exception as e:
            result.error = f"Fehler bei Text-Verarbeitung: {e}"
            logger.error(result.error)

        return result
