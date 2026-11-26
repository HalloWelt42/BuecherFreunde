"""Einstellungen des Katalogs (BF-69) in `app_settings`; solange dort nichts Gültiges steht, gilt die Vorgabe aus der
Einrichtung (`core/config.py`, etwa `KATALOG_STAPEL`)."""

from __future__ import annotations

from pydantic import ValidationError

from backend.app.core import einstellungen
from backend.app.core.config import settings
from backend.app.katalog.modelle import Katalogeinstellungen

# Feld -> Schlüssel in app_settings
SCHLUESSEL = {"stapel": "katalog_stapel", "ki_je_anfrage": "katalog_ki_je_anfrage", "sicher_ab": "katalog_sicher_ab",
              "teilen_ab": "katalog_teilen_ab"}


def vorgaben() -> Katalogeinstellungen:
    return Katalogeinstellungen(stapel=settings.katalog_stapel, ki_je_anfrage=settings.katalog_ki_je_anfrage,
                                sicher_ab=settings.katalog_sicher_ab, teilen_ab=settings.katalog_teilen_ab)


async def lesen() -> Katalogeinstellungen:
    """Je Feld der gemerkte Wert, wenn er gilt, sonst die Vorgabe."""
    werte = vorgaben().model_dump()
    for feld, schluessel in SCHLUESSEL.items():
        gemerkt = await einstellungen.lesen(schluessel)
        if gemerkt is None:
            continue
        try:
            werte[feld] = Katalogeinstellungen.model_validate({**werte, feld: gemerkt}).model_dump()[feld]
        except ValidationError:
            pass                                       # ungültig gemerkt: die Vorgabe gilt
    return Katalogeinstellungen(**werte)


async def schreiben(neu: Katalogeinstellungen) -> Katalogeinstellungen:
    for feld, schluessel in SCHLUESSEL.items():
        await einstellungen.schreiben(schluessel, str(getattr(neu, feld)))
    return await lesen()
