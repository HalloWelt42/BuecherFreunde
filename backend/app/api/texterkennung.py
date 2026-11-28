"""Texterkennung aus dem Leser (BF-109): wer in der Textansicht auf einer Seite ohne Text steht, bittet um Vorrang für sie und die
nächsten Seiten, und fragt so auch nach, welche noch warten. Auf einer erkannten Seite bittet man um die Nachbesserung über die
Leitstelle und wählt danach je Seite, welche Fassung gilt (BF-118). Rechte wie das Lesen des Buchs: jedes Profil, nur Bücher,
die es sieht (das prüft die Anmeldung am Buch im Pfad). Die Arbeit tun die Aufträge "Texte erkennen" (texterkennung/auftrag.py)
und "Texte nachbessern" (texterkennung/nachbesserung.py)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.api import vorhanden
from backend.app.core.auth import braucht, profil
from backend.app.familie.modelle import Profil
from backend.app.models.grenzen import SEITEN_HOECHSTENS, Nr
from backend.app.texterkennung.auftrag import Vorrangstand, texterkennung
from backend.app.texterkennung.modelle import Herkunft
from backend.app.texterkennung.nachbesserung import Nachbesserungsantwort, nachbesserung

router = APIRouter(prefix="/api/books", tags=["Texterkennung"])
NUR_PDF = "Die Texterkennung gibt es nur für PDF"


class Vorrangbitte(BaseModel):
    seite: int = Field(ge=1, le=SEITEN_HOECHSTENS)       # die Dateiseite, auf der gelesen wird


@router.post("/{book_id}/texterkennung/vorrang", response_model=Vorrangstand)
async def vorrang(book_id: Nr, bitte: Vorrangbitte, _p: Profil = Depends(profil)) -> Vorrangstand:
    """Die Seite und die nächsten `TEXTERKENNUNG_VORRANG_SEITEN` zuerst erkennen; antwortet, ob die Erkennung bereit ist (sonst
    mit Grund) und welche dieser Seiten noch warten. Wiederholt (sanft, im wachsenden Abstand) ist es das Nachfragen."""
    buch = await vorhanden.buch(book_id, "id, file_format")
    if (buch["file_format"] or "").lower() != "pdf":
        raise HTTPException(status_code=422, detail=NUR_PDF)
    return await texterkennung.vorrang(book_id, bitte.seite)


class Nachbesserungsbitte(BaseModel):
    seite: int = Field(ge=1, le=SEITEN_HOECHSTENS)       # die Dateiseite, auf der gelesen wird; die nächsten kommen mit


class Fassungsbitte(BaseModel):
    seite: int = Field(ge=1, le=SEITEN_HOECHSTENS)
    gilt: Herkunft                                       # klassisch oder ki


async def _pdf(book_id: int) -> dict:
    buch = await vorhanden.buch(book_id, "id, hash, file_format")
    if (buch["file_format"] or "").lower() != "pdf":
        raise HTTPException(status_code=422, detail=NUR_PDF)
    return buch


@router.post("/{book_id}/texterkennung/nachbessern", response_model=Nachbesserungsantwort, dependencies=[Depends(braucht("ki"))])
async def nachbessern(book_id: Nr, bitte: Nachbesserungsbitte, _p: Profil = Depends(profil)) -> Nachbesserungsantwort:
    """Die erkannte Seite und die nächsten (`TEXTERKENNUNG_KI_SEITEN` zusammen) über die Leitstelle nachbessern, soweit sie noch
    keine Nachbesserung haben; antwortet, welche Seiten jetzt drankommen (ohne Leitstelle mit Grund). Nur Profile, die KI dürfen;
    die Fassung wählen darf jedes."""
    buch = await _pdf(book_id)
    return await nachbesserung.bitten(book_id, buch["hash"], bitte.seite)


@router.post("/{book_id}/texterkennung/fassung", status_code=204, response_model=None)
async def fassung(book_id: Nr, bitte: Fassungsbitte, _p: Profil = Depends(profil)) -> None:
    """Welche Fassung einer erkannten Seite gilt, die klassische oder die nachgebesserte; die andere bleibt gespeichert. Die Wahl
    gilt für Textansicht, Volltext, Suche und Vorlesen."""
    buch = await _pdf(book_id)
    if not await nachbesserung.waehlen(book_id, buch["hash"], bitte.seite, bitte.gilt):
        raise HTTPException(status_code=404, detail="Diese Fassung gibt es für die Seite nicht")
