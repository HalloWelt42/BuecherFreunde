"""ISBN im Buch (BF-111): Kandidaten mit Fundstellen und Stufe, Prüfen bei den Quellen, ISBN zur Wahl aus dem Lauf "ISBN"."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.api.books import buecher_mit_nummern
from backend.app.core.auth import braucht
from backend.app.familie.modelle import Profil
from backend.app.isbnsuche import dienst, wahl
from backend.app.isbnsuche.modelle import Isbnpruefung, Isbnsuche, Kandidat, Pruefen, Wahlbuecher, Wahlergebnis
from backend.app.models.book import BookListItem
from backend.app.models.grenzen import Index, Nr

router = APIRouter(prefix="/api/books", tags=["ISBN im Buch"])
WAHL_HOECHSTENS = 500                # so viele Bücher zur Wahl liefert eine Seite höchstens


class Wahlzeile(BaseModel):
    """Ein Buch mit ISBN zur Wahl: der beste Kandidat und wie viele es sonst noch gibt."""

    buch: BookListItem
    kandidat: Kandidat
    weitere: int


class Wahlseite(BaseModel):
    gesamt: int
    zeilen: list[Wahlzeile]


# Die Wege unter /rescan zuerst: sonst nähme /{book_id}/isbn-wahl "rescan" als Nummer eines Buchs
@router.get("/rescan/isbn-wahl", response_model=Wahlseite)
async def isbn_wahl(anzahl: int = Query(3, ge=1, le=WAHL_HOECHSTENS), ab: Index = Query(0), p: Profil = Depends(braucht("einstellungen"))) -> Wahlseite:
    """Bücher mit ISBN zur Wahl, je Buch der beste Kandidat; die besten Stufen zuerst. Was das Profil nicht sieht, fehlt."""
    gesamt, liste = await wahl.seite(anzahl, ab)
    buecher = await buecher_mit_nummern([w.buch_id for w in liste], p)
    return Wahlseite(gesamt=gesamt, zeilen=[Wahlzeile(buch=buecher[w.buch_id], kandidat=w.kandidat, weitere=w.weitere) for w in liste if w.buch_id in buecher])


@router.post("/rescan/isbn-wahl/annehmen", response_model=Wahlergebnis, dependencies=[Depends(braucht("einstellungen"))])
async def isbn_wahl_annehmen(auswahl: Wahlbuecher) -> Wahlergebnis:
    """Je Buch den besten Kandidaten als ISBN eintragen."""
    return Wahlergebnis(betroffen=await wahl.annehmen(auswahl.buecher))


@router.post("/rescan/isbn-wahl/ablehnen", response_model=Wahlergebnis, dependencies=[Depends(braucht("einstellungen"))])
async def isbn_wahl_ablehnen(auswahl: Wahlbuecher) -> Wahlergebnis:
    """Alle Kandidaten dieser Bücher ablehnen; ein neuer Lauf schlägt sie nicht wieder vor."""
    return Wahlergebnis(betroffen=await wahl.ablehnen(auswahl.buecher))


@router.post("/{book_id}/isbn-scan", response_model=Isbnsuche)
async def isbn_scan(book_id: Nr, _p: Profil = Depends(braucht("bearbeiten"))) -> Isbnsuche:
    """Alle ISBN im Text des Buchs, je ISBN ein Kandidat mit Fundstellen und Stufe aus dem Text, in der Rangfolge. Fehlt der
    Volltext, wird er zuerst aus der Datei gelesen. Gefragt wird keine Quelle."""
    try:
        return await dienst.im_buch(book_id)
    except dienst.KeinBuch as f:
        raise HTTPException(status_code=404, detail=str(f)) from None


@router.post("/{book_id}/isbn-pruefen", response_model=Isbnpruefung)
async def isbn_pruefen(book_id: Nr, angabe: Pruefen, _p: Profil = Depends(braucht("bearbeiten"))) -> Isbnpruefung:
    """Eine ISBN bei den Quellen, der Reihe nach bis zum ersten Fund, und ihre Stufe gegen Titel und Autor des Buchs."""
    try:
        return await dienst.pruefe(book_id, angabe.isbn)
    except dienst.KeinBuch as f:
        raise HTTPException(status_code=404, detail=str(f)) from None
    except dienst.KeineIsbn as f:
        raise HTTPException(status_code=422, detail=str(f)) from None


@router.get("/{book_id}/isbn-wahl", response_model=list[Kandidat])
async def isbn_wahl_des_buchs(book_id: Nr, _p: Profil = Depends(braucht("bearbeiten"))) -> list[Kandidat]:
    """Die ISBN zur Wahl dieses Buchs aus dem Lauf, in der Rangfolge; leer, wenn es keine gibt oder das Buch eine ISBN hat."""
    return await wahl.fuer_buch(book_id)
