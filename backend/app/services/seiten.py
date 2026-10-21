"""Seiten eines Volltexts: eine Regel für Leser, Suche im Buch und den Anbieterweg für Fundus.

Zwei Zählungen, überall gleich benannt:
- Dateiseite: die N-te Seite der Datei, wie im Leser (?page=N); für Sprünge.
- gedruckte Seite: die Beschriftung im Buch ("110", "iv"); für Menschen. Aus den Seitenbeschriftungen des PDF
  (PageLabels), sonst aus den Zahlen am Rand der Seiten erkannt (Kopf- und Fußzeilen), sonst leer.

fulltext.txt trennt Seiten mit Seitenvorschub (\\f), je Dateiseite genau ein Teil, auch leere Seiten. Ältere Volltexte
eines PDF ohne Seitenvorschub (früher mit Zeilenumbruch verbunden) werden beim ersten Lesen aus der Originaldatei neu
ausgelesen (Befund 21.10.2026: die gleichmäßige Teilung nach Zeichen traf Seiten um bis zu ein Dutzend daneben). Nur
Formate ohne Seiten (EPUB, Text) werden gleichmäßig geteilt (mindestens 500 Zeichen je Seite).

Die gedruckten Seiten liegen als Begleiter seiten.json neben dem Volltext (einmal berechnet)."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from pathlib import Path

from backend.app.services.storage import get_original_file, get_sidecar_path, load_fulltext, save_fulltext

logger = logging.getLogger(__name__)

SEITENTRENNER = "\f"
BEGLEITER = "seiten.json"
_FASSUNG = 1
_RANDZEILEN = 2                      # so viele Zeilen oben und unten gelten als Rand (Kopf- und Fußzeile)
_ZAHL = re.compile(r"(?<![\d.,])\d{1,4}(?![\d.,])")


def seiten_aus(text: str, page_count: int | None) -> list[str]:
    if not text:
        return []
    if SEITENTRENNER in text:
        return text.split(SEITENTRENNER)
    je_seite = max(len(text) // (page_count or 1), 500)
    return [text[i:i + je_seite] for i in range(0, len(text), je_seite)]


def pdf_seitentexte(pfad: Path) -> list[str]:
    import fitz

    with fitz.open(str(pfad)) as doc:
        return [(seite.get_text("text") or "") for seite in doc]


def pdf_volltext(pfad: Path) -> str:
    """Volltext eines PDF: je Dateiseite ein Teil, getrennt mit Seitenvorschub."""
    return SEITENTRENNER.join(t.replace(SEITENTRENNER, "\n") for t in pdf_seitentexte(pfad))


def _beschriftungen(pfad: Path) -> list[str]:
    """Seitenbeschriftungen des PDF (PageLabels); leer, wenn das PDF keine hat."""
    import fitz

    with fitz.open(str(pfad)) as doc:
        if not doc.get_page_labels():
            return []
        return [seite.get_label() or "" for seite in doc]


def _rand(text: str) -> list[str]:
    zeilen = [z.strip() for z in text.splitlines() if z.strip()]
    return zeilen[:_RANDZEILEN] + zeilen[-_RANDZEILEN:] if len(zeilen) > 2 * _RANDZEILEN else zeilen


def erkennen(texte: list[str]) -> list[str]:
    """Gedruckte Seiten aus den Zahlen am Rand: jede Zahl in Kopf- oder Fußzeile stimmt für einen Versatz zur
    Dateiseite; der häufigste gilt, wenn er auf genug Seiten steht. Beschriftet werden die Seiten vom ersten bis zum
    letzten Treffer dieses Versatzes (dazwischen auch leere Seiten); davor und danach bleibt die Angabe leer."""
    stimmen: Counter[int] = Counter()
    funde: list[set[int]] = []
    for nr, text in enumerate(texte, 1):
        versaetze = {int(z) - nr for zeile in _rand(text) for z in _ZAHL.findall(zeile) if int(z) > 0}
        funde.append(versaetze)
        stimmen.update(versaetze)
    if not stimmen:
        return []
    versatz, anzahl = stimmen.most_common(1)[0]
    if anzahl < max(5, len(texte) // 5):
        return []
    treffer = [i for i, v in enumerate(funde) if versatz in v]
    erste, letzte = treffer[0], treffer[-1]
    return [str(i + 1 + versatz) if erste <= i <= letzte and i + 1 + versatz > 0 else "" for i in range(len(texte))]


def _gedruckt_berechnen(original: Path | None, fmt: str, texte: list[str]) -> tuple[str, list[str]]:
    if fmt == "pdf" and original is not None:
        try:
            beschriftet = _beschriftungen(original)
            if len(beschriftet) == len(texte) and any(beschriftet):
                return "beschriftungen", beschriftet
        except Exception as f:  # noqa: BLE001 - ohne Beschriftungen bleibt die Erkennung am Rand
            logger.info("Seitenbeschriftungen nicht lesbar: %s", f)
    if fmt != "pdf":
        return "", []
    erkannt = erkennen(texte)
    return ("rand", erkannt) if any(erkannt) else ("", [])


def buch_seiten(file_hash: str, fmt: str | None, page_count: int | None) -> tuple[list[str], list[str]]:
    """Die Seiten eines Buchs (Text je Dateiseite) und je Seite die gedruckte Seite ("" wo unbekannt). Ein PDF-Volltext
    ohne Seitenvorschub wird dabei einmal aus der Originaldatei neu ausgelesen und gespeichert."""
    fmt = (fmt or "").lower()
    text = load_fulltext(file_hash) or ""
    original = get_original_file(file_hash)
    if fmt == "pdf" and original is not None and SEITENTRENNER not in text:
        try:
            neu = pdf_volltext(original)
            if neu.strip():
                save_fulltext(file_hash, neu)
                text = neu
                get_sidecar_path(file_hash, BEGLEITER).unlink(missing_ok=True)
        except Exception as f:  # noqa: BLE001 - dann gilt der alte Volltext weiter
            logger.warning("Volltext von %s nicht neu auslesbar: %s", file_hash[:12], f)
    texte = seiten_aus(text, page_count)
    pfad = get_sidecar_path(file_hash, BEGLEITER)
    try:
        gespeichert = json.loads(pfad.read_text(encoding="utf-8")) if pfad.exists() else {}
    except (OSError, ValueError):
        gespeichert = {}
    gedruckt = gespeichert.get("gedruckt") if gespeichert.get("fassung") == _FASSUNG else None
    if gedruckt is None or (gedruckt and len(gedruckt) != len(texte)):
        quelle, gedruckt = _gedruckt_berechnen(original, fmt, texte)
        try:
            pfad.write_text(json.dumps({"fassung": _FASSUNG, "quelle": quelle, "gedruckt": gedruckt}, ensure_ascii=False),
                            encoding="utf-8")
        except OSError:
            pass
    return texte, (gedruckt or [""] * len(texte))
