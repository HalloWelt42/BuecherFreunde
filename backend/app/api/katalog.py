"""Katalog (BF-69, docs/neubau/KATALOG.md): Bereiche und Kategorien, Entwurf, Einordnen mit Regeln und KI, Vorschläge und
die alten Regale. Die Arbeit tut das Paket backend/app/katalog; hier stehen nur die Wege. Ansehen darf den Katalog, wer die
Fähigkeit `katalog` hat, pflegen nur, wer `einstellungen` hat; Zahlen und Bücher nur, wie das Profil sie sieht (BF-78)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.app.api.books import buecher_mit_nummern
from backend.app.core.auth import braucht, profil, sicht
from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht
from backend.app.katalog import alt, datei, einstellungen, entwurf, kategorien, vorschlaege
from backend.app.katalog.bestandslauf import bestandslauf
from backend.app.katalog.einordnen import KeinKatalog, einordner
from backend.app.katalog.modelle import (
    Abgelehnt, Ablehnen, AltesRegal, AltLoeschfolgen, Angenommen, Annehmen, Auch, Bereich, BereichAenderung, BereichEingabe,
    EinordnenStart, EntwurfStand, EntwurfWeg, Katalog, KatalogAntwort, Katalogeinstellungen, Kategorie, KategorieAenderung,
    KategorieEingabe, Laufstand, Loeschfolgen, OffeneJeKategorie, Treffer, Uebernahme, Uebernommen, Vorschlagsquelle,
)
from backend.app.models.book import BookListItem
from backend.app.models.grenzen import LISTENSEITE, Nr

router = APIRouter(prefix="/api/katalog", tags=["Katalog"], dependencies=[Depends(braucht("katalog"))])
EINSTELLUNGEN, KI = Depends(braucht("einstellungen")), Depends(braucht("ki"))
KEIN_ENTWURF = "Es gibt keinen Entwurf"
# Die Datei zum Sichern und Teilen: ohne Zahlen, die nur im Entwurf etwas bedeuten
OHNE_ZAHLEN = {"bereiche": {"__all__": {"anzahl": True, "kategorien": {"__all__": {"anzahl": True}}}}}


class Vorschlag(BaseModel):
    id: int
    buch: BookListItem                         # wie in der Bücherliste, mit Deckblattangaben
    kategorie_id: int
    quelle: Vorschlagsquelle
    gruende: list[str]
    sicherheit: int
    vorab: bool
    auch: list[Auch]


class Vorschlagsseite(BaseModel):
    gesamt: int
    vorschlaege: list[Vorschlag]


class Geloescht(BaseModel):
    geloescht: bool = True
    id: int


class Entfernt(BaseModel):
    entfernt: bool = True
    id: int
    buecher: int


def _fehler(f: Exception) -> HTTPException:
    if isinstance(f, (kategorien.Fehlt, alt.Fehlt)):
        return HTTPException(status_code=404, detail=str(f))
    return HTTPException(status_code=409, detail=str(f))


FEHLER = (kategorien.Fehlt, kategorien.Vergeben, kategorien.HatKategorien, alt.Fehlt, KeinKatalog)


# -- Katalog ----------------------------------------------------------------------------------------------------------------

@router.get("", response_model=KatalogAntwort)
async def katalog_lesen(s: Sicht = Depends(sicht)) -> KatalogAntwort:
    return await kategorien.katalog(s)


@router.get("/standard", response_model=Katalog, dependencies=[EINSTELLUNGEN])
async def standard_lesen() -> Katalog:
    """Der Standard-Katalog als Entwurf: Herkunft standard, ohne Zahlen."""
    return entwurf.gezeigt(entwurf.aus_standard())


@router.get("/datei", dependencies=[EINSTELLUNGEN])
async def datei_lesen() -> JSONResponse:
    """Der gültige Katalog als Datei im Format des Standards."""
    k = await kategorien.als_datei()
    return JSONResponse(k.model_dump(mode="json", exclude=OHNE_ZAHLEN),
                        headers={"Content-Disposition": 'attachment; filename="katalog.json"'})


@router.post("/datei", response_model=EntwurfStand, dependencies=[EINSTELLUNGEN])
async def datei_laden(k: Katalog) -> EntwurfStand:
    """Eine Katalog-Datei wird zum Entwurf; geprüft wie jede Eingabe (422 mit Feld und Grund)."""
    await bestandslauf.ersetzen()
    await entwurf.speichern(datei.herkunft_ergaenzen(k))
    return await entwurf_lesen()


# -- Entwurf ----------------------------------------------------------------------------------------------------------------

@router.get("/entwurf", response_model=EntwurfStand, dependencies=[EINSTELLUNGEN])
async def entwurf_lesen() -> EntwurfStand:
    e = await entwurf.lesen()
    return EntwurfStand(entwurf=entwurf.gezeigt(e) if e else None, lauf=await bestandslauf.zum_entwurf(e is not None))


@router.post("/entwurf", response_model=EntwurfStand, dependencies=[EINSTELLUNGEN])
async def entwurf_beginnen(w: EntwurfWeg) -> EntwurfStand:
    """Standard und leer gleich; "bestand" startet einen Lauf, der Entwurf kommt, wenn er fertig ist."""
    if w.weg == "bestand":
        return EntwurfStand(entwurf=None, lauf=await bestandslauf.beginnen())
    await bestandslauf.ersetzen()
    await entwurf.speichern(entwurf.aus_standard() if w.weg == "standard" else entwurf.leer())
    return await entwurf_lesen()


@router.put("/entwurf", response_model=EntwurfStand, dependencies=[EINSTELLUNGEN])
async def entwurf_aendern(k: Katalog) -> EntwurfStand:
    await bestandslauf.ersetzen()
    await entwurf.speichern(datei.herkunft_ergaenzen(k, zahlen_behalten=True))
    return await entwurf_lesen()


@router.post("/entwurf/annehmen", response_model=KatalogAntwort, dependencies=[EINSTELLUNGEN])
async def entwurf_annehmen(s: Sicht = Depends(sicht)) -> KatalogAntwort:
    """Schreibt den Katalog: gleicher Schlüssel ändert, sonst anlegen, gelöscht wird nichts. Danach gibt es keinen Entwurf."""
    e = await entwurf.lesen()
    if e is None:
        raise HTTPException(status_code=404, detail=KEIN_ENTWURF)
    await kategorien.annehmen(e)
    await entwurf.verwerfen()
    return await kategorien.katalog(s)


@router.delete("/entwurf", response_model=EntwurfStand, dependencies=[EINSTELLUNGEN])
async def entwurf_verwerfen() -> EntwurfStand:
    await bestandslauf.ersetzen()
    await entwurf.verwerfen()
    return await entwurf_lesen()


# -- Bereiche und Kategorien ------------------------------------------------------------------------------------------------

@router.post("/bereiche", response_model=Bereich, status_code=201, dependencies=[EINSTELLUNGEN])
async def bereich_anlegen(e: BereichEingabe) -> Bereich:
    try:
        return await kategorien.bereich_anlegen(e)
    except FEHLER as f:
        raise _fehler(f) from None


@router.patch("/bereiche/{nr}", response_model=Bereich, dependencies=[EINSTELLUNGEN])
async def bereich_aendern(nr: Nr, a: BereichAenderung) -> Bereich:
    try:
        return await kategorien.bereich_aendern(nr, a)
    except FEHLER as f:
        raise _fehler(f) from None


@router.get("/bereiche/{nr}/loeschfolgen", response_model=Loeschfolgen, dependencies=[EINSTELLUNGEN])
async def bereich_loeschfolgen(nr: Nr) -> Loeschfolgen:
    try:
        return await kategorien.loeschfolgen_bereich(nr)
    except FEHLER as f:
        raise _fehler(f) from None


@router.delete("/bereiche/{nr}", response_model=Geloescht, dependencies=[EINSTELLUNGEN])
async def bereich_loeschen(nr: Nr) -> Geloescht:
    """Nur nach den Folgen und nur ohne Kategorien (409)."""
    try:
        await kategorien.bereich_loeschen(nr)
    except FEHLER as f:
        raise _fehler(f) from None
    return Geloescht(id=nr)


@router.post("/kategorien", response_model=Kategorie, status_code=201, dependencies=[EINSTELLUNGEN])
async def kategorie_anlegen(e: KategorieEingabe) -> Kategorie:
    try:
        return await kategorien.kategorie_anlegen(e)
    except FEHLER as f:
        raise _fehler(f) from None


@router.patch("/kategorien/{nr}", response_model=Kategorie, dependencies=[EINSTELLUNGEN])
async def kategorie_aendern(nr: Nr, a: KategorieAenderung) -> Kategorie:
    try:
        return await kategorien.kategorie_aendern(nr, a)
    except FEHLER as f:
        raise _fehler(f) from None


@router.get("/kategorien/{nr}/loeschfolgen", response_model=Loeschfolgen, dependencies=[EINSTELLUNGEN])
async def kategorie_loeschfolgen(nr: Nr) -> Loeschfolgen:
    try:
        return await kategorien.loeschfolgen_kategorie(nr)
    except FEHLER as f:
        raise _fehler(f) from None


@router.delete("/kategorien/{nr}", response_model=Geloescht, dependencies=[EINSTELLUNGEN])
async def kategorie_loeschen(nr: Nr) -> Geloescht:
    """Nur nach den Folgen: die Bücher verlieren die Zuordnung, die Vorschläge fallen weg, die Bücher bleiben."""
    try:
        await kategorien.kategorie_loeschen(nr)
    except FEHLER as f:
        raise _fehler(f) from None
    return Geloescht(id=nr)


@router.get("/kategorien/{nr}/treffer", response_model=Treffer, dependencies=[EINSTELLUNGEN])
async def kategorie_treffer(nr: Nr) -> Treffer:
    try:
        return await kategorien.treffer(nr)
    except FEHLER as f:
        raise _fehler(f) from None


# -- alte Regale ------------------------------------------------------------------------------------------------------------

@router.get("/alt", response_model=list[AltesRegal], dependencies=[EINSTELLUNGEN])
async def alte_regale() -> list[AltesRegal]:
    return await alt.liste()


@router.post("/alt/uebernehmen", response_model=Uebernommen, dependencies=[EINSTELLUNGEN])
async def alte_uebernehmen(u: Uebernahme, p: Profil = Depends(profil)) -> Uebernommen:
    """In eine Kategorie oder als Etikett an die Bücher (Etiketten des Profils); das alte Regal bleibt stehen."""
    try:
        return Uebernommen(buecher=await alt.uebernehmen(u.ids, u.ziel, p.id))
    except FEHLER as f:
        raise _fehler(f) from None


@router.get("/alt/{nr}/loeschfolgen", response_model=AltLoeschfolgen, dependencies=[EINSTELLUNGEN])
async def altes_loeschfolgen(nr: Nr) -> AltLoeschfolgen:
    try:
        return await alt.loeschfolgen(nr)
    except FEHLER as f:
        raise _fehler(f) from None


@router.delete("/alt/{nr}", response_model=Entfernt, dependencies=[EINSTELLUNGEN])
async def altes_entfernen(nr: Nr) -> Entfernt:
    """Nur nach den Folgen: das Regal fort, die Bücher bleiben."""
    try:
        return Entfernt(id=nr, buecher=await alt.entfernen(nr))
    except FEHLER as f:
        raise _fehler(f) from None


# -- Einordnen --------------------------------------------------------------------------------------------------------------

@router.post("/einordnen", response_model=Laufstand, dependencies=[EINSTELLUNGEN, KI])
async def einordnen(start: EinordnenStart | None = None) -> Laufstand:
    """Startet den Lauf; läuft schon einer oder ist er pausiert, bleibt es bei ihm. Ohne Katalog: 409."""
    try:
        return await einordner.beginnen((start or EinordnenStart()).stapel)
    except FEHLER as f:
        raise _fehler(f) from None


@router.get("/einordnen/stand", response_model=Laufstand, dependencies=[EINSTELLUNGEN])
async def einordnen_stand() -> Laufstand:
    return await einordner.stand()


@router.post("/einordnen/pause", response_model=Laufstand, dependencies=[EINSTELLUNGEN, KI])
async def einordnen_pause() -> Laufstand:
    return await einordner.pausieren()


@router.post("/einordnen/fortsetzen", response_model=Laufstand, dependencies=[EINSTELLUNGEN, KI])
async def einordnen_fortsetzen() -> Laufstand:
    return await einordner.fortsetzen()


# -- Vorschläge -------------------------------------------------------------------------------------------------------------

@router.get("/vorschlaege/uebersicht", response_model=list[OffeneJeKategorie], dependencies=[EINSTELLUNGEN])
async def vorschlaege_uebersicht() -> list[OffeneJeKategorie]:
    return await vorschlaege.uebersicht()


@router.get("/vorschlaege", response_model=Vorschlagsseite, dependencies=[EINSTELLUNGEN])
async def vorschlaege_lesen(kategorie: Nr | None = Query(None), seite: int = Query(1, ge=1, le=LISTENSEITE),
                            pro_seite: int = Query(50, ge=1, le=100), p: Profil = Depends(profil)) -> Vorschlagsseite:
    """Offene Vorschläge, die sichersten zuerst; mit `kategorie` nur die einer Kategorie (404, wenn es sie nicht gibt)."""
    if kategorie is not None:
        try:
            await kategorien.kategorie(kategorie)
        except FEHLER as f:
            raise _fehler(f) from None
    gesamt, offen = await vorschlaege.seite(kategorie, seite, pro_seite, (await einstellungen.lesen()).sicher_ab)
    buecher = await buecher_mit_nummern([v.buch_id for v in offen], p)            # was das Profil nicht sieht, fehlt
    return Vorschlagsseite(gesamt=gesamt, vorschlaege=[Vorschlag(buch=buecher[v.buch_id], **v.model_dump(exclude={"buch_id"}))
                                                       for v in offen if v.buch_id in buecher])


@router.post("/vorschlaege/annehmen", response_model=Angenommen, dependencies=[EINSTELLUNGEN])
async def vorschlaege_annehmen(a: Annehmen) -> Angenommen:
    """Die genannten offenen oder alle offenen einer Kategorie; schreibt book_categories."""
    return Angenommen(angenommen=await vorschlaege.annehmen(a.ids, a.kategorie))


@router.post("/vorschlaege/ablehnen", response_model=Abgelehnt, dependencies=[EINSTELLUNGEN])
async def vorschlaege_ablehnen(a: Ablehnen) -> Abgelehnt:
    """Abgelehnte Vorschläge kommen nie wieder."""
    return Abgelehnt(abgelehnt=await vorschlaege.ablehnen(a.ids))


# -- Einstellungen ----------------------------------------------------------------------------------------------------------

@router.get("/einstellungen", response_model=Katalogeinstellungen, dependencies=[EINSTELLUNGEN])
async def einstellungen_lesen() -> Katalogeinstellungen:
    return await einstellungen.lesen()


@router.put("/einstellungen", response_model=Katalogeinstellungen, dependencies=[EINSTELLUNGEN])
async def einstellungen_schreiben(e: Katalogeinstellungen) -> Katalogeinstellungen:
    return await einstellungen.schreiben(e)
