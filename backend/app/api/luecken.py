"""Wege der Lücken in Sammlungen (BF-75): je Sammlung die Reihen je Sprache mit fehlenden Bänden, Zahl der Bände und Platzhalter
einstellen, Ausblenden und Zurückholen, neu nachschlagen; dazu die Suchadresse in den Einstellungen und der Stand des Auftrags.

Alles braucht die Fähigkeit `luecken` (familie/stufen.json: Erwachsene; ein Kind nur, wenn seine Stufe sie nennt), Ändern dazu
`bearbeiten`, die Suchadresse setzen `einstellungen`. Gezeigt wird nur, was das Profil sieht (luecken/dienst.py)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.books import buecher_mit_nummern
from backend.app.core.auth import braucht
from backend.app.core.database import db
from backend.app.familie.modelle import Profil
from backend.app.luecken import dienst, speicher, suchadresse
from backend.app.luecken.modelle import (
    Ausblenden, LueckenAendern, Nachschlagestand, Platzhalter, Probe, Sammlungsluecken, Suchadresse, Suchadresseinstellungen, Zurueckholen,
)
from backend.app.luecken.nachschlagen import nachschlagen
from backend.app.models.grenzen import Nr
from backend.app.quellen.sprache import kuerzel

router = APIRouter(tags=["Lücken"])
LUECKEN = braucht("luecken")
AENDERN = [Depends(braucht("bearbeiten"))]
NICHT_AUSGEBLENDET = "Diese Lücke ist nicht ausgeblendet"


async def _ansicht(sammlung_id: int, p: Profil) -> Sammlungsluecken:
    """Die Lücken mit den Büchern, wie sie in der Liste stehen; stößt das Nachschlagen an, wenn etwas offen ist."""
    try:
        a = await dienst.ansicht(sammlung_id, p)
    except speicher.SammlungFehlt as f:
        raise HTTPException(status_code=404, detail=str(f)) from None
    buecher = await buecher_mit_nummern([e.buch_id for r in a.reihen for e in r.eintraege if e.buch_id], p)
    for r in a.reihen:
        for e in r.eintraege:
            e.buch = buecher.get(e.buch_id) if e.buch_id else None
    if any(r.nachschlagen.stand == "offen" for r in a.reihen):
        await db.commit()                              # erst buchen, dann anstoßen: der Auftrag liest über seine eigene Verbindung
        nachschlagen.anstossen()
    return a


async def _vorhanden(sammlung_id: int) -> None:
    try:
        await speicher.sammlung(sammlung_id)
    except speicher.SammlungFehlt as f:
        raise HTTPException(status_code=404, detail=str(f)) from None


@router.get("/api/collections/{collection_id}/luecken", response_model=Sammlungsluecken)
async def hole_luecken(collection_id: Nr, p: Profil = Depends(LUECKEN)) -> Sammlungsluecken:
    return await _ansicht(collection_id, p)


@router.patch("/api/collections/{collection_id}/luecken", response_model=Sammlungsluecken, dependencies=AENDERN)
async def aendere_luecken(collection_id: Nr, data: LueckenAendern, p: Profil = Depends(LUECKEN)) -> Sammlungsluecken:
    """Platzhalter an oder aus und die Zahl der Bände je Sprache (aus der Quelle, eigene, keine)."""
    await _vorhanden(collection_id)
    if data.an is not None:
        await speicher.an_setzen(collection_id, data.an)
    for g in data.gesamt:
        await speicher.wahl_setzen(collection_id, kuerzel(g.sprache), g.wahl, g.zahl)
    return await _ansicht(collection_id, p)


@router.post("/api/collections/{collection_id}/luecken/ausblenden", response_model=Sammlungsluecken, dependencies=AENDERN)
async def blende_aus(collection_id: Nr, data: Ausblenden, p: Profil = Depends(LUECKEN)) -> Sammlungsluecken:
    """"Gibt es nicht" oder "Brauche ich nicht": der Platzhalter verschwindet, zurückholbar."""
    await _vorhanden(collection_id)
    await speicher.ausblenden(collection_id, kuerzel(data.sprache), data.nummer, data.grund)
    return await _ansicht(collection_id, p)


@router.post("/api/collections/{collection_id}/luecken/zurueckholen", response_model=Sammlungsluecken, dependencies=AENDERN)
async def hole_zurueck(collection_id: Nr, data: Zurueckholen, p: Profil = Depends(LUECKEN)) -> Sammlungsluecken:
    await _vorhanden(collection_id)
    if not await speicher.zurueckholen(collection_id, kuerzel(data.sprache), data.nummer):
        raise HTTPException(status_code=404, detail=NICHT_AUSGEBLENDET)
    return await _ansicht(collection_id, p)


@router.post("/api/collections/{collection_id}/luecken/nachschlagen", response_model=Sammlungsluecken, dependencies=AENDERN)
async def schlage_neu_nach(collection_id: Nr, p: Profil = Depends(LUECKEN)) -> Sammlungsluecken:
    """Auf Wunsch noch einmal fragen, etwa nach einem Fehler oder einem neuen Namen; eine gleiche Frage beantwortet der Vorrat."""
    await _vorhanden(collection_id)
    await speicher.neu_nachschlagen(collection_id)
    return await _ansicht(collection_id, p)


# -- Für die ganze App --------------------------------------------------------------------------------------------------------

async def _einstellungen() -> Suchadresseinstellungen:
    return Suchadresseinstellungen(suchadresse=await suchadresse.lesen(),
                                   platzhalter=[Platzhalter(name=n, bedeutung=b) for n, b in suchadresse.PLATZHALTER.items()])


@router.get("/api/luecken/einstellungen", response_model=Suchadresseinstellungen)
async def hole_einstellungen(_: Profil = Depends(LUECKEN)) -> Suchadresseinstellungen:
    return await _einstellungen()


@router.put("/api/luecken/einstellungen", response_model=Suchadresseinstellungen, dependencies=[Depends(LUECKEN)])
async def setze_einstellungen(data: Suchadresse, _: Profil = Depends(braucht("einstellungen"))) -> Suchadresseinstellungen:
    await suchadresse.schreiben(data.suchadresse)
    return await _einstellungen()


@router.post("/api/luecken/suchadresse/probe", response_model=Probe)
async def probiere_suchadresse(data: Suchadresse, p: Profil = Depends(LUECKEN)) -> Probe:
    """Die fertige Adresse für einen fehlenden Band, den das Profil sieht, mit dieser Vorlage (noch nicht gemerkt)."""
    gefunden = await dienst.erste_luecke(p, data.suchadresse)
    if gefunden is None:
        return Probe(adresse=None)
    sammlung, luecke = gefunden
    return Probe(adresse=luecke.suchadresse, sammlung=sammlung, luecke=luecke)


@router.get("/api/luecken/stand", response_model=Nachschlagestand)
async def stand(_: Profil = Depends(LUECKEN)) -> Nachschlagestand:
    return await nachschlagen.stand()
