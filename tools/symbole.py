#!/usr/bin/env python3
"""Leitet aus frontend/symbole den Symbolsatz für Browser-Tabs, Startbildschirm und PWA ab.

Quellen, jede für ihren Zweck gezeichnet:
  symbol.svg       groß, Grund randlos
  maskierbar.svg   Grund randlos, Motiv ganz in der sicheren Zone (Kreis mit 80 % Durchmesser)
  tab.svg          vereinfacht für kleine Größen, freigestellt und mit kräftigem Rand
  einfarbig.svg    eine Farbe (currentColor)
Erzeugt in frontend/public:
  symbol.svg                                    Kopie für andere Programme im Haus
  favicon.svg, favicon.ico, favicon-32.png      aus tab.svg (16, 32 und 48 in der ico)
  icon-192.png, icon-512.png                    aus symbol.svg mit runden, durchsichtigen Ecken (purpose any)
  icon-maskable-192.png, icon-maskable-512.png  aus maskierbar.svg (purpose maskable)
  icon-monochrom-512.png, einfarbig.svg         aus einfarbig.svg (purpose monochrome, angeheftete Tabs)
  apple-touch-icon.png                          180, deckend
  startbild-<breite>x<höhe>-hell.png, -dunkel.png  Startbilder fürs iPhone, je Größe hell und dunkel: Grund der App
                                                (--grund in src/stil/marken.css), mittig das Symbol
Dazu in frontend/index.html der Block zwischen den Marken "Startbild und Statusleiste": Farbe der Statusleiste je
Einstellung des Geräts (bis das Skript sie der gewählten Darstellung anpasst) und die Startbilder.
Das Zeichen im Kopf der App steht in frontend/src/lib/schale/Logo.svelte (freigestellt aus symbol.svg).

Die Bilder liegen im Repo und werden nie zur Laufzeit erzeugt. Nach einer Änderung neu erzeugen:
  python3 tools/symbole.py
Braucht cairosvg und Pillow, nur auf dem Rechner, der die Bilder erzeugt.
"""

from __future__ import annotations

import io
import re
import shutil
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw

WURZEL = Path(__file__).resolve().parent.parent / "frontend"
QUELLEN, ZIEL = WURZEL / "symbole", WURZEL / "public"
ECKE = 0.22            # Rundung des allgemeinen Symbols, Anteil der Kante
MARKEN, SEITE = WURZEL / "src" / "stil" / "marken.css", WURZEL / "index.html"
# iPhones im Hochformat: Breite und Höhe in Punkten, Pixeldichte. Ein Startbild gilt nur, wenn es genau passt.
IPHONES = [(440, 956, 3), (420, 912, 3), (402, 874, 3), (430, 932, 3), (393, 852, 3), (428, 926, 3), (390, 844, 3), (375, 812, 3),
           (414, 896, 3), (414, 896, 2), (414, 736, 3), (375, 667, 2)]
STARTSYMBOL = 0.3      # Breite des Symbols am Startbild, Anteil der Breite
ANFANG, ENDE = "<!-- Startbild und Statusleiste", "<!-- /Startbild und Statusleiste -->"


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


def grundfarben() -> dict[str, str]:
    """Der Grund hell und dunkel, wie ihn die App selbst zeichnet."""
    css = MARKEN.read_text(encoding="utf-8")
    hell = re.search(r":root\s*\{[^}]*?--grund:\s*(#[0-9a-fA-F]{6})", css)
    dunkel = re.search(r':root\[data-theme="dark"\]\s*\{[^}]*?--grund:\s*(#[0-9a-fA-F]{6})', css)
    if not (hell and dunkel):
        raise SystemExit(f"--grund hell und dunkel nicht gefunden in {MARKEN}")
    return {"hell": hell.group(1).lower(), "dunkel": dunkel.group(1).lower()}


def startbilder(farben: dict[str, str]) -> list[str]:
    """Je iPhone und Darstellung ein Startbild; liefert die Verweise für den Kopf der Seite."""
    verweise = []
    for breite, hoehe, dichte in IPHONES:
        b, h = breite * dichte, hoehe * dichte
        seite = round(b * STARTSYMBOL)
        symbol = runde_ecken(rastern("symbol.svg", seite))
        for art, schema in (("hell", "light"), ("dunkel", "dark")):
            name = f"startbild-{b}x{h}-{art}.png"
            bild = Image.new("RGB", (b, h), farben[art])
            bild.paste(symbol, ((b - seite) // 2, (h - seite) // 2), symbol)
            bild.save(ZIEL / name, optimize=True)
            verweise.append(f'<link rel="apple-touch-startup-image" media="(device-width: {breite}px) and (device-height: {hoehe}px) and '
                            f'(-webkit-device-pixel-ratio: {dichte}) and (orientation: portrait) and (prefers-color-scheme: {schema})" href="/{name}" />')
    return verweise


def kopf(farben: dict[str, str], verweise: list[str]) -> None:
    """Schreibt den Block zwischen den Marken in index.html neu."""
    seite = SEITE.read_text(encoding="utf-8")
    anfang, ende = seite.find(ANFANG), seite.find(ENDE)
    if anfang < 0 or ende < anfang:
        raise SystemExit(f"Marken {ANFANG!r} und {ENDE!r} fehlen in {SEITE}")
    einzug = "    "
    zeilen = [f'{ANFANG}, erzeugt von tools/symbole.py aus src/stil/marken.css: nicht von Hand ändern -->',
              f'<meta name="theme-color" content="{farben["hell"]}" media="(prefers-color-scheme: light)" />',
              f'<meta name="theme-color" content="{farben["dunkel"]}" media="(prefers-color-scheme: dark)" />', *verweise]
    SEITE.write_text(seite[:anfang] + f"\n{einzug}".join(zeilen) + f"\n{einzug}" + seite[ende:], encoding="utf-8")


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
    farben = grundfarben()
    kopf(farben, startbilder(farben))
    print(f"Symbolsatz erzeugt in {ZIEL}")


if __name__ == "__main__":
    main()
