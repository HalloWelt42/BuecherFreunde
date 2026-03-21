"""PDF-Verarbeitung mit PyMuPDF (fitz)."""

import io
import logging
from pathlib import Path

import fitz
from PIL import Image

from backend.app.services.processors.base import BaseProcessor, BookProcessingResult
from backend.app.services.isbn_extractor import extract_isbn_from_pages

logger = logging.getLogger("buecherfreunde.processor.pdf")

MAX_COVER_WIDTH = 800
MAX_COVER_HEIGHT = 1200


class PdfProcessor(BaseProcessor):
    """Extrahiert Text, Metadaten und Cover aus PDF-Dateien."""

    def process(self, file_path: Path) -> BookProcessingResult:
        result = BookProcessingResult()

        try:
            doc = fitz.open(str(file_path))
        except Exception as e:
            result.error = f"PDF konnte nicht geoeffnet werden: {e}"
            logger.error(result.error)
            return result

        try:
            # Metadaten
            meta = doc.metadata or {}
            result.title = meta.get("title", "") or ""
            result.author = meta.get("author", "") or ""
            result.publisher = meta.get("producer", "") or ""
            result.page_count = len(doc)
            result.metadata_raw = meta

            # Text extrahieren (seitenweise fuer ISBN-Suche)
            page_texts = []
            for page in doc:
                text = page.get_text("text")
                page_texts.append(text or "")
            result.fulltext = "\n".join(page_texts)

            # ISBN aus den ersten/letzten Seiten extrahieren
            isbn = extract_isbn_from_pages(page_texts)
            if isbn:
                result.isbn = isbn
                logger.info("ISBN aus PDF extrahiert: %s", isbn)

            # Cover (erste Seite als Bild)
            result.cover_data = self._extract_cover(doc)

            # Titel aus Dateiname ableiten falls leer
            if not result.title:
                result.title = file_path.stem.replace("_", " ").replace("-", " ")

        except Exception as e:
            result.error = f"Fehler bei PDF-Verarbeitung: {e}"
            logger.error(result.error)
        finally:
            doc.close()

        return result

    def _extract_cover(self, doc: fitz.Document) -> bytes | None:
        """Rendert die erste Seite als Cover-Bild."""
        if len(doc) == 0:
            return None

        try:
            page = doc[0]
            # Hohe Aufloesung fuer gute Qualitaet
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=mat)

            # In PIL-Bild konvertieren und skalieren
            img = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

            # Proportional skalieren
            img.thumbnail((MAX_COVER_WIDTH, MAX_COVER_HEIGHT), Image.Resampling.LANCZOS)

            # Als JPEG speichern
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85, optimize=True)
            return buffer.getvalue()

        except Exception as e:
            logger.warning("Cover-Extraktion fehlgeschlagen: %s", e)
            return None
