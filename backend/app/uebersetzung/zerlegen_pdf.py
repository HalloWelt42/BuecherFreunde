"""Ein PDF zerlegen (BF-71): die Seiten lesen (pdf_lesen.py), den Aufbau finden (pdf_aufbau.py), daraus ein englisches EPUB
bauen (pdf_epub.py) und dieses zerlegen wie jedes EPUB (zerlegen_epub.py). So bekommt ein PDF dieselben Blöcke mit Kennung,
Marken und Vorlagen, und seine deutsche Fassung setzt derselbe Setzer (setzen.py). Jeder Block kennt die Seite im PDF, ihre
gedruckte Beschriftung und seine Lage dort (aus `data-bf-seite` und `data-bf-lage` seines Elements).

Seiten ohne Textschicht in einem PDF mit Text kommen als Bild hinein und werden genannt (`nicht_lesbar`). Nicht zerlegt wird
ein PDF, das überwiegend aus solchen Seiten besteht (Scan), dessen Text sich nicht lesen lässt (Schrift ohne
Zeichenzuordnung) oder in dem kaum Text steht: das kommt mit der Texterkennung."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import fitz

from backend.app.uebersetzung import pdf_aufbau, pdf_epub, pdf_lesen
from backend.app.uebersetzung.zerlegen_epub import NichtLesbar, Zerlegung
from backend.app.uebersetzung.zerlegen_epub import zerlegen as epub_zerlegen

FASSUNG = 1                                          # steigt sie (anderer Aufbau), wird jede Fassung eines PDF neu zerlegt
TEXTERKENNUNG = "Texterkennung folgt in der nächsten Stufe"
MINDESTENS_WOERTER = 20
SCAN_ANTEIL = 0.5                                    # ab so vielen Seiten ohne Text unter denen mit Inhalt ist es ein Scan


class OhneText(NichtLesbar):
    """Das PDF hat keinen Text, der sich zerlegen lässt; der Grund nennt, dass die Texterkennung folgt."""


@dataclass(frozen=True)
class Seitenlage:
    seite: int                                       # Dateiseite ab 1
    gedruckt: str                                    # die Beschriftung der Seite, sonst die Dateiseite
    lage: tuple[float, float, float, float]


@dataclass(eq=False)
class PdfZerlegung:
    epub: bytes                                      # das englische EPUB, aus dem gesetzt wird
    zerlegung: Zerlegung
    seiten: int
    lagen: dict[str, Seitenlage] = field(default_factory=dict)
    nicht_lesbar: list[str] = field(default_factory=list)
    sprache: str = ""                                # laut PDF (/Lang); leer: unbekannt


def _beschriftung(gedruckt: Sequence[str]):
    def von(seite: int) -> str:
        if 1 <= seite <= len(gedruckt) and gedruckt[seite - 1].strip():
            return gedruckt[seite - 1].strip()
        return str(seite)
    return von


def _pruefen(seiten: list[pdf_lesen.Seite]) -> None:
    mit_inhalt = [s for s in seiten if s.mit_text or s.mit_bild or s.mit_zeichen]
    mit_text = [s for s in mit_inhalt if s.mit_text]
    if not mit_text:
        if any(s.mit_zeichen for s in mit_inhalt):
            raise OhneText(f"Der Text des PDF lässt sich nicht lesen (Schrift ohne Zeichenzuordnung): {TEXTERKENNUNG}")
        raise OhneText(f"Das PDF hat keine Textschicht (Scan): {TEXTERKENNUNG}")
    if len(mit_inhalt) - len(mit_text) > SCAN_ANTEIL * len(mit_inhalt):
        raise OhneText(f"Das PDF besteht überwiegend aus Seiten ohne Textschicht (Scan): {TEXTERKENNUNG}")


def _lagen(z: Zerlegung, beschriftung) -> dict[str, Seitenlage]:
    aus = {}
    for d in z.dokumente:
        for nr, lauf in enumerate(d.laeufe, 1):
            seite, lage = lauf.eltern.attr("data-bf-seite"), lauf.eltern.attr("data-bf-lage").split()
            if seite.isdigit() and len(lage) == 4:
                aus[d.kennung(nr)] = Seitenlage(int(seite), beschriftung(int(seite)), tuple(float(v) for v in lage))
    return aus


def zerlegen(daten: bytes, nie_klassen: frozenset[str] = frozenset(), gedruckt: Sequence[str] = (), titel: str = "",
             autor: str = "") -> PdfZerlegung:
    """`gedruckt` sind die Beschriftungen der Seiten (services/seiten.py), "" wo unbekannt; `titel` und `autor` die des
    Buchs für die Angaben des EPUB (sonst aus dem PDF). Die Blöcke hängen nur an der Datei: was vor dem ersten Kapitel steht,
    heißt nach seiner ersten Überschrift oder dem Titel im PDF."""
    try:
        doc = fitz.open(stream=daten, filetype="pdf")
    except Exception as f:  # noqa: BLE001 - jede Art kaputter Datei
        raise NichtLesbar("Die Datei ist kein lesbares PDF") from f
    with doc:
        if doc.needs_pass:
            raise NichtLesbar("Das PDF ist mit einem Kennwort geschützt")
        seiten = pdf_lesen.lesen(doc)
        _pruefen(seiten)
        angaben = doc.metadata or {}
        im_pdf = " ".join((angaben.get("title") or "").split())
        titel = titel or im_pdf
        autor = autor or (angaben.get("author") or "").strip()
        sprache = (doc.language or "").strip()
        buch = pdf_aufbau.aufbauen(seiten, [(stufe, t, seite) for stufe, t, seite, *_ in doc.get_toc(simple=True)], im_pdf)
        beschriftung = _beschriftung(gedruckt)
        epub = pdf_epub.epub(doc, buch, beschriftung, titel, autor, sprache or "en", pdf_epub.kennung_von(daten))
        nicht_lesbar = [f"Seite {s.nr}" for s in seiten if not s.mit_text and (s.mit_bild or s.mit_zeichen)]
        anzahl = doc.page_count
    zerlegung = epub_zerlegen(epub, nie_klassen)
    if sum(b.woerter for b in zerlegung.bloecke()) < MINDESTENS_WOERTER:
        raise OhneText(f"Im PDF steht kaum Text, der sich zerlegen lässt: {TEXTERKENNUNG}")
    return PdfZerlegung(epub=epub, zerlegung=zerlegung, seiten=anzahl, lagen=_lagen(zerlegung, beschriftung), nicht_lesbar=nicht_lesbar,
                        sprache=sprache)
