"""Die Codestellen eines Buchs erkennen, je Format: PDF über die Schrift der Textebene (pdf.py) und den Code, den die
Textansicht sonst erkennt (services/textansicht), auch auf erkannten Seiten eines Scans (BF-109, mit den Erkennungen des
Buchs), EPUB, Markdown und Text über ihre Codeblöcke (auszeichnung.py). Läuft in einem eigenen Prozess (dienst.py); hier ist
alles ohne Datenbank und Netz."""

from __future__ import annotations

from pathlib import Path

from backend.app.codestellen import auszeichnung, pdf
from backend.app.codestellen.modelle import Begleiter, Codestelle, Format, Teil, pruefsumme
from backend.app.codestellen.sprache import bestimmen
from backend.app.texterkennung.modelle import Erkennungen

FORMATE: dict[str, Format] = {"pdf": "pdf", "epub": "epub", "md": "md", "txt": "txt"}


def _stelle(kennung_lage: str, teile: list[Teil], code: str, titel: str, datei: str, nummer: int | None,
            sprache_vorgabe: str | None = None) -> Codestelle:
    befund = bestimmen(code, titel, datei)
    if sprache_vorgabe:
        befund = type(befund)(sprache_vorgabe, 0.95, "titel")
    summe = pruefsumme(code)
    return Codestelle(kennung=f"{kennung_lage}-{summe[:8]}", teile=teile, sprache=befund.sprache, sicherheit=befund.sicherheit,
                      quelle=befund.quelle, titel=titel, datei=datei, code=code, zeilennummern_ab=nummer, pruefsumme=summe)


def aus_pdf(pfad: Path, erkennungen: Erkennungen | None = None) -> list[Codestelle]:
    """Listings in Festbreite (pdf.py), dazu der Code, den die Textansicht sonst erkennt (Tafeln mit Code in Textschrift, lose
    Codezeilen; BF-103): so trägt jeder Code, den die Textansicht als Code zeigt, eine Stelle (mit Taste und Vorprüfung).
    `erkennungen`: je Dateiseite die Erkennung, wo es eine gibt (für die Textansicht, wie sie sie liest)."""
    stellen = []
    for kette in pdf.ketten(list(pdf.seiten_lesen(pfad))):
        code, nummer, je_teil = pdf.text_der_kette(kette)
        if not code.strip():
            continue
        erste = kette[0]
        teile = [Teil(seite=b.seite, rechteck=[round(v, 1) for v in b.rechteck], offen_oben=b.offen_oben or i > 0,
                      offen_unten=b.offen_unten or i < len(kette) - 1, zeilen=je_teil[i]) for i, b in enumerate(kette)]
        stellen.append(_stelle(f"s{erste.seite}-{int(erste.zeilen[0].y0)}", teile, code, erste.titel, erste.datei, nummer))
    return stellen + _aus_textansicht(pfad, stellen, erkennungen or {})


def _aus_textansicht(pfad: Path, gefunden: list[Codestelle], erkennungen: Erkennungen) -> list[Codestelle]:
    """Je Seite der Code der Textansicht, der keine Stelle aus Festbreite ist (sie stehen ihr dabei als Codeteile im Weg)."""
    import fitz

    from backend.app.services.textansicht import Codeteil, seitenaufbau

    je_seite: dict[int, list[Codeteil]] = {}
    for s in gefunden:
        for i, (t, zeilen) in enumerate(zip(s.teile, s.zeilen_der_teile())):
            if t.seite is not None and t.rechteck:
                je_seite.setdefault(t.seite, []).append(Codeteil(fitz.Rect(t.rechteck), s.kennung, s.sprache, s.titel, i,
                                                                 len(s.teile), zeilen))
    aus = []
    with fitz.open(str(pfad)) as doc:
        for nr, seite in enumerate(doc, start=1):
            for b in seitenaufbau(seite, je_seite.get(nr), zuschneiden=False, erkennung=erkennungen.get(nr)):
                if b.art != "code" or b.code is None or b.code.kennung or not "".join(b.code.zeilen).strip():
                    continue
                r = b.code.rechteck
                teil = Teil(seite=nr, rechteck=[round(v, 1) for v in r], zeilen=len(b.code.zeilen))
                aus.append(_stelle(f"s{nr}-{int(r.y0)}", [teil], "\n".join(b.code.zeilen), "", "", None))
    return aus


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


def erkennen(pfad: Path, fmt: str, erkennungen: Erkennungen | None = None) -> Begleiter:
    """Alle Codestellen der Datei; eine unlesbare Datei ergibt einen Begleiter ohne Stellen mit Grund."""
    art = FORMATE[fmt]
    try:
        stellen = aus_pdf(pfad, erkennungen) if art == "pdf" else aus_auszeichnung(pfad, art)
    except Exception as f:  # noqa: BLE001 - eine kaputte Datei bekommt einen Grund statt einer Ausnahme
        return Begleiter(format=art, grund=f"Datei nicht lesbar: {type(f).__name__}: {f}"[:300])
    return Begleiter(format=art, stellen=stellen)
