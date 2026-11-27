"""EPUB-Verarbeitung mit ebooklib und BeautifulSoup."""

import logging
import re
from datetime import date
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from backend.app.services.processors.base import BaseProcessor, BookProcessingResult
from backend.app.isbnsuche.kandidaten import beste

logger = logging.getLogger("buecherfreunde.processor.epub")
_JAHR = re.compile(r"\b(1[5-9]\d\d|2\d\d\d)\b")


def erscheinungsjahr(datum: str) -> int | None:
    """Das Jahr aus dc:date ("2019", "2019-03-01T00:00:00Z"); None ohne oder mit einem Jahr in der Zukunft."""
    m = _JAHR.search(datum or "")
    return int(m.group(1)) if m and int(m.group(1)) <= date.today().year + 1 else None


class EpubProcessor(BaseProcessor):
    """Extrahiert Text, Metadaten und Cover aus EPUB-Dateien."""

    def process(self, file_path: Path) -> BookProcessingResult:
        result = BookProcessingResult()

        book = None
        try:
            book = epub.read_epub(str(file_path), options={"ignore_ncx": True})
        except Exception as e:
            logger.warning("ebooklib konnte EPUB nicht vollstaendig lesen: %s", e)

        if book:
            try:
                # Metadaten
                result.title = self._get_metadata(book, "title")
                result.author = self._get_metadata(book, "creator")
                result.publisher = self._get_metadata(book, "publisher")
                result.language = self._get_metadata(book, "language")
                result.description = self._get_metadata(book, "description")
                result.year = erscheinungsjahr(self._get_metadata(book, "date"))

                isbn = self._get_isbn(book)
                if isbn:
                    result.isbn = isbn

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

                # ohne ISBN in den Metadaten die aus dem Text, die am besten zum Buch passt (BF-111), je Dokument eine Seite
                if not result.isbn and result.fulltext:
                    isbn_from_text = beste(text_parts, result.title, result.author)
                    if isbn_from_text:
                        result.isbn = isbn_from_text
                        logger.info("ISBN aus EPUB-Text extrahiert: %s", isbn_from_text)

            except Exception as e:
                logger.warning("Fehler bei EPUB-Verarbeitung via ebooklib: %s", e)


        # ZIP-Fallback fuer Metadaten wenn ebooklib gescheitert
        if not book and not result.title:
            self._extract_metadata_from_zip(file_path, result)

        if not book and not result.fulltext:
            result.error = result.error or "EPUB konnte nicht geöffnet werden"

        # Titel aus Dateiname ableiten falls immer noch leer
        if not result.title:
            result.title = file_path.stem.replace("_", " ").replace("-", " ")

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

    @staticmethod
    def _extract_metadata_from_zip(file_path: Path, result) -> None:
        """Extrahiert Metadaten direkt aus der OPF-Datei per zipfile."""
        import zipfile
        import re

        try:
            with zipfile.ZipFile(file_path) as zf:
                # OPF-Datei finden
                opf_file = None
                for name in zf.namelist():
                    if name.lower().endswith(".opf"):
                        opf_file = name
                        break

                if not opf_file:
                    return

                opf_content = zf.read(opf_file).decode("utf-8", errors="ignore")

                # Einfache Regex-Extraktion aus OPF
                def _extract_tag(tag):
                    m = re.search(rf"<dc:{tag}[^>]*>([^<]+)</dc:{tag}>", opf_content, re.IGNORECASE)
                    return m.group(1).strip() if m else ""

                result.title = result.title or _extract_tag("title")
                result.author = result.author or _extract_tag("creator")
                result.publisher = result.publisher or _extract_tag("publisher")
                result.language = result.language or _extract_tag("language")
                result.description = result.description or _extract_tag("description")

                # ISBN aus dc:identifier extrahieren
                if not result.isbn:
                    isbn_pattern = re.compile(
                        r"<dc:identifier[^>]*>(?:(?:urn:isbn:)?|(?:ISBN[:\s]?)?)(\d[\d\-]{8,16}\d)</dc:identifier>",
                        re.IGNORECASE
                    )
                    for m in isbn_pattern.finditer(opf_content):
                        candidate = m.group(1).replace("-", "")
                        if len(candidate) in (10, 13):
                            result.isbn = candidate
                            logger.info("ZIP-Fallback ISBN aus OPF: %s", candidate)
                            break

                # ISBN aus HTML-Seiten extrahieren (steht oft im Impressum)
                if not result.isbn:
                    isbn_text_pattern = re.compile(
                        r"ISBN[\s:]*(\d[\d\-\s]{8,16}\d)", re.IGNORECASE
                    )
                    html_files = sorted([n for n in zf.namelist() if n.lower().endswith((".html", ".xhtml", ".htm"))])
                    # Nur die ersten paar Seiten durchsuchen (Impressum ist vorne)
                    for html_name in html_files[:10]:
                        try:
                            html_content = zf.read(html_name).decode("utf-8", errors="ignore")
                            for m in isbn_text_pattern.finditer(html_content):
                                candidate = re.sub(r"[\-\s]", "", m.group(1))
                                if len(candidate) in (10, 13):
                                    result.isbn = candidate
                                    logger.info("ZIP-Fallback ISBN aus Text (%s): %s", html_name, candidate)
                                    break
                        except Exception:
                            continue
                        if result.isbn:
                            break

                # Volltext aus HTML extrahieren wenn noch leer
                if not result.fulltext:
                    text_parts = []
                    html_files = sorted([n for n in zf.namelist() if n.lower().endswith((".html", ".xhtml", ".htm"))])
                    for html_name in html_files:
                        try:
                            html_content = zf.read(html_name).decode("utf-8", errors="ignore")
                            soup = BeautifulSoup(html_content, "html.parser")
                            text = soup.get_text(separator="\n", strip=True)
                            if text:
                                text_parts.append(text)
                        except Exception:
                            continue
                    if text_parts:
                        result.fulltext = "\n\n".join(text_parts)
                        result.page_count = len(text_parts)
                        logger.info("ZIP-Fallback Volltext: %d Seiten extrahiert", len(text_parts))

                if result.title:
                    logger.info("ZIP-Fallback Metadaten: Titel=%s, Autor=%s", result.title, result.author)

        except Exception as e:
            logger.warning("ZIP-Fallback Metadaten fehlgeschlagen: %s", e)
