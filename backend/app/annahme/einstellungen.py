"""Einstellungen fürs Hinzufügen (BF-80) in `app_settings`, Weg `GET`/`PUT /api/annahme/einstellungen` (Fähigkeit
einstellungen): je Weg "erst bestätigen" und die Grenzen für ZIP. Solange nichts Gültiges gemerkt ist, gilt die Vorgabe aus der
Einrichtung (`core/config.py`, etwa `BESTAETIGEN_EINGANGSORDNER`, `ZIP_DATEIEN_HOECHSTENS`).

Wege: Hochladen im Browser hält immer vor dem Regal (fest), der Eingangsordner und Ordner auf dem Gerät (Einlese-Ordner und
externe Sammlung, `WEG_DER_QUELLE`) nur, wenn eingeschaltet; gemeinfreie Bücher wählt man einzeln und sie halten nie."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ValidationError

from backend.app.core import einstellungen
from backend.app.core.config import settings
from backend.app.models.grenzen import ZipDateien, ZipMb, ZipTiefe, ZipVerhaeltnis

Weg = Literal["hochladen", "eingangsordner", "ordner"]
WEG_DER_QUELLE: dict[str, Weg] = {"hochladen": "hochladen", "eingangsordner": "eingangsordner", "ordner": "ordner", "extern": "ordner"}


class Bestaetigen(BaseModel):
    hochladen: Literal[True] = True               # fest: Hochladen im Browser läuft immer über die Vorschau
    eingangsordner: bool
    ordner: bool                                  # Einlese-Ordner und externe Sammlung auf dem Gerät


class Zipgrenzen(BaseModel):
    """Gegen ZIP-Bomben und Versehen; wer darüber liegt, wird nicht ausgepackt (ganz oder der eine Eintrag)."""

    dateien: ZipDateien                           # Einträge der ZIP
    datei_mb: ZipMb                               # ein Eintrag ausgepackt
    gesamt_mb: ZipMb                              # alle zusammen ausgepackt
    tiefe: ZipTiefe                               # Ordner in der ZIP
    verhaeltnis: ZipVerhaeltnis                   # ausgepackt durch gepackt, je Eintrag

    @property
    def datei_bytes(self) -> int:
        return self.datei_mb * 1024 * 1024

    @property
    def gesamt_bytes(self) -> int:
        return self.gesamt_mb * 1024 * 1024


class Hinzufuegen(BaseModel):
    bestaetigen: Bestaetigen
    zip: Zipgrenzen


# Feld -> Schlüssel in app_settings
SCHLUESSEL = {("bestaetigen", "eingangsordner"): "hinzufuegen_bestaetigen_eingangsordner",
              ("bestaetigen", "ordner"): "hinzufuegen_bestaetigen_ordner",
              ("zip", "dateien"): "hinzufuegen_zip_dateien", ("zip", "datei_mb"): "hinzufuegen_zip_datei_mb",
              ("zip", "gesamt_mb"): "hinzufuegen_zip_gesamt_mb", ("zip", "tiefe"): "hinzufuegen_zip_tiefe",
              ("zip", "verhaeltnis"): "hinzufuegen_zip_verhaeltnis"}


def vorgaben() -> Hinzufuegen:
    return Hinzufuegen(bestaetigen=Bestaetigen(eingangsordner=settings.bestaetigen_eingangsordner, ordner=settings.bestaetigen_ordner),
                       zip=Zipgrenzen(dateien=settings.zip_dateien_hoechstens, datei_mb=settings.zip_datei_mb_hoechstens,
                                      gesamt_mb=settings.zip_gesamt_mb_hoechstens, tiefe=settings.zip_tiefe_hoechstens,
                                      verhaeltnis=settings.zip_verhaeltnis_hoechstens))


def _wert(text: str) -> object:
    return {"true": True, "false": False}.get(text, text)


async def lesen() -> Hinzufuegen:
    """Je Feld der gemerkte Wert, wenn er gilt, sonst die Vorgabe."""
    werte = vorgaben().model_dump()
    for (teil, feld), schluessel in SCHLUESSEL.items():
        gemerkt = await einstellungen.lesen(schluessel)
        if gemerkt is None:
            continue
        probe = {**werte, teil: {**werte[teil], feld: _wert(gemerkt)}}
        try:
            werte = Hinzufuegen.model_validate(probe).model_dump()
        except ValidationError:
            pass                                       # ungültig gemerkt: die Vorgabe gilt
    return Hinzufuegen(**werte)


async def schreiben(neu: Hinzufuegen) -> Hinzufuegen:
    for (teil, feld), schluessel in SCHLUESSEL.items():
        wert = getattr(getattr(neu, teil), feld)
        await einstellungen.schreiben(schluessel, str(wert).lower() if isinstance(wert, bool) else str(wert))
    return await lesen()


async def halten(quelle: str) -> bool:
    """Wartet eine Aufnahme dieser Quelle vor dem Regal auf die Bestätigung?"""
    weg = WEG_DER_QUELLE.get(quelle)
    if weg is None:
        return False
    return weg == "hochladen" or getattr((await lesen()).bestaetigen, weg)
