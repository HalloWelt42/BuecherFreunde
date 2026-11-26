"""Wege des Begleitmaterials (BF-81), Vertrag in docs/neubau/SCHNITTSTELLE.md (Abschnitt Begleitmaterial).

Das Material folgt dem Buch: wer das Buch nicht sieht (privat eines anderen, einem Kind nicht freigegeben), bekommt 404, wie für
ein Buch, das es nicht gibt (core/auth.py prüft das Buch im Pfad). Lesen und Öffnen braucht `lesen`, Hinzufügen, Umbenennen
und Funde entscheiden `bearbeiten`, Entfernen `loeschen` (stufen.json); Kinder lesen also nur. Hinzufügen läuft über die
Annahme (fortsetzbares Hochladen in Teilen, sichtbar bei den Aufträgen): die Teile gehen an `PATCH /api/annahme/{id}`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.app.ablage.wolke import WolkeFehler
from backend.app.annahme.dienst import annahme
from backend.app.api import vorhanden
from backend.app.core.auth import braucht
from backend.app.familie.modelle import Profil
from backend.app.material import dienst
from backend.app.material.erkennen import abgleich
from backend.app.material.modelle import Material, Materialfolgen, Materialliste, Materialstand, Umbenennen
from backend.app.material.textlauf import textlauf
from backend.app.models.grenzen import DATEINAME, GROESSTE_ZAHL, Nr

router = APIRouter(prefix="/api/books", tags=["Begleitmaterial"])
stand_router = APIRouter(prefix="/api/material", tags=["Begleitmaterial"])


class MaterialNeu(BaseModel):
    name: str = Field(min_length=1, max_length=DATEINAME)
    groesse: int = Field(ge=0, le=GROESSTE_ZAHL)
    sha256: str = Field("", pattern=r"^([0-9a-f]{64})?$")
    entpacken: bool = False                       # eine ZIP in einzelne Dateien auspacken (sonst bleibt sie eine Datei)


def _fehlt(f: Exception) -> HTTPException:
    return HTTPException(404, str(f))


@router.get("/{book_id}/material", response_model=Materialliste)
async def liste(book_id: Nr, _: Profil = Depends(braucht("lesen"))) -> Materialliste:
    await vorhanden.buch(book_id)
    return await dienst.liste(book_id)


@router.post("/{book_id}/material")
async def hinzufuegen(book_id: Nr, neu: MaterialNeu, _: Profil = Depends(braucht("bearbeiten"))):
    """Eine Datei anmelden; antwortet wie `POST /api/annahme` (die Aufnahme mit `teil_groesse`), danach die Teile hochladen.
    Mehrere Dateien: je Datei ein Aufruf."""
    await vorhanden.buch(book_id)
    return await annahme.anlegen(neu.name, neu.groesse, neu.sha256, material_fuer=book_id,
                                 auspacken=neu.entpacken and neu.name.lower().endswith(".zip"))


@router.patch("/{book_id}/material/{mid}", response_model=Material)
async def umbenennen(book_id: Nr, mid: str, neu: Umbenennen, _: Profil = Depends(braucht("bearbeiten"))) -> Material:
    try:
        return await dienst.umbenennen(book_id, mid, neu.name)
    except dienst.MaterialFehlt as f:
        raise _fehlt(f) from f
    except WolkeFehler as f:
        raise HTTPException(502, f"Nicht umbenannt: {f.meldung}") from f


@router.get("/{book_id}/material/{mid}/datei")
async def datei(book_id: Nr, mid: str, request: Request, herunterladen: bool = Query(False), _: Profil = Depends(braucht("lesen", inhalt=True))):
    """Die Datei zum Ansehen (inline, mit Bereichen) oder als Anhang; was nicht in der App öffnet, kommt immer als Anhang."""
    try:
        return await dienst.antwort(request, book_id, mid, herunterladen)
    except dienst.MaterialFehlt as f:
        raise _fehlt(f) from f


@router.get("/{book_id}/material/{mid}/folgen", response_model=Materialfolgen)
async def folgen(book_id: Nr, mid: str, _: Profil = Depends(braucht("loeschen"))) -> Materialfolgen:
    try:
        return await dienst.folgen(book_id, mid)
    except dienst.MaterialFehlt as f:
        raise _fehlt(f) from f


@router.delete("/{book_id}/material/{mid}")
async def entfernen(book_id: Nr, mid: str, stand: str = Query(max_length=64), _: Profil = Depends(braucht("loeschen"))):
    """Nur nach den Folgen: `stand` aus GET .../folgen; hat sich seitdem etwas geändert, 409."""
    try:
        await dienst.entfernen(book_id, mid, stand)
    except dienst.MaterialFehlt as f:
        raise _fehlt(f) from f
    except dienst.StandVeraltet as f:
        raise HTTPException(409, str(f)) from f
    except WolkeFehler as f:
        raise HTTPException(502, f"Nicht entfernt, das Material bleibt: {f.meldung}") from f
    return {"entfernt": True, "id": mid}


@router.post("/{book_id}/material/funde/{knoten}/annehmen", response_model=Material)
async def fund_annehmen(book_id: Nr, knoten: str, _: Profil = Depends(braucht("bearbeiten"))) -> Material:
    """Ja: die Datei neben dem Original wird Begleitmaterial (in der Kellerwolke Begleiter des Originals)."""
    try:
        return await dienst.fund_annehmen(book_id, knoten)
    except dienst.MaterialFehlt as f:
        raise _fehlt(f) from f
    except WolkeFehler as f:
        raise HTTPException(502, f"Nicht übernommen: {f.meldung}") from f


@router.post("/{book_id}/material/funde/{knoten}/ablehnen")
async def fund_ablehnen(book_id: Nr, knoten: str, _: Profil = Depends(braucht("bearbeiten"))):
    """Nein: die Datei bleibt, wo sie ist, und wird nicht wieder angeboten."""
    try:
        await dienst.fund_ablehnen(book_id, knoten)
    except dienst.MaterialFehlt as f:
        raise _fehlt(f) from f
    return {"abgelehnt": True, "knoten": knoten}


@stand_router.get("/stand", response_model=Materialstand)
async def stand(_: Profil = Depends(braucht("bearbeiten"))) -> Materialstand:
    """Die Aufträge des Materials: Abgleich neben den Originalen und Text für die Suche."""
    return Materialstand(abgleich=await abgleich.stand(), texte=await textlauf.stand())


@stand_router.post("/abgleich", response_model=Materialstand)
async def abgleichen(_: Profil = Depends(braucht("bearbeiten"))) -> Materialstand:
    """Jetzt neben den Originalen nachsehen (sonst im Takt); läuft er schon, bleibt es bei ihm."""
    if not abgleich.laeuft:
        abgleich.anstossen()
    return Materialstand(abgleich=await abgleich.stand(), texte=await textlauf.stand())
