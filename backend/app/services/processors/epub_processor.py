"""EPUB-Verarbeitung mit ebooklib und BeautifulSoup."""

import logging
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from backend.app.services.processors.base import BaseProcessor, BookProcessingResult
from backend.app.services.isbn_extractor import extract_isbn_from_fulltext

logger = logging.getLogger("buecherfreunde.processor.epub")


class EpubProcessor(BaseProcessor):
    """Extrahiert Text, Metadaten und Cover aus EPUB-Dateien."""

    def process(self, file_path: Path) -> BookProcessingResult:
        result = BookProcessingResult()

        try:
            book = epub.read_epub(str(file_path), options={"ignore_ncx": True})
        except Exception as e:
            result.error = f"EPUB konnte nicht geöffnet werden: {e}"
            logger.error(result.error)
            return result

        try:
            # Metadaten
            result.title = self._get_metadata(book, "title")
            result.author = self._get_metadata(book, "creator")
            result.publisher = self._get_metadata(book, "publisher")
            result.language = self._get_metadata(book, "language")
            result.description = self._get_metadata(book, "description")

            isbn = self._get_isbn(book)
            if isbn:
                result.isbn = isbn
            # Fallback: ISBN aus Text extrahieren wenn Metadaten leer

            # Text extrahieren
            text_parts = []
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                html_content = item.get_content().decode("utf-8", errors="replace")
                soup = BeautifulSoup(html_content, "html.parser")
                text = soup.get_text(separator="\n", strip=True)
                if text:
                    text_parts.append(text)

            result.fulltext = "\n\n".join(text_parts)
            result.page_count = len(text_parts)

            # Fallback-ISBN aus Volltext wenn Metadaten-ISBN leer
            if not result.isbn and result.fulltext:
                isbn_from_text = extract_isbn_from_fulltext(result.fulltext)
                if isbn_from_text:
                    result.isbn = isbn_from_text
                    logger.info("ISBN aus EPUB-Text extrahiert: %s", isbn_from_text)

            # Cover extrahieren
            result.cover_data = self._extract_cover(book)

            # Titel aus Dateiname ableiten falls leer
            if not result.title:
                result.title = file_path.stem.replace("_", " ").replace("-", " ")

        except Exception as e:
            result.error = f"Fehler bei EPUB-Verarbeitung: {e}"
            logger.error(result.error)

        return result

    def _get_metadata(self, book: epub.EpubBook, field: str) -> str:
        """Liest ein Metadatenfeld aus dem EPUB."""
        try:
            values = book.get_metadata("DC", field)
            if values:
                return str(values[0][0])
        except (IndexError, KeyError):
            pass
        return ""

    def _get_isbn(self, book: epub.EpubBook) -> str:
        """Versucht die ISBN aus den Identifikatoren zu extrahieren."""
        try:
            identifiers = book.get_metadata("DC", "identifier")
            for ident, attrs in identifiers:
                ident_str = str(ident)
                # Direkte ISBN
                clean = ident_str.replace("-", "").replace(" ", "")
                if len(clean) in (10, 13) and clean.replace("X", "").isdigit():
                    return clean
                # Schema-basiert
                scheme = attrs.get("scheme", "").upper()
                if scheme == "ISBN":
                    return clean
        except (IndexError, KeyError, TypeError):
            pass
        return ""

    def _extract_cover(self, book: epub.EpubBook) -> bytes | None:
        """Extrahiert das Cover-Bild aus dem EPUB."""
        # Methode 1: Cover-Image aus Metadaten (ITEM_COVER)
        try:
            cover_items = book.get_items_of_type(ebooklib.ITEM_COVER)
            for item in cover_items:
                data = item.get_content()
                if data and len(data) > 100:
                    return data
        except Exception as e:
            logger.debug("Cover Methode 1 (ITEM_COVER): %s", e)

        # Methode 2: OPF meta cover-Referenz
        try:
            cover_id = None
            for meta in book.get_metadata("OPF", "cover"):
                if isinstance(meta, tuple) and len(meta) > 1:
                    attrs = meta[1] if isinstance(meta[1], dict) else {}
                    cover_id = attrs.get("content", "")
                    if not cover_id and isinstance(meta[0], str):
                        cover_id = meta[0]
                    break
            if cover_id:
                item = book.get_item_with_id(cover_id)
                if item:
                    data = item.get_content()
                    if data and len(data) > 100:
                        return data
        except Exception as e:
            logger.debug("Cover Methode 2 (OPF meta): %s", e)

        # Methode 3: Item mit "cover" im Namen oder ID
        try:
            for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
                name = (item.get_name() or "").lower()
                item_id = (item.id or "").lower()
                if "cover" in name or "cover" in item_id:
                    data = item.get_content()
                    if data and len(data) > 100:
                        return data
        except Exception as e:
            logger.debug("Cover Methode 3 (Name/ID): %s", e)

        # Methode 4: Item mit "cover" im Dateinamen (Pfad)
        try:
            for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
                fname = (item.file_name or "").lower()
                if "cover" in fname or "titel" in fname or "title" in fname:
                    data = item.get_content()
                    if data and len(data) > 100:
                        return data
        except Exception as e:
            logger.debug("Cover Methode 4 (Dateiname): %s", e)

        # Methode 5: Groesstes Bild nehmen (wahrscheinlich Cover)
        try:
            groesstes = None
            groesste_bytes = 0
            for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
                data = item.get_content()
                if data and len(data) > groesste_bytes:
                    groesste_bytes = len(data)
                    groesstes = data
            if groesstes and groesste_bytes > 1000:
                return groesstes
        except Exception as e:
            logger.debug("Cover Methode 5 (groesstes Bild): %s", e)

        return None
