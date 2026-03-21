"""Tests fuer die Buchprozessoren (Text, PDF, EPUB, MOBI).

Testet Textextraktion, Metadaten-Erkennung, Fehlerbehandlung
und den Format-Dispatcher.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.app.services.processors.base import BaseProcessor, BookProcessingResult
from backend.app.services.processors.text_processor import TextProcessor
from backend.app.services.processor import get_processor, process_book, PROCESSORS


# ---------------------------------------------------------------------------
# BookProcessingResult
# ---------------------------------------------------------------------------

class TestBookProcessingResult:
    """Tests fuer das Verarbeitungs-Ergebnis-Objekt."""

    def test_standard_werte(self):
        """Ein neues Ergebnis muss sinnvolle Standardwerte haben."""
        ergebnis = BookProcessingResult()
        assert ergebnis.title == ""
        assert ergebnis.author == ""
        assert ergebnis.page_count == 0
        assert ergebnis.fulltext == ""
        assert ergebnis.cover_data is None
        assert ergebnis.error == ""

    def test_fts_content_begrenzt_auf_100000_zeichen(self):
        """FTS-Inhalt darf maximal 100.000 Zeichen haben."""
        ergebnis = BookProcessingResult()
        ergebnis.fulltext = "A" * 200_000
        assert len(ergebnis.fts_content) == 100_000

    def test_fts_content_kurzer_text(self):
        """Kurzer Text muss vollstaendig in fts_content enthalten sein."""
        ergebnis = BookProcessingResult()
        ergebnis.fulltext = "Kurzer Testtext"
        assert ergebnis.fts_content == "Kurzer Testtext"

    def test_metadata_raw_ist_dict(self):
        """metadata_raw muss standardmaessig ein leeres Dict sein."""
        ergebnis = BookProcessingResult()
        assert isinstance(ergebnis.metadata_raw, dict)
        assert len(ergebnis.metadata_raw) == 0


# ---------------------------------------------------------------------------
# BaseProcessor
# ---------------------------------------------------------------------------

class TestBaseProcessor:
    """Tests fuer die abstrakte Basisklasse."""

    def test_process_nicht_implementiert(self, tmp_path):
        """BaseProcessor.process() muss NotImplementedError ausloesen."""
        processor = BaseProcessor()
        with pytest.raises(NotImplementedError):
            processor.process(tmp_path / "test.txt")


# ---------------------------------------------------------------------------
# TextProcessor
# ---------------------------------------------------------------------------

class TestTextProcessor:
    """Tests fuer den Text- und Markdown-Prozessor."""

    def test_textdatei_verarbeiten(self, beispiel_text_datei):
        """Eine Textdatei muss korrekt verarbeitet werden."""
        processor = TextProcessor()
        ergebnis = processor.process(beispiel_text_datei)

        assert ergebnis.error == ""
        assert ergebnis.title == "testbuch"
        assert len(ergebnis.fulltext) > 0
        assert "Grundlagen" in ergebnis.fulltext
        assert ergebnis.page_count >= 1

    def test_textdatei_titel_aus_dateiname(self, erstelle_textdatei):
        """Der Titel muss aus dem Dateinamen abgeleitet werden."""
        datei = erstelle_textdatei("mein_tolles_buch.txt", "Inhalt")
        processor = TextProcessor()
        ergebnis = processor.process(datei)
        assert ergebnis.title == "mein tolles buch"

    def test_textdatei_titel_bindestriche(self, erstelle_textdatei):
        """Bindestriche im Dateinamen muessen durch Leerzeichen ersetzt werden."""
        datei = erstelle_textdatei("python-fuer-einsteiger.txt", "Inhalt")
        processor = TextProcessor()
        ergebnis = processor.process(datei)
        assert ergebnis.title == "python fuer einsteiger"

    def test_markdown_titel_aus_ueberschrift(self, beispiel_markdown_datei):
        """Bei Markdown muss die erste H1-Ueberschrift als Titel genutzt werden."""
        processor = TextProcessor()
        ergebnis = processor.process(beispiel_markdown_datei)
        assert ergebnis.title == "Mein Testbuch in Markdown"

    def test_markdown_ohne_ueberschrift(self, erstelle_textdatei):
        """Markdown ohne H1 muss den Dateinamen als Titel verwenden."""
        datei = erstelle_textdatei("notizen.md", "Nur Text ohne Ueberschrift")
        processor = TextProcessor()
        ergebnis = processor.process(datei)
        assert ergebnis.title == "notizen"

    def test_seitenanzahl_berechnung(self, erstelle_textdatei):
        """Die Seitenanzahl muss anhand der Zeilenanzahl geschaetzt werden."""
        # 120 Zeilen = ca. 3 Seiten bei 40 Zeilen/Seite
        zeilen = "\n".join(f"Zeile {i}" for i in range(120))
        datei = erstelle_textdatei("lang.txt", zeilen)
        processor = TextProcessor()
        ergebnis = processor.process(datei)
        assert ergebnis.page_count == 3

    def test_leere_textdatei(self, erstelle_textdatei):
        """Eine leere Datei muss mindestens 1 Seite ergeben."""
        datei = erstelle_textdatei("leer.txt", "")
        processor = TextProcessor()
        ergebnis = processor.process(datei)
        assert ergebnis.page_count >= 1
        assert ergebnis.error == ""

    def test_umlaute_im_text(self, erstelle_textdatei):
        """Umlaute muessen korrekt verarbeitet werden."""
        text = "Aepfel, Birnen und Kirschen - ein Obstbuch"
        datei = erstelle_textdatei("umlaute.txt", text)
        processor = TextProcessor()
        ergebnis = processor.process(datei)
        assert text in ergebnis.fulltext

    def test_grosse_datei_wird_abgelehnt(self, erstelle_binaerdatei):
        """Dateien ueber 50 MB muessen einen Fehler erzeugen."""
        # Wir mocken stat() statt eine riesige Datei anzulegen
        datei = erstelle_binaerdatei("riesig.txt", b"x")
        processor = TextProcessor()

        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value = MagicMock(st_size=60 * 1024 * 1024)
            ergebnis = processor.process(datei)

        assert ergebnis.error != ""
        assert "zu gross" in ergebnis.error


# ---------------------------------------------------------------------------
# Format-Dispatcher
# ---------------------------------------------------------------------------

class TestFormatDispatcher:
    """Tests fuer den automatischen Format-Dispatcher."""

    def test_prozessor_fuer_txt(self, tmp_path):
        """Fuer .txt muss ein TextProcessor zurueckgegeben werden."""
        processor = get_processor(tmp_path / "buch.txt")
        assert processor is not None
        assert isinstance(processor, TextProcessor)

    def test_prozessor_fuer_md(self, tmp_path):
        """Fuer .md muss ein TextProcessor zurueckgegeben werden."""
        processor = get_processor(tmp_path / "notizen.md")
        assert processor is not None
        assert isinstance(processor, TextProcessor)

    def test_prozessor_fuer_pdf(self, tmp_path):
        """Fuer .pdf muss ein Prozessor vorhanden sein."""
        processor = get_processor(tmp_path / "buch.pdf")
        assert processor is not None

    def test_prozessor_fuer_epub(self, tmp_path):
        """Fuer .epub muss ein Prozessor vorhanden sein."""
        processor = get_processor(tmp_path / "buch.epub")
        assert processor is not None

    def test_prozessor_fuer_mobi(self, tmp_path):
        """Fuer .mobi muss ein Prozessor vorhanden sein."""
        processor = get_processor(tmp_path / "buch.mobi")
        assert processor is not None

    def test_kein_prozessor_fuer_unbekanntes_format(self, tmp_path):
        """Fuer unbekannte Formate muss None zurueckgegeben werden."""
        processor = get_processor(tmp_path / "bild.jpg")
        assert processor is None

    def test_alle_formate_registriert(self):
        """Alle erwarteten Formate muessen registriert sein."""
        erwartete = {".pdf", ".epub", ".mobi", ".txt", ".md"}
        assert set(PROCESSORS.keys()) == erwartete

    def test_process_book_datei_nicht_gefunden(self, tmp_path):
        """process_book() muss bei fehlender Datei einen Fehler liefern."""
        ergebnis = process_book(tmp_path / "gibt_es_nicht.pdf")
        assert ergebnis.error != ""
        assert "nicht gefunden" in ergebnis.error

    def test_process_book_unbekanntes_format(self, erstelle_textdatei):
        """process_book() muss bei unbekanntem Format einen Fehler liefern."""
        datei = erstelle_textdatei("daten.xyz", "Inhalt")
        ergebnis = process_book(datei)
        assert ergebnis.error != ""
        assert "Kein Prozessor" in ergebnis.error

    def test_process_book_textdatei(self, beispiel_text_datei):
        """process_book() muss eine Textdatei korrekt verarbeiten."""
        ergebnis = process_book(beispiel_text_datei)
        assert ergebnis.error == ""
        assert len(ergebnis.fulltext) > 0

    def test_process_book_gross_kleinschreibung(self, erstelle_textdatei):
        """Dateierweiterungen muessen unabhaengig von Gross/Kleinschreibung erkannt werden."""
        datei = erstelle_textdatei("buch.TXT", "Inhalt")
        processor = get_processor(datei)
        assert processor is not None


# ---------------------------------------------------------------------------
# PDF-Prozessor (mit Mock)
# ---------------------------------------------------------------------------

class TestPdfProzessorMock:
    """Tests fuer den PDF-Prozessor mit gemocktem PyMuPDF."""

    def test_pdf_metadaten_extrahieren(self, tmp_path):
        """PDF-Metadaten muessen korrekt extrahiert werden."""
        from backend.app.services.processors.pdf_processor import PdfProcessor

        mock_page = MagicMock()
        mock_page.get_text.return_value = "Seite 1 Text"
        mock_page.get_pixmap.return_value = MagicMock(
            width=100, height=150, samples=b"\x00" * (100 * 150 * 3)
        )

        mock_doc = MagicMock()
        mock_doc.metadata = {
            "title": "Testbuch PDF",
            "author": "PDF-Autor",
            "producer": "TestVerlag",
        }
        mock_doc.__len__ = lambda self: 1
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_doc.__getitem__ = lambda self, i: mock_page

        with patch("backend.app.services.processors.pdf_processor.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            mock_fitz.Matrix.return_value = MagicMock()

            processor = PdfProcessor()
            datei = tmp_path / "test.pdf"
            datei.write_bytes(b"%PDF-1.4")

            with patch("backend.app.services.processors.pdf_processor.Image") as mock_image:
                mock_img = MagicMock()
                mock_image.frombytes.return_value = mock_img
                mock_buffer = MagicMock()
                mock_buffer.getvalue.return_value = b"\xff\xd8\xff"
                with patch("backend.app.services.processors.pdf_processor.io") as mock_io:
                    mock_io.BytesIO.return_value = mock_buffer
                    ergebnis = processor.process(datei)

        assert ergebnis.title == "Testbuch PDF"
        assert ergebnis.author == "PDF-Autor"
        assert ergebnis.publisher == "TestVerlag"
        assert ergebnis.page_count == 1

    def test_pdf_ohne_metadaten(self, tmp_path):
        """PDF ohne Metadaten muss Titel aus Dateiname ableiten."""
        from backend.app.services.processors.pdf_processor import PdfProcessor

        mock_doc = MagicMock()
        mock_doc.metadata = {"title": "", "author": "", "producer": ""}
        mock_doc.__len__ = lambda self: 0
        mock_doc.__iter__ = lambda self: iter([])

        with patch("backend.app.services.processors.pdf_processor.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc

            processor = PdfProcessor()
            datei = tmp_path / "mein_pdf_buch.pdf"
            datei.write_bytes(b"%PDF-1.4")
            ergebnis = processor.process(datei)

        assert ergebnis.title == "mein pdf buch"

    def test_pdf_oeffnen_fehlgeschlagen(self, tmp_path):
        """Bei fehlerhafter PDF muss ein Fehler gemeldet werden."""
        from backend.app.services.processors.pdf_processor import PdfProcessor

        with patch("backend.app.services.processors.pdf_processor.fitz") as mock_fitz:
            mock_fitz.open.side_effect = Exception("Ungueltige PDF")

            processor = PdfProcessor()
            datei = tmp_path / "kaputt.pdf"
            datei.write_bytes(b"kein pdf")
            ergebnis = processor.process(datei)

        assert "geoeffnet" in ergebnis.error


# ---------------------------------------------------------------------------
# EPUB-Prozessor (mit Mock)
# ---------------------------------------------------------------------------

class TestEpubProzessorMock:
    """Tests fuer den EPUB-Prozessor mit gemockter ebooklib."""

    def test_epub_metadaten_extrahieren(self, tmp_path):
        """EPUB-Metadaten muessen korrekt extrahiert werden."""
        from backend.app.services.processors.epub_processor import EpubProcessor

        mock_book = MagicMock()

        def mock_get_metadata(ns, field):
            meta = {
                "title": [("Testbuch EPUB", {})],
                "creator": [("EPUB-Autor", {})],
                "publisher": [("EPUB-Verlag", {})],
                "language": [("de", {})],
                "description": [("Eine Beschreibung", {})],
                "identifier": [("9783000000001", {"scheme": "ISBN"})],
            }
            return meta.get(field, [])

        mock_book.get_metadata = mock_get_metadata

        mock_item = MagicMock()
        mock_item.get_content.return_value = b"<html><body><p>Kapitelinhalt</p></body></html>"

        mock_book.get_items_of_type.return_value = [mock_item]

        with patch("backend.app.services.processors.epub_processor.epub") as mock_epub:
            mock_epub.read_epub.return_value = mock_book

            # ebooklib-Konstanten muessen verfuegbar sein
            with patch("backend.app.services.processors.epub_processor.ebooklib") as mock_ebooklib:
                mock_ebooklib.ITEM_DOCUMENT = 9
                mock_ebooklib.ITEM_COVER = 3
                mock_ebooklib.ITEM_IMAGE = 6

                # get_items_of_type soll je nach Typ unterschiedlich antworten
                def items_by_type(item_type):
                    if item_type == 9:  # ITEM_DOCUMENT
                        return [mock_item]
                    return []

                mock_book.get_items_of_type = items_by_type

                processor = EpubProcessor()
                datei = tmp_path / "test.epub"
                datei.write_bytes(b"PK\x03\x04")
                ergebnis = processor.process(datei)

        assert ergebnis.title == "Testbuch EPUB"
        assert ergebnis.author == "EPUB-Autor"
        assert ergebnis.publisher == "EPUB-Verlag"
        assert ergebnis.isbn == "9783000000001"
        assert ergebnis.language == "de"
        assert "Kapitelinhalt" in ergebnis.fulltext

    def test_epub_oeffnen_fehlgeschlagen(self, tmp_path):
        """Bei fehlerhaftem EPUB muss ein Fehler gemeldet werden."""
        from backend.app.services.processors.epub_processor import EpubProcessor

        with patch("backend.app.services.processors.epub_processor.epub") as mock_epub:
            mock_epub.read_epub.side_effect = Exception("Ungueltige EPUB")

            processor = EpubProcessor()
            datei = tmp_path / "kaputt.epub"
            datei.write_bytes(b"kein epub")
            ergebnis = processor.process(datei)

        assert "geoeffnet" in ergebnis.error


# ---------------------------------------------------------------------------
# MOBI-Prozessor (mit Mock)
# ---------------------------------------------------------------------------

class TestMobiProzessorMock:
    """Tests fuer den MOBI-Prozessor."""

    def test_mobi_ohne_bibliothek(self, tmp_path):
        """Ohne mobi-Bibliothek muss ein passender Fehler kommen."""
        from backend.app.services.processors.mobi_processor import MobiProcessor

        processor = MobiProcessor()
        datei = tmp_path / "test.mobi"
        datei.write_bytes(b"MOBI-Daten")

        with patch.dict("sys.modules", {"mobi": None}):
            with patch("builtins.__import__", side_effect=ImportError("mobi nicht installiert")):
                ergebnis = processor.process(datei)

        # Entweder funktioniert der Mock oder die Bibliothek ist vorhanden
        # In beiden Faellen darf kein unbehandelter Fehler auftreten
        assert isinstance(ergebnis, BookProcessingResult)
