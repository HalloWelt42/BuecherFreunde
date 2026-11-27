"""BF-110: Ein PDF kennt keinen Verlag; "producer" nennt das Programm, das die Datei erzeugt hat, und wird nie zum Verlag."""

import fitz

from backend.app.services.processors.pdf_processor import PdfProcessor


def test_erzeuger_des_pdf_wird_kein_verlag(tmp_path):
    datei = tmp_path / "zahlenreich.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Zahlenreich")
    doc.set_metadata({"title": "Zahlenreich", "author": "HalloWelt42", "producer": "Erfundenes Satzprogramm 1.0", "creator": "Textmaschine"})
    doc.save(datei)
    ergebnis = PdfProcessor().process(datei)
    assert (ergebnis.title, ergebnis.author, ergebnis.publisher) == ("Zahlenreich", "HalloWelt42", "")
