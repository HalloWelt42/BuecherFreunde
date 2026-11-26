"""Katalog-Dateien (BF-69): der Standard für jede Bibliothek (`standard.json` neben diesem Modul) und Dateien zum Sichern
und Teilen, alle im selben Format (`modelle.Katalog`). Geprüft wird beim Lesen: Schlüssel und Namen eindeutig, Zeichen,
Farben, Arten und Regeln in ihrer Form; was nicht passt, ist ein Fehler mit Feld und Grund.

Die Herkunft einer Kategorie ergibt sich, wenn eine Datei sie nicht nennt, aus dem Standard: ein Schlüssel des Standards
ist `standard`, einer seiner Teile `geteilt`, alles andere `eigen`."""

from __future__ import annotations

import re
import unicodedata
from functools import cache
from pathlib import Path

from backend.app.katalog.modelle import Herkunft, Katalog

STANDARD = Path(__file__).with_name("standard.json")
UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


@cache
def _standard() -> Katalog:
    return Katalog.model_validate_json(STANDARD.read_bytes())


def standard() -> Katalog:
    """Der Standard-Katalog, jedes Mal eine eigene Abschrift."""
    return _standard().model_copy(deep=True)


@cache
def _herkunft_im_standard() -> dict[str, Herkunft]:
    s = _standard()
    aus: dict[str, Herkunft] = {b.schluessel: "standard" for b in s.bereiche}
    for _, k in s.kategorien():
        aus[k.schluessel] = "standard"
        aus |= {t.schluessel: "geteilt" for t in k.teile}
    return aus


def herkunft(schluessel: str) -> Herkunft:
    return _herkunft_im_standard().get(schluessel, "eigen")


def herkunft_ergaenzen(k: Katalog, zahlen_behalten: bool = False) -> Katalog:
    """Ein Katalog als Entwurf: fehlende Herkunft aus dem Standard. Die Zahlen einer geladenen Datei gelten nicht; die eines
    geänderten Entwurfs bleiben (`zahlen_behalten`)."""
    k = k.model_copy(deep=True)
    for b in k.bereiche:
        b.herkunft = b.herkunft or herkunft(b.schluessel)
        b.anzahl = b.anzahl if zahlen_behalten else None
        for kat in b.kategorien:
            kat.herkunft = kat.herkunft or herkunft(kat.schluessel)
            kat.anzahl = kat.anzahl if zahlen_behalten else None
    return k


def zeichen_im_standard() -> list[str]:
    """Alle Zeichen des Standards, für Wahlen der KI."""
    s = _standard()
    zeichen = [b.zeichen for b in s.bereiche] + [k.zeichen for _, k in s.kategorien()]
    zeichen += [t.zeichen for _, k in s.kategorien() for t in k.teile]
    return sorted({z for z in zeichen if z} | {"tag", "folder", "bookmark"})


def schluesselteil(name: str) -> str:
    """Ein Teil eines Schlüssels aus einem Namen: klein, Umlaute ausgeschrieben, ohne Akzente, Wörter mit Bindestrich."""
    t = unicodedata.normalize("NFKC", name).casefold().translate(UMLAUTE)
    t = "".join(z for z in unicodedata.normalize("NFKD", t) if not unicodedata.combining(z))
    return "-".join(re.findall(r"[a-z0-9]+", t))[:60] or "eigen"


def freier_schluessel(grund: str, vergeben: set[str]) -> str:
    """`grund`, oder mit angehängter Zahl, wenn er schon vergeben ist."""
    schluessel, zaehler = grund, 2
    while schluessel in vergeben:
        schluessel, zaehler = f"{grund}-{zaehler}", zaehler + 1
    return schluessel
