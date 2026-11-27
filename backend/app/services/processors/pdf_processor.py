"""PDF-Verarbeitung mit PyMuPDF (fitz)."""

import logging
from pathlib import Path

import fitz

from backend.app.services.processors.base import BaseProcessor, BookProcessingResult
from backend.app.isbnsuche.kandidaten import beste
from backend.app.services.pdfseite import seitentext

logger = logging.getLogger("buecherfreunde.processor.pdf")


class PdfProcessor(BaseProcessor):
    """Extrahiert Text, Metadaten und Cover aus PDF-Dateien."""

    def process(self, file_path: Path) -> BookProcessingResult:
        result = BookProcessingResult()

        try:
            doc = fitz.open(str(file_path))
        except Exception as e:
            result.error = f"PDF konnte nicht geöffnet werden: {e}"
            logger.error(result.error)
            return result

        try:
            # Metadaten
            meta = doc.metadata or {}
            result.title = meta.get("title", "") or ""
            result.author = meta.get("author", "") or ""
            # Ein PDF kennt keinen Verlag: "producer" und "creator" nennen das Programm, das die Datei erzeugt hat (BF-110)
            result.page_count = len(doc)
            result.metadata_raw = meta

            # Text extrahieren (seitenweise für ISBN-Suche), Ligaturen als Buchstaben (BF-104)
            page_texts = []
            for page in doc:
                page_texts.append(seitentext(page))
            # je Dateiseite ein Teil, getrennt mit Seitenvorschub (Regel in services/seiten.py)
            result.fulltext = "\f".join(t.replace("\f", "\n") for t in page_texts)

            # die ISBN, die im Text am besten zu Titel und Autor passt (BF-111); eine fremde aus der Literaturliste nie
            isbn = beste(page_texts, result.title, result.author)
            if isbn:
                result.isbn = isbn
                logger.info("ISBN aus PDF extrahiert: %s", isbn)

            # Titel aus Dateiname ableiten falls leer
            if not result.title:
                result.title = file_path.stem.replace("_", " ").replace("-", " ")

        except Exception as e:
            result.error = f"Fehler bei PDF-Verarbeitung: {e}"
            logger.error(result.error)
        finally:
            doc.close()

        return result
