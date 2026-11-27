"""Eine Textschicht je Seite (BF-109): hier, und nur hier, entscheidet sich, ob für eine PDF-Seite die Textschicht des PDF gilt
oder ihre Erkennung. Textansicht, Volltext, Suche, Codestellen und der Auftrag "Texte erkennen" fragen alle diese Stelle.

- Ohne lesbaren Text (`ohne_lesbaren_text`) ist ein Seitentext mit weniger als `TEXTERKENNUNG_MINDESTZEICHEN` Buchstaben und
  Ziffern, oder einer, der nicht lesbar ist (Zeichensalat einer Schrift ohne Zeichenzuordnung, `pdfseite.lesbar`, dieselbe
  Regel wie in der Textansicht).
- Die Erkennung gilt nur für eine Seite ohne lesbaren Text, und nur, wenn sie selbst lesbaren Text trägt. Sonst gilt die
  Textschicht des PDF, wie sie ist; das Original bleibt immer unverändert.
- Aus einer Erkennung zählen nur Wörter, deren Sicherheit mindestens SICHER_AB ist (Rauschen in Bildern hat wenig).
- Erkannt werden die Seiten ohne lesbaren Text eines Scans (`ist_scan`): eines PDF, in dem mindestens
  `TEXTERKENNUNG_SCAN_ANTEIL` der Seiten keinen lesbaren Text tragen. In anderen PDF sind solche Seiten Bilder (Umschlag,
  ganzseitige Abbildung) und bleiben, wie sie sind; mit dem Anteil 0 wird jede Seite ohne lesbaren Text erkannt.

`schicht` gibt je Seite die Art ("pdf", "erkannt", "ohne": weder Textschicht noch Erkennung mit lesbarem Text), den schlichten
Text (für Volltext und Suche) und die geltende Erkennung."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import fitz

from backend.app.core.config import settings
from backend.app.services import pdfseite
from backend.app.texterkennung.modelle import ErkannteZeile, Seitenerkennung, Wort

SICHER_AB = 20                  # Sicherheit eines Worts, ab der es zählt (gemessen: Fließtext über 90, schwierige echte Wörter
                                # bis hinab zu 29, Striche einer Tabelle aus Zeichen bis 2)

Schichtart = Literal["pdf", "erkannt", "ohne"]


def lesbare_zeichen(text: str) -> int:
    return sum(c.isalnum() for c in text)


def ohne_lesbaren_text(text: str) -> bool:
    """Trägt ein Seitentext keinen lesbaren Text (zu wenige Buchstaben und Ziffern, oder Zeichensalat)?"""
    return lesbare_zeichen(text) < settings.texterkennung_mindestzeichen or not pdfseite.lesbar(text)


def ist_scan(ohne_text: int, seiten: int) -> bool:
    """Ist ein PDF mit so vielen Seiten ohne lesbaren Text ein Scan, dessen Seiten erkannt werden?"""
    return ohne_text > 0 and ohne_text >= settings.texterkennung_scan_anteil * seiten


def sichere_woerter(zeile: ErkannteZeile) -> list[Wort]:
    return [w for w in zeile.woerter if w.sicherheit >= SICHER_AB]


def erkannter_text(e: Seitenerkennung) -> str:
    """Der schlichte Text einer Erkennung: Zeile für Zeile, wie das Programm sie gliedert (wie `pdfseite.seitentext`)."""
    zeilen = (" ".join(w.text for w in sichere_woerter(z)) for z in e.zeilen)
    return "\n".join(z for z in zeilen if z)


def traegt_text(e: Seitenerkennung) -> bool:
    """Hat die Erkennung lesbaren Text gefunden?"""
    return pdfseite.lesbar(erkannter_text(e))


@dataclass(frozen=True)
class Schicht:
    art: Schichtart
    text: str                                   # der schlichte Text der Seite
    erkennung: Seitenerkennung | None = None    # bei "erkannt" die geltende Erkennung


def schicht_aus(pdf_text: str, erkennung: Seitenerkennung | None) -> Schicht:
    """Die Entscheidung aus dem schlichten Text der Textschicht und der Erkennung der Seite (falls es eine gibt)."""
    if not ohne_lesbaren_text(pdf_text):
        return Schicht("pdf", pdf_text)
    if erkennung is not None and traegt_text(erkennung):
        return Schicht("erkannt", erkannter_text(erkennung), erkennung)
    return Schicht("ohne", pdf_text)


def schicht(seite: fitz.Page, erkennung: Seitenerkennung | None) -> Schicht:
    """Welche Textschicht für diese PDF-Seite gilt."""
    return schicht_aus(pdfseite.seitentext(seite), erkennung)
