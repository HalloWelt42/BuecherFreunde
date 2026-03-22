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

                # Fallback-ISBN aus Volltext wenn Metadaten-ISBN leer
                if not result.isbn and result.fulltext:
                    isbn_from_text = extract_isbn_from_fulltext(result.fulltext)
                    if isbn_from_text:
                        result.isbn = isbn_from_text
                        logger.info("ISBN aus EPUB-Text extrahiert: %s", isbn_from_text)

                # Cover extrahieren
                result.cover_data = self._extract_cover(book)

            except Exception as e:
                logger.warning("Fehler bei EPUB-Verarbeitung via ebooklib: %s", e)

        # ZIP-Fallback fuer Cover wenn ebooklib gescheitert oder kein Cover gefunden
        if not result.cover_data:
            result.cover_data = self._extract_cover_from_zip(file_path)

        # ZIP-Fallback fuer Metadaten wenn ebooklib gescheitert
        if not book and not result.title:
            self._extract_metadata_from_zip(file_path, result)

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

        # Methode 6: Alle Items durchsuchen (ebooklib erkennt nicht alle Bilder als ITEM_IMAGE)
        try:
            _IMAGE_MAGIC = (
                b"\xff\xd8\xff",      # JPEG
                b"\x89PNG",           # PNG
                b"GIF8",             # GIF
                b"RIFF",             # WebP
            )
            groesstes = None
            groesste_bytes = 0
            for item in book.get_items():
                data = item.get_content()
                if not data or len(data) < 500:
                    continue
                if any(data.startswith(magic) for magic in _IMAGE_MAGIC):
                    name = (getattr(item, "file_name", "") or "").lower()
                    item_id = (getattr(item, "id", "") or "").lower()
                    # Cover-Kandidat priorisieren
                    if "cover" in name or "cover" in item_id:
                        return data
                    if len(data) > groesste_bytes:
                        groesste_bytes = len(data)
                        groesstes = data
            if groesstes and groesste_bytes > 1000:
                return groesstes
        except Exception as e:
            logger.debug("Cover Methode 6 (alle Items Magic Bytes): %s", e)

        # Methode 7: Cover aus XHTML-Seiten extrahieren (base64-eingebettete Bilder)
        try:
            import base64
            import re
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                content = item.get_content().decode("utf-8", errors="ignore")
                # Nur in Seiten suchen die "cover" im Namen oder Inhalt haben
                name = (getattr(item, "file_name", "") or "").lower()
                if "cover" not in name and "cover" not in content[:500].lower():
                    continue
                # Base64-Bilder suchen
                matches = re.findall(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', content)
                for match in matches:
                    data = base64.b64decode(match)
                    if len(data) > 1000:
                        return data
        except Exception as e:
            logger.debug("Cover Methode 7 (base64 in XHTML): %s", e)

        return None

    @staticmethod
    def _extract_cover_from_zip(file_path: Path) -> bytes | None:
        """Extrahiert Cover direkt per zipfile -- Fallback fuer kaputte EPUBs."""
        import zipfile

        _IMG_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

        try:
            with zipfile.ZipFile(file_path) as zf:
                namen = zf.namelist()

                # 1. Datei mit "cover" im Namen
                for name in namen:
                    lower = name.lower()
                    if "cover" in lower and any(lower.endswith(e) for e in _IMG_EXT):
                        data = zf.read(name)
                        if data and len(data) > 500:
                            logger.info("ZIP-Fallback Cover: %s (%d Bytes)", name, len(data))
                            return data

                # 2. Groesstes Bild
                groesstes = None
                groesste_bytes = 0
                for name in namen:
                    lower = name.lower()
                    if any(lower.endswith(e) for e in _IMG_EXT):
                        data = zf.read(name)
                        if data and len(data) > groesste_bytes:
                            groesste_bytes = len(data)
                            groesstes = data

                if groesstes and groesste_bytes > 1000:
                    return groesstes

        except Exception as e:
            logger.warning("ZIP-Fallback Cover fehlgeschlagen: %s", e)

        return None

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

                if result.title:
                    logger.info("ZIP-Fallback Metadaten: Titel=%s, Autor=%s", result.title, result.author)

        except Exception as e:
            logger.warning("ZIP-Fallback Metadaten fehlgeschlagen: %s", e)
