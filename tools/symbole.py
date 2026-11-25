#!/usr/bin/env python3
"""Leitet aus frontend/symbole den Symbolsatz für Browser-Tabs, Startbildschirm und PWA ab.

Quellen, jede für ihren Zweck gezeichnet:
  symbol.svg       groß, Grund randlos
  maskierbar.svg   Grund randlos, Motiv ganz in der sicheren Zone (Kreis mit 80 % Durchmesser)
  tab.svg          vereinfacht für kleine Größen, mit eigener runder Platte
  einfarbig.svg    eine Farbe (currentColor)
Erzeugt in frontend/public:
  symbol.svg                                    Kopie für andere Programme im Haus
  favicon.svg, favicon.ico, favicon-32.png      aus tab.svg (16, 32 und 48 in der ico)
  icon-192.png, icon-512.png                    aus symbol.svg mit runden, durchsichtigen Ecken (purpose any)
  icon-maskable-192.png, icon-maskable-512.png  aus maskierbar.svg (purpose maskable)
  icon-monochrom-512.png, einfarbig.svg         aus einfarbig.svg (purpose monochrome, angeheftete Tabs)
  apple-touch-icon.png                          180, deckend
Das Zeichen im Kopf der App steht in frontend/src/lib/schale/Logo.svelte (wie tab.svg).

Die Bilder liegen im Repo und werden nie zur Laufzeit erzeugt. Nach einer Änderung neu erzeugen:
  python3 tools/symbole.py
Braucht cairosvg und Pillow, nur auf dem Rechner, der die Bilder erzeugt.
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw

WURZEL = Path(__file__).resolve().parent.parent / "frontend"
QUELLEN, ZIEL = WURZEL / "symbole", WURZEL / "public"
ECKE = 0.22            # Rundung des allgemeinen Symbols, Anteil der Kante


def rastern(quelle: str, groesse: int) -> Image.Image:
    png = cairosvg.svg2png(bytestring=(QUELLEN / quelle).read_bytes(), output_width=groesse, output_height=groesse)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def runde_ecken(bild: Image.Image) -> Image.Image:
    fein = bild.width * 4
    maske = Image.new("L", (fein, fein))
    ImageDraw.Draw(maske).rounded_rectangle((0, 0, fein - 1, fein - 1), radius=fein * ECKE, fill=255)
    bild.putalpha(maske.resize(bild.size, Image.Resampling.LANCZOS))
    return bild


def deckend(bild: Image.Image) -> Image.Image:
    """Ohne Durchsichtigkeit: iOS füllt durchsichtige Stellen sonst schwarz."""
    grund = Image.new("RGBA", bild.size, bild.getpixel((1, 1)))
    return Image.alpha_composite(grund, bild).convert("RGB")


def main() -> None:
    for quelle, ziel in (("symbol.svg", "symbol.svg"), ("tab.svg", "favicon.svg"), ("einfarbig.svg", "einfarbig.svg")):
        shutil.copyfile(QUELLEN / quelle, ZIEL / ziel)
    ico = [rastern("tab.svg", g) for g in (48, 32, 16)]
    ico[0].save(ZIEL / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=ico[1:])
    ico[1].save(ZIEL / "favicon-32.png", optimize=True)
    for g in (192, 512):
        runde_ecken(rastern("symbol.svg", g)).save(ZIEL / f"icon-{g}.png", optimize=True)
        rastern("maskierbar.svg", g).convert("RGB").save(ZIEL / f"icon-maskable-{g}.png", optimize=True)
    rastern("einfarbig.svg", 512).save(ZIEL / "icon-monochrom-512.png", optimize=True)
    deckend(rastern("symbol.svg", 180)).save(ZIEL / "apple-touch-icon.png", optimize=True)
    print(f"Symbolsatz erzeugt in {ZIEL}")


if __name__ == "__main__":
    main()
