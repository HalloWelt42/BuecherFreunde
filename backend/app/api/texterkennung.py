"""Texterkennung aus dem Leser (BF-109): wer in der Textansicht auf einer Seite ohne Text steht, bittet um Vorrang für sie und die
nächsten Seiten, und fragt so auch nach, welche noch warten. Rechte wie das Lesen des Buchs: jedes Profil, nur Bücher, die es
sieht (das prüft die Anmeldung am Buch im Pfad). Die Arbeit tut der Auftrag "Texte erkennen" (texterkennung/auftrag.py)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.api import vorhanden
from backend.app.core.auth import profil
from backend.app.familie.modelle import Profil
from backend.app.models.grenzen import SEITEN_HOECHSTENS, Nr
from backend.app.texterkennung.auftrag import Vorrangstand, texterkennung

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
