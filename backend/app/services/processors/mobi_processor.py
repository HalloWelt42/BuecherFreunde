"""MOBI-Verarbeitung mit mobi-Bibliothek."""

import logging
import tempfile
from pathlib import Path

from backend.app.services.processors.base import BaseProcessor, BookProcessingResult
from backend.app.services.isbn_extractor import extract_isbn_from_fulltext

logger = logging.getLogger("buecherfreunde.processor.mobi")


class MobiProcessor(BaseProcessor):
    """Extrahiert Text und Metadaten aus MOBI-Dateien."""

    def process(self, file_path: Path) -> BookProcessingResult:
        result = BookProcessingResult()

        try:
            import mobi

            with tempfile.TemporaryDirectory() as tmpdir:
                # mobi entpackt in ein Verzeichnis
                tempdir, extracted = mobi.extract(str(file_path))

                # Extrahierten HTML-Text lesen
                extracted_path = Path(extracted) if extracted else None
                if extracted_path and extracted_path.exists():
                    try:
                        from bs4 import BeautifulSoup

                        html = extracted_path.read_text(
                            encoding="utf-8", errors="replace"
                        )
                        soup = BeautifulSoup(html, "html.parser")

                        # Titel aus HTML
                        title_tag = soup.find("title")
                        if title_tag:
                            result.title = title_tag.get_text(strip=True)

                        # Text extrahieren
                        result.fulltext = soup.get_text(separator="\n", strip=True)
                    except Exception as e:
                        logger.warning("HTML-Verarbeitung fehlgeschlagen: %s", e)

                # ISBN aus Volltext extrahieren
                if result.fulltext:
                    isbn = extract_isbn_from_fulltext(result.fulltext)
                    if isbn:
                        result.isbn = isbn
                        logger.info("ISBN aus MOBI-Text extrahiert: %s", isbn)

                # Metadaten aus dem Pfadnamen ableiten falls noetig
                if not result.title:
                    result.title = file_path.stem.replace("_", " ").replace("-", " ")

        except ImportError:
            result.error = "mobi-Bibliothek nicht installiert"
            logger.error(result.error)
        except Exception as e:
            result.error = f"Fehler bei MOBI-Verarbeitung: {e}"
            logger.error(result.error)

        return result
