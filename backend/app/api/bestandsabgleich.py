"""Abgleich mit dem Bestand (BF-119): was eine fremde Seite anbietet, gegen die Bibliothek des Profils, für die Erweiterung im
Browser. Nur lesend; verglichen wird mit den Büchern, die das Profil sieht."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.bestandsabgleich import dienst
from backend.app.bestandsabgleich.modelle import Abgleichantwort, Abgleichfrage, Suchantwort, Suchfrage
from backend.app.core.auth import profil, sicht
from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht

router = APIRouter(prefix="/api/bestandsabgleich", tags=["Abgleich mit dem Bestand"])


@router.post("", response_model=Abgleichantwort)
async def abgleichen(frage: Abgleichfrage, p: Profil = Depends(profil), s: Sicht = Depends(sicht)) -> Abgleichantwort:
    """Alle Bücher einer Seite auf einmal; zurück kommen nur die mit Treffern, je Buch die besten zuerst."""
    return await dienst.abgleichen(frage, s, p)


@router.post("/suche", response_model=Suchantwort)
async def suchen(frage: Suchfrage, p: Profil = Depends(profil), s: Sicht = Depends(sicht)) -> Suchantwort:
    """Freier Text, etwa markiert auf einer Seite: ein Titel oder ein Name."""
    return await dienst.suchen(frage, s, p)
