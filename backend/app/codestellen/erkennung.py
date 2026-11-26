"""Die Codestellen eines Buchs erkennen, je Format: PDF über die Schrift der Textebene (pdf.py), EPUB, Markdown und Text über
ihre Codeblöcke (auszeichnung.py). Läuft in einem eigenen Prozess (dienst.py); hier ist alles ohne Datenbank und Netz."""

from __future__ import annotations

import hashlib
from pathlib import Path

from backend.app.codestellen import auszeichnung, pdf
from backend.app.codestellen.modelle import Begleiter, Codestelle, Format, Teil
from backend.app.codestellen.sprache import bestimmen

FORMATE: dict[str, Format] = {"pdf": "pdf", "epub": "epub", "md": "md", "txt": "txt"}


def pruefsumme(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]


def _stelle(kennung_lage: str, teile: list[Teil], code: str, titel: str, datei: str, nummer: int | None,
            sprache_vorgabe: str | None = None) -> Codestelle:
    befund = bestimmen(code, titel, datei)
    if sprache_vorgabe:
        befund = type(befund)(sprache_vorgabe, 0.95, "titel")
    summe = pruefsumme(code)
    return Codestelle(kennung=f"{kennung_lage}-{summe[:8]}", teile=teile, sprache=befund.sprache, sicherheit=befund.sicherheit,
                      quelle=befund.quelle, titel=titel, datei=datei, code=code, zeilennummern_ab=nummer, pruefsumme=summe)


def aus_pdf(pfad: Path) -> list[Codestelle]:
    stellen = []
    for kette in pdf.ketten(list(pdf.seiten_lesen(pfad))):
        code, nummer, je_teil = pdf.text_der_kette(kette)
        if not code.strip():
            continue
        erste = kette[0]
        teile = [Teil(seite=b.seite, rechteck=[round(v, 1) for v in b.rechteck], offen_oben=b.offen_oben or i > 0,
                      offen_unten=b.offen_unten or i < len(kette) - 1, zeilen=je_teil[i]) for i, b in enumerate(kette)]
        stellen.append(_stelle(f"s{erste.seite}-{int(erste.zeilen[0].y0)}", teile, code, erste.titel, erste.datei, nummer))
    return stellen


def aus_auszeichnung(pfad: Path, fmt: Format) -> list[Codestelle]:
    bloecke = auszeichnung.epub_bloecke(pfad) if fmt == "epub" else auszeichnung.text_bloecke(pfad.read_text("utf-8", errors="replace"))
    stellen = []
    for b in bloecke:
        if fmt == "epub":
            teil, lage = Teil(kapitel=b.kapitel, nr=b.nr), f"{b.kapitel}#{b.nr}"
        else:
            teil, lage = Teil(zeile=b.zeile), f"z{b.zeile}"
        stellen.append(_stelle(lage, [teil], b.code, b.titel, "", None, b.sprache))
    return stellen


def erkennen(pfad: Path, fmt: str) -> Begleiter:
    """Alle Codestellen der Datei; eine unlesbare Datei ergibt einen Begleiter ohne Stellen mit Grund."""
    art = FORMATE[fmt]
    try:
        stellen = aus_pdf(pfad) if art == "pdf" else aus_auszeichnung(pfad, art)
    except Exception as f:  # noqa: BLE001 - eine kaputte Datei bekommt einen Grund statt einer Ausnahme
        return Begleiter(format=art, grund=f"Datei nicht lesbar: {type(f).__name__}: {f}"[:300])
    return Begleiter(format=art, stellen=stellen)
