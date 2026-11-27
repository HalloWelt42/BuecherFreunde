"""Das Programm der klassischen Erkennung (Tesseract) als eigener Prozess: ob es auf dem Gerät ist, in welcher Fassung und mit
welchen Sprachdaten, und die Erkennung eines Seitenbilds als TSV.

Das Programm heißt in `TEXTERKENNUNG_PROGRAMM` (Name im Suchpfad oder Pfad). Es bekommt das Bild über die Standardeingabe, rechnet
mit höchstens `TEXTERKENNUNG_KERNE` Kernen (OMP_THREAD_LIMIT) und darf je Seite `TEXTERKENNUNG_FRIST_S` brauchen; danach wird es
beendet. Fehlt es oder fehlen Sprachdaten, sagt `bereitschaft` warum, in Worten für die Liste der Aufträge."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass

from pydantic import BaseModel

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.texterkennung")
WERKZEUG = "tesseract"
SEITENTEILUNG = "3"             # --psm 3: Spalten, Blöcke, Absätze und Zeilen gliedert das Programm selbst
PRUEFUNG_GILT_S = 300.0         # so lange gilt eine Prüfung, ob das Programm da ist
FRAGE_FRIST_S = 15.0            # so lange darf die Frage nach Fassung und Sprachdaten dauern
NICHT_EINGERICHTET = "Die Texterkennung ist auf diesem Gerät nicht eingerichtet"
OHNE_SPRACHEN = "Der Texterkennung fehlen Sprachdaten: {fehlen}"
FASSUNG = re.compile(r"(\d+\.\d+(?:\.\d+)?)")


class Bereitschaft(BaseModel):
    bereit: bool
    grund: str = ""
    werkzeug: str = WERKZEUG
    fassung: str = ""
    programm: str = ""                          # der gefundene Pfad


class Erkennungsfehler(Exception):
    """Diese Seite ließ sich nicht erkennen; der Grund steht in Worten da."""


class WerkzeugFehlt(Erkennungsfehler):
    """Das Programm ist (nicht mehr) da: keine Frage der Seite, die Erkennung ruht."""


@dataclass
class _Gemerkt:
    schluessel: tuple[str, str]
    seit: float
    stand: Bereitschaft


_gemerkt: _Gemerkt | None = None


def vergessen() -> None:
    """Die nächste Frage prüft neu (nach einer Änderung der Einstellungen, in Tests)."""
    global _gemerkt
    _gemerkt = None


async def _fragen(programm: str, *argumente: str) -> str:
    prozess = await asyncio.create_subprocess_exec(programm, *argumente, stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.STDOUT)
    try:
        aus, _ = await asyncio.wait_for(prozess.communicate(), FRAGE_FRIST_S)
    except TimeoutError:
        prozess.kill()
        await prozess.wait()
        raise
    return aus.decode("utf-8", errors="replace")


def _sprachen_der_liste(ausgabe: str) -> set[str]:
    """Die Sprachdaten aus `--list-langs`: jede Zeile nach der Überschrift ist ein Name."""
    zeilen = [z.strip() for z in ausgabe.splitlines() if z.strip()]
    return {z for z in zeilen[1:] if " " not in z}


async def _pruefen(programm_name: str, sprachen: str) -> Bereitschaft:
    programm = shutil.which(programm_name)
    if programm is None:
        return Bereitschaft(bereit=False, grund=NICHT_EINGERICHTET)
    try:
        fassung = FASSUNG.search(await _fragen(programm, "--version"))
        vorhanden = _sprachen_der_liste(await _fragen(programm, "--list-langs"))
    except (OSError, TimeoutError):
        return Bereitschaft(bereit=False, grund=NICHT_EINGERICHTET)
    fehlen = [s for s in sprachen.split("+") if s not in vorhanden]
    if fehlen:
        return Bereitschaft(bereit=False, grund=OHNE_SPRACHEN.format(fehlen=", ".join(fehlen)), programm=programm,
                            fassung=fassung.group(1) if fassung else "")
    return Bereitschaft(bereit=True, programm=programm, fassung=fassung.group(1) if fassung else "")


async def bereitschaft() -> Bereitschaft:
    """Ist die Erkennung auf diesem Gerät bereit? Einmal geprüft, gilt die Antwort PRUEFUNG_GILT_S lang (je Programm und
    Sprachen)."""
    global _gemerkt
    schluessel = (settings.texterkennung_programm, settings.texterkennung_sprachen)
    if _gemerkt is None or _gemerkt.schluessel != schluessel or time.monotonic() - _gemerkt.seit > PRUEFUNG_GILT_S:
        _gemerkt = _Gemerkt(schluessel, time.monotonic(), await _pruefen(*schluessel))
    return _gemerkt.stand


def _umgebung() -> dict[str, str]:
    return {**os.environ, "OMP_THREAD_LIMIT": str(settings.texterkennung_kerne)}


async def tsv(bild: bytes, dpi: int) -> str:
    """Ein Seitenbild (PNG) erkennen; die Ausgabe als TSV (Wörter mit Lage, Sicherheit, Block, Absatz und Zeile). Wirft
    `WerkzeugFehlt`, wenn das Programm nicht da ist, und `Erkennungsfehler` mit Grund, wenn diese Seite scheitert."""
    stand = await bereitschaft()
    if not stand.bereit:
        raise WerkzeugFehlt(stand.grund)
    frist = settings.texterkennung_frist_s
    try:
        prozess = await asyncio.create_subprocess_exec(
            stand.programm, "stdin", "stdout", "--dpi", str(dpi), "-l", settings.texterkennung_sprachen, "--psm", SEITENTEILUNG,
            "tsv", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=_umgebung())
    except OSError as f:
        vergessen()
        raise WerkzeugFehlt(NICHT_EINGERICHTET) from f
    try:
        aus, fehler = await asyncio.wait_for(prozess.communicate(bild), frist)
    except (TimeoutError, asyncio.CancelledError) as f:
        prozess.kill()
        await prozess.wait()
        if isinstance(f, asyncio.CancelledError):
            raise
        raise Erkennungsfehler(f"Die Erkennung der Seite dauerte länger als {frist:g} s") from f
    if prozess.returncode != 0:
        logger.warning("Texterkennung mit Code %s beendet: %s", prozess.returncode,
                       fehler.decode("utf-8", errors="replace").strip()[-500:])
        raise Erkennungsfehler(f"Die Texterkennung brach ab (Code {prozess.returncode})")
    return aus.decode("utf-8", errors="replace")
