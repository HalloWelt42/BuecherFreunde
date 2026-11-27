"""Hilfen für die Tests der Texterkennung (BF-109), alles erfunden: Seiten als Scan (Text gerendert, als Bild in ein PDF ohne
Textschicht gelegt), eine Attrappe des Programms (ein eigener Prozess, der TSV ausgibt wie das echte) und Erkennungen von Hand."""

from __future__ import annotations

import shutil
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

import fitz
import pytest

from backend.app.texterkennung.modelle import ErkannteZeile, Seitenerkennung, Wort

ECHT = shutil.which("tesseract")
braucht_programm = pytest.mark.skipif(ECHT is None, reason="Tesseract ist auf diesem Gerät nicht eingerichtet")

# Maße einer erfundenen Schrift (Anteile der Schriftgröße), etwas anders als die Eichung der Textansicht
OBERLAENGE, X_HOEHE, UNTERLAENGE = 0.73, 0.52, 0.21
OBEN = set("ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ0123456789bdfhklßtij")
UNTEN = set("gjpqy")


@dataclass
class Probezeile:
    text: str
    x: float                # linker Rand in PDF-Punkten
    basis: float            # Grundlinie in PDF-Punkten
    groesse: float = 11.0
    block: int = 1
    absatz: int = 1


def _woerter(z: Probezeile) -> list[tuple[str, tuple[float, float, float, float]]]:
    aus, x = [], z.x
    for wort in z.text.split():
        breite = fitz.get_text_length(wort, fontname="helv", fontsize=z.groesse)
        oben = z.basis - (OBERLAENGE if set(wort) & OBEN else X_HOEHE) * z.groesse
        unten = z.basis + (UNTERLAENGE * z.groesse if set(wort) & UNTEN else 0.0)
        aus.append((wort, (x, oben, x + breite, unten)))
        x += breite + fitz.get_text_length(" ", fontname="helv", fontsize=z.groesse)
    return aus


def erkennung(seite: int, zeilen: list[Probezeile], flaechen: list[tuple[float, float, float, float]] | None = None,
              sicherheit: int = 95) -> Seitenerkennung:
    """Eine Erkennung von Hand, wie das Programm sie liefern würde."""
    erkannt = [ErkannteZeile(block=z.block, absatz=z.absatz, zeile=i, woerter=[Wort(text=t, lage=r, sicherheit=sicherheit)
                                                                                 for t, r in _woerter(z)])
               for i, z in enumerate(zeilen, start=1)]
    return Seitenerkennung(seite=seite, werkzeug="tesseract", fassung="5.3.0", sprachen="deu+eng", dpi=300,
                           erkannt_am="2026-11-27T10:00:00Z", dauer_s=1.0, zeilen=erkannt, flaechen=flaechen or [])


def tsv(zeilen: list[Probezeile], dpi: int = 300, flaechen: list[tuple[float, float, float, float]] | None = None) -> str:
    """Die TSV des Programms für diese Zeilen (Bildpunkte bei `dpi`), mit Blöcken ohne Text für `flaechen`."""
    f = dpi / 72
    kopf = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
    reihen = [kopf, "1\t1\t0\t0\t0\t0\t0\t0\t2480\t3508\t-1\t"]

    def box(r: tuple[float, float, float, float]) -> str:
        return f"{round(r[0] * f)}\t{round(r[1] * f)}\t{round((r[2] - r[0]) * f)}\t{round((r[3] - r[1]) * f)}"

    for i, z in enumerate(zeilen, start=1):
        reihen.append(f"2\t1\t{z.block}\t0\t0\t0\t{box((z.x, z.basis - z.groesse, z.x + 100, z.basis))}\t-1\t")
        for n, (wort, r) in enumerate(_woerter(z), start=1):
            reihen.append(f"5\t1\t{z.block}\t{z.absatz}\t{i}\t{n}\t{box(r)}\t96.5\t{wort}")
    for k, r in enumerate(flaechen or [], start=100):
        reihen.append(f"2\t1\t{k}\t0\t0\t0\t{box(r)}\t-1\t")
    return "\n".join(reihen) + "\n"


def scan_pdf(pfad: Path, seiten: list[str], dpi: int = 150, groesse: float = 12) -> Path:
    """Ein PDF ohne Textschicht: je Seite der Text gerendert und nur als Bild eingelegt."""
    scan = fitz.open()
    for text in seiten:
        vorlage = fitz.open()
        s = vorlage.new_page(width=595, height=842)
        s.insert_textbox(fitz.Rect(72, 90, 523, 780), text, fontname="helv", fontsize=groesse)
        bild = s.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
        neu = scan.new_page(width=595, height=842)
        neu.insert_image(neu.rect, pixmap=bild)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    scan.save(pfad)
    return pfad


def text_pdf(pfad: Path, seiten: list[str]) -> Path:
    """Ein PDF mit Textschicht."""
    doc = fitz.open()
    for text in seiten:
        doc.new_page(width=595, height=842).insert_textbox(fitz.Rect(72, 90, 523, 780), text, fontname="helv", fontsize=11)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    doc.save(pfad)
    return pfad


ATTRAPPE = """#!{python}
# Attrappe des Programms der Texterkennung: Fassung, Sprachdaten und je Bild die TSV aus ATTRAPPE_TSV
import os, sys, time
argumente = sys.argv[1:]
if "--version" in argumente:
    print("tesseract 5.3.0")
    sys.exit(0)
if "--list-langs" in argumente:
    print('List of available languages in "/attrappe/" (2):')
    print("\\n".join(os.environ.get("ATTRAPPE_SPRACHEN", "deu eng").split()))
    sys.exit(0)
bild = sys.stdin.buffer.read()
with open(os.environ["ATTRAPPE_PROTOKOLL"], "a", encoding="utf-8") as f:
    f.write(" ".join(argumente) + " OMP=" + os.environ.get("OMP_THREAD_LIMIT", "") + " PNG=" + str(bild[:4] == b"\\x89PNG") + "\\n")
time.sleep(float(os.environ.get("ATTRAPPE_SCHLAF", "0")))
code = int(os.environ.get("ATTRAPPE_CODE", "0"))
if code:
    sys.stderr.write("die Attrappe scheitert")
    sys.exit(code)
with open(os.environ["ATTRAPPE_TSV"], encoding="utf-8") as f:
    sys.stdout.write(f.read())
"""


@dataclass
class Attrappe:
    programm: Path
    protokoll: Path
    ausgabe: Path

    def aufrufe(self) -> list[str]:
        return self.protokoll.read_text(encoding="utf-8").splitlines() if self.protokoll.exists() else []

    def liefert(self, zeilen: list[Probezeile], flaechen: list[tuple[float, float, float, float]] | None = None) -> None:
        self.ausgabe.write_text(tsv(zeilen, flaechen=flaechen), encoding="utf-8")


def attrappe_anlegen(ordner: Path, monkeypatch) -> Attrappe:
    """Die Attrappe als ausführbare Datei; die Einstellungen zeigen auf sie."""
    from backend.app.core.config import settings
    from backend.app.texterkennung import werkzeug

    ordner.mkdir(parents=True, exist_ok=True)
    programm = ordner / "tesseract"
    programm.write_text(ATTRAPPE.format(python=sys.executable), encoding="utf-8")
    programm.chmod(programm.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    a = Attrappe(programm, ordner / "aufrufe.txt", ordner / "ausgabe.tsv")
    a.liefert([Probezeile("Eine erfundene Zeile der Attrappe.", 72, 120)])
    monkeypatch.setenv("ATTRAPPE_PROTOKOLL", str(a.protokoll))
    monkeypatch.setenv("ATTRAPPE_TSV", str(a.ausgabe))
    monkeypatch.setattr(settings, "texterkennung_programm", str(programm))
    werkzeug.vergessen()
    return a
