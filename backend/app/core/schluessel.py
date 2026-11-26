"""Der Schlüsselbund der App: die eine Stelle, die Schlüssel liest und schreibt (BF-82).

Zwei Orte, eine Regel: Was in der App eingetragen ist (Ersteinrichtung, Anschlüsse, Umzug), steht in ihrer eigenen
Schlüsseldatei (`settings.schluessel_pfad`, JSON, Modus 0600, nur für den Server lesbar, nie in einer Sicherung) und gilt
vor der Datei aus der Einrichtung (`KELLERWOLKE_SCHLUESSEL_DATEI`, `LEITSTELLE_SCHLUESSEL_DATEI`). Ohne Eintrag in der App gilt
die Datei der Einrichtung wie bisher. Wer einen Schlüssel braucht (Kellerwolke, Anmeldung, Leitstelle), fragt `lesen`.

Kein Weg gibt einen Schlüssel zurück; hinaus geht nur `stand` (eingetragen und woher). Vorgemerkte Schlüssel (Assistent unter
Wartung, noch nicht bestätigt) liegen in derselben Datei und gelten erst nach `uebernehmen`."""

from __future__ import annotations

import json
import logging
import os
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.schluessel")
ART = "buecherfreunde-schluessel/1"


class Art(StrEnum):
    KELLERWOLKE = "kellerwolke"        # App-Zugang der Kellerwolke
    LEITSTELLE = "leitstelle"          # Schlüssel der Anwendung in der Leitstelle (KI und Sprechdienst)
    UMZUG = "umzug"                    # neues Gerät: Sitzung beim alten Gerät, um Originale zu holen


# die Datei der Einrichtung je Art; der Umzug hat keine
EINRICHTUNG = {Art.KELLERWOLKE: "kellerwolke_schluessel_datei", Art.LEITSTELLE: "leitstelle_schluessel_datei"}


class Schluesselstand(BaseModel):
    """Was hinausgeht: nie der Schlüssel selbst."""

    eingetragen: bool
    herkunft: Literal["app", "einrichtung", ""] = ""        # app: in der eigenen Datei; einrichtung: Datei aus der .env
    vorgemerkt: bool = False                                 # ein neuer wartet auf die Bestätigung (Wartung)


class _Inhalt(BaseModel):
    art: str = ART
    schluessel: dict[str, str] = Field(default_factory=dict)
    vorgemerkt: dict[str, str] = Field(default_factory=dict)


def _laden() -> _Inhalt:
    pfad = settings.schluessel_pfad
    try:
        return _Inhalt.model_validate_json(pfad.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _Inhalt()
    except (OSError, ValueError) as f:
        logger.warning("Eigene Schlüsseldatei nicht lesbar: %s", type(f).__name__)
        return _Inhalt()


def _sichern(inhalt: _Inhalt) -> None:
    """Schreibt die Datei ganz neu, erst fertig unter ihrem Namen, von Anfang an nur für den Server lesbar."""
    pfad = settings.schluessel_pfad
    pfad.parent.mkdir(parents=True, exist_ok=True)
    teil = pfad.with_name(f".{pfad.name}.teil")
    fd = os.open(teil, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(inhalt.model_dump(), ensure_ascii=False, indent=1))
            f.flush()
            os.fsync(f.fileno())
        os.chmod(teil, 0o600)
        os.replace(teil, pfad)
    finally:
        teil.unlink(missing_ok=True)


def _aus_einrichtung(art: Art) -> str:
    feld = EINRICHTUNG.get(art)
    datei = getattr(settings, feld) if feld else ""
    if not datei:
        return ""
    try:
        return Path(datei).read_text(encoding="utf-8").strip()
    except OSError as f:
        logger.warning("Schlüsseldatei der Einrichtung für %s nicht lesbar: %s", art.value, f)
        return ""


def lesen(art: Art) -> str:
    """Der Schlüssel, der gilt; leer ohne."""
    return _laden().schluessel.get(art.value, "") or _aus_einrichtung(art)


def stand(art: Art) -> Schluesselstand:
    inhalt = _laden()
    vorgemerkt = bool(inhalt.vorgemerkt.get(art.value))
    if inhalt.schluessel.get(art.value):
        return Schluesselstand(eingetragen=True, herkunft="app", vorgemerkt=vorgemerkt)
    if _aus_einrichtung(art):
        return Schluesselstand(eingetragen=True, herkunft="einrichtung", vorgemerkt=vorgemerkt)
    return Schluesselstand(eingetragen=False, vorgemerkt=vorgemerkt)


def eintragen(art: Art, wert: str) -> None:
    """Gilt sofort; ein früherer Eintrag der App ist damit ersetzt, die Datei der Einrichtung bleibt unberührt."""
    inhalt = _laden()
    inhalt.schluessel[art.value] = wert.strip()
    inhalt.vorgemerkt.pop(art.value, None)
    _sichern(inhalt)


def vormerken(art: Art, wert: str) -> None:
    """Gilt erst nach `uebernehmen`; bis dahin bleibt der bisherige."""
    inhalt = _laden()
    inhalt.vorgemerkt[art.value] = wert.strip()
    _sichern(inhalt)


def uebernehmen(art: Art) -> bool:
    inhalt = _laden()
    wert = inhalt.vorgemerkt.pop(art.value, "")
    if wert:
        inhalt.schluessel[art.value] = wert
    _sichern(inhalt)
    return bool(wert)


def verwerfen_vorgemerkt() -> None:
    inhalt = _laden()
    if inhalt.vorgemerkt:
        inhalt.vorgemerkt.clear()
        _sichern(inhalt)
