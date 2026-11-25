"""Die fünf Orte der App auf dem Gerät. Jeder ist für sich einstellbar und umziehbar (zweite Platte, SSD im NAS):

- bestand: Datenbank (Angaben, Notizen, Lesestände), die einzige Wahrheit auf dem Gerät
- suche: Suchindex, jederzeit neu zu bauen
- texte: Volltext, Seiten und Angaben je Buch, auch im Begleiter in der Kellerwolke
- umschlaege: Umschlagbilder, auch im Begleiter
- zwischen: Originale auf Zeit, im Betrieb im Arbeitsspeicher

Eine Markerdatei je Ort verhindert, dass bei einer nicht eingehängten Platte still ein leerer Ordner benutzt wird."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.orte")
MARKER = ".buecherfreunde"
KNAPP = {True: 2_000_000_000, False: 200_000_000}      # so wenig freier Platz ist knapp; der Zwischenspeicher räumt selbst auf


@dataclass(frozen=True)
class Ort:
    kennung: str
    name: str
    pfad: Path
    dauerhaft: bool        # braucht die Markerdatei; der Zwischenspeicher ist flüchtig


def alle() -> list[Ort]:
    return [Ort("bestand", "Bestand", settings.database_dir, True), Ort("suche", "Suchindex", settings.suche_dir, False),
            Ort("texte", "Volltexte", settings.storage_dir, True), Ort("umschlaege", "Umschläge", settings.umschlaege_dir, False),
            Ort("zwischen", "Zwischenspeicher", settings.zwischen_dir, False)]


def einrichten() -> None:
    """Legt fehlende Ordner an und prüft die Marker. Die Datenbank ohne Marker heißt: Platte nicht eingehängt."""
    neu = not (settings.database_path.exists() or (settings.storage_dir / MARKER).exists())
    for ort in alle():
        ort.pfad.mkdir(parents=True, exist_ok=True)
        marker = ort.pfad / MARKER
        if not ort.dauerhaft or marker.exists():
            continue
        leer = not any(ort.pfad.iterdir())
        if not neu and leer:
            raise RuntimeError(f"ABBRUCH: {ort.name} ({ort.pfad}) ist leer und trägt keine Markerdatei. Ist die Platte eingehängt?")
        marker.write_text("BücherFreunde: diese Datei nicht löschen, sie zeigt, dass die Platte eingehängt ist.\n", encoding="utf-8")
        logger.info("Marker angelegt: %s", marker)


def belegt(pfad: Path) -> int:
    return sum(f.stat().st_size for f in pfad.rglob("*") if f.is_file())


def stand() -> list[dict]:
    aus = []
    for ort in alle():
        try:
            platz = shutil.disk_usage(ort.pfad)
            gut = not ort.dauerhaft or (ort.pfad / MARKER).exists()
            aus.append({"kennung": ort.kennung, "name": ort.name, "pfad": str(settings.host_pfade.get(ort.kennung) or ort.pfad),
                        "belegt": belegt(ort.pfad), "frei": platz.free, "stand": "schlecht" if not gut else "warn" if platz.free < KNAPP[ort.dauerhaft] else "gut"})
        except OSError as f:
            aus.append({"kennung": ort.kennung, "name": ort.name, "pfad": str(ort.pfad), "belegt": 0, "frei": 0, "stand": "schlecht", "text": str(f)})
    return aus
