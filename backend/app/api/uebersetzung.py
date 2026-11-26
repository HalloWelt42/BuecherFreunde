"""Bücher übersetzen (BF-71): Fassungen eines Buchs, ihr Lauf, der Prüfbericht, Blöcke von Hand und die Begriffsliste
(docs/neubau/UEBERSETZUNG.md, Schnittstelle). Jede Änderung wird gebucht, bevor der Lauf angestoßen wird, damit er sie sieht."""

from __future__ import annotations

import asyncio
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from backend.app.core.auth import braucht, profil, sicht, verify_token, verify_token_inhalt
from backend.app.familie import sichtbar
from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht
from backend.app.core.database import db
from backend.app.models.fassung import (
    BegriffAenderung, BegriffEintrag, BegriffNeu, Bericht, BlockAktion, BlockAntwort, FassungEintrag, FassungStand, FassungStart,
    Fassungswahl, Folgen, FragwuerdigeEntfernt, FragwuerdigeWeg, LaufEintrag, Lesestand, LesestandNeu, Zielsprache,
)
from backend.app.models.grenzen import Nr
from backend.app.services import begriffsliste, fassung_ablage, fassung_lesen, fassungen, fassungsstand
from backend.app.services.fassungen import Beanstandet, BlockZeile, Buchangaben, FassungZeile, Ungueltig
from backend.app.services.uebersetzungslauf import uebersetzungslauf

router = APIRouter(tags=["Übersetzung"])
KI = Depends(braucht("ki"))                     # übersetzen, prüfen, Begriffe: KI, nie für Kinder (BF-78); lesen darf jeder


async def _buch(buch_id: int) -> Buchangaben:
    b = await fassungen.buch(buch_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")
    return b


async def _fassung(fid: int) -> FassungZeile:
    f = await fassungen.holen(fid)
    if f is None:
        raise HTTPException(status_code=404, detail="Fassung nicht gefunden")
    return f


async def _gebucht_und_angestossen() -> None:
    await db.commit()
    uebersetzungslauf.anstossen()


def _antwort(z: BlockZeile) -> BlockAntwort:
    return BlockAntwort(kennung=z.kennung, stand=z.stand, deutsch=z.uebersetzung, befunde=z.befunde)


# -- Fassungen ----------------------------------------------------------------------------------------------------------------

@router.get("/api/books/{buch_id}/fassungen", response_model=list[FassungEintrag])
async def fassungen_liste(buch_id: Nr, p: Profil = Depends(profil)) -> list[FassungEintrag]:
    """Das Original zuerst (`id` null, `original` true), dann jede Fassung mit Stand und Kapiteln; die Wahl des Profils."""
    b = await _buch(buch_id)
    z = await db.fetch_one("SELECT created_at FROM books WHERE id = ?", (buch_id,))
    return await fassungsstand.eintraege(b, z["created_at"], await fassung_lesen.wahl(p.id, buch_id))


@router.put("/api/books/{buch_id}/fassungen/wahl", response_model=list[FassungEintrag])
async def fassung_waehlen(buch_id: Nr, wahl: Fassungswahl, p: Profil = Depends(profil)) -> list[FassungEintrag]:
    """Welche Fassung "Lesen" auf der Buchseite öffnet (`sprache` null: das Original); gilt auf jedem Gerät."""
    await _buch(buch_id)
    if wahl.sprache is not None and await fassungen.zum_buch(buch_id, wahl.sprache) is None:
        raise HTTPException(status_code=404, detail="Diese Fassung gibt es noch nicht")
    await fassung_lesen.waehlen(p.id, buch_id, wahl.sprache)
    await db.commit()
    return await fassungen_liste(buch_id, p)


@router.get("/api/fassungen", response_model=list[LaufEintrag], dependencies=[KI, Depends(verify_token)])
async def fassungen_in_arbeit(s: Sicht = Depends(sicht)) -> list[LaufEintrag]:
    """Jede Fassung, die läuft, Pause macht oder auf einen Menschen wartet (Fehler), für die Aufträge; nur von Büchern, die das
    Profil sieht (BF-78)."""
    laeufe = await fassungsstand.laeufe()
    sieht = set(await sichtbar.nur_sichtbare(s, [f.buch_id for f in laeufe]))
    return [f for f in laeufe if f.buch_id in sieht]


@router.get("/api/books/{buch_id}/fassungen/{sprache}/folgen", response_model=Folgen, dependencies=[KI, Depends(verify_token)])
async def fassung_folgen(buch_id: Nr, sprache: Zielsprache) -> Folgen:
    """Rückfrage vor dem Start: Umfang, Dauer, Ablage; `geht` false mit Grund."""
    return await fassungsstand.folgen(await _buch(buch_id), sprache)


@router.post("/api/books/{buch_id}/fassungen/{sprache}", response_model=FassungStand, dependencies=[KI, Depends(verify_token)])
async def fassung_starten(buch_id: Nr, sprache: Zielsprache, eingabe: FassungStart | None = None) -> FassungStand:
    """Startet die Übersetzung oder setzt sie fort (aus Pause, abgebrochen, nach einem Fehler, oder fertig mit geänderten
    Prüfungen). `anrede` gilt für eine neue Fassung; eine bestehende bleibt bei ihrer (sonst 409)."""
    b = await _buch(buch_id)
    f = await fassungen.zum_buch(buch_id, sprache)
    anrede = eingabe.anrede if eingabe is not None else None
    if f is None:
        folgen = await fassungsstand.folgen(b, sprache)
        if not folgen.geht:
            raise HTTPException(status_code=422, detail=folgen.grund)
        f = await fassungen.anlegen(buch_id, sprache, "en", anrede or fassungen.anrede_vorgabe())
    elif anrede is not None and anrede != f.anrede:
        raise HTTPException(status_code=409, detail=f"Diese Fassung spricht den Leser mit {f.anrede} an; ein Buch bleibt bei einer "
                                                    "Anrede")
    elif f.stand in ("pause", "teilweise", "fehler") or (f.stand == "fertig" and await fassungen.noch_zu_tun(f)):
        await fassungen.stand_setzen(f.id, "laeuft")
    await _gebucht_und_angestossen()
    return await fassungsstand.stand(await _fassung(f.id))


@router.get("/api/fassungen/{fid}/stand", response_model=FassungStand, dependencies=[Depends(verify_token)])
async def fassung_stand(fid: Nr) -> FassungStand:
    return await fassungsstand.stand(await _fassung(fid))


@router.post("/api/fassungen/{fid}/pause", response_model=FassungStand, dependencies=[KI, Depends(verify_token)])
async def fassung_pause(fid: Nr) -> FassungStand:
    """Hält den Lauf sofort an; Fortsetzen nimmt ihn am ersten offenen Block wieder auf."""
    await _fassung(fid)
    await fassungen.stand_setzen(fid, "pause", nur_aus=("laeuft",))
    await db.commit()
    uebersetzungslauf.halten(fid)
    return await fassungsstand.stand(await _fassung(fid))


@router.post("/api/fassungen/{fid}/fortsetzen", response_model=FassungStand, dependencies=[KI, Depends(verify_token)])
async def fassung_fortsetzen(fid: Nr) -> FassungStand:
    await _fassung(fid)
    await fassungen.stand_setzen(fid, "laeuft", nur_aus=("pause", "teilweise", "fehler"))
    await _gebucht_und_angestossen()
    return await fassungsstand.stand(await _fassung(fid))


@router.post("/api/fassungen/{fid}/abbrechen", response_model=FassungStand, dependencies=[KI, Depends(verify_token)])
async def fassung_abbrechen(fid: Nr) -> FassungStand:
    """Beendet den Lauf; Fertiges bleibt, die Fassung bleibt "teilweise" und wird so abgelegt."""
    f = await _fassung(fid)
    rest = not f.zerlegt or await fassungen.offen_in_arbeit(fid)
    await fassungen.stand_setzen(fid, "teilweise" if rest else "fertig", nur_aus=("laeuft", "pause", "fehler"))
    await db.commit()
    uebersetzungslauf.halten(fid)
    uebersetzungslauf.anstossen()
    return await fassungsstand.stand(await _fassung(fid))


@router.get("/api/fassungen/{fid}/bericht", response_model=Bericht, dependencies=[KI, Depends(verify_token)])
async def fassung_bericht(fid: Nr) -> Bericht:
    """Zahlen und jede offene Stelle mit Original, Übersetzung und Befunden."""
    return await fassungsstand.bericht(await _fassung(fid))


@router.post("/api/fassungen/{fid}/bloecke/{kennung}", response_model=BlockAntwort, dependencies=[KI, Depends(verify_token)])
async def block_aendern(fid: Nr, kennung: str, eingabe: BlockAktion) -> BlockAntwort | JSONResponse:
    """neu: wird neu übersetzt; annehmen: eine offene Stelle wie übersetzt; setzen: dein Text, wenn er die festen Prüfungen
    besteht (sonst 422 mit Befunden)."""
    f = await _fassung(fid)
    try:
        if eingabe.aktion == "neu":
            z = await fassungen.block_neu(f, kennung)
        elif eingabe.aktion == "annehmen":
            z = await fassungen.block_annehmen(f, kennung)
        else:
            z = await fassungen.block_setzen(f, kennung, eingabe.text or "", await begriffsliste.gelten(f.buch_id))
    except Ungueltig as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Beanstandet as e:
        return JSONResponse(status_code=422, content={"detail": f"Der Text besteht die festen Prüfungen nicht: {e}",
                                                      "befunde": [b.model_dump() for b in e.befunde]})
    if z is None:
        raise HTTPException(status_code=404, detail="Block nicht gefunden")
    await _gebucht_und_angestossen()
    return _antwort(z)


@router.get("/api/fassungen/{fid}/datei", dependencies=[Depends(verify_token_inhalt)])
async def fassung_datei(fid: Nr, request: Request, herunterladen: bool = Query(False, description="Als Anhang statt zum Lesen")) -> Response:
    """Die deutsche Fassung als EPUB, auch teilweise: offene Blöcke stehen im Original und sind markiert."""
    f = await _fassung(fid)
    b = await _buch(f.buch_id)
    abgelegt = await fassung_ablage.antwort(request, f, b, herunterladen)
    if abgelegt is not None:
        return abgelegt
    if not f.zerlegt:
        raise HTTPException(status_code=409, detail="Die Fassung ist noch nicht zerlegt; gleich gibt es die ersten Kapitel")
    original = await fassungen.original_lesen(b)
    if original is None:
        raise HTTPException(status_code=503, detail="Das Original ist gerade nicht zu holen")
    daten = await asyncio.to_thread(fassungen.epub_bauen, b, original, await fassungen.satz(f))
    weise = "attachment" if herunterladen else "inline"
    name = fassung_ablage.name_zum_lesen(b, f.sprache)
    return Response(daten, media_type=fassung_ablage.EPUB, headers={"Content-Disposition": f"{weise}; filename*=UTF-8''{quote(name)}"})


@router.get("/api/fassungen/{fid}/leseposition", response_model=Lesestand)
async def fassung_lesestand(fid: Nr, p: Profil = Depends(profil)) -> Lesestand:
    """Wo das Profil in dieser Fassung liest; getrennt vom Lesestand des Originals."""
    await _fassung(fid)
    return await fassung_lesen.lesestand(p.id, fid)


@router.patch("/api/fassungen/{fid}/leseposition", response_model=Lesestand)
async def fassung_lesestand_merken(fid: Nr, neu: LesestandNeu, p: Profil = Depends(braucht("lesen"))) -> Lesestand:
    """Merkt die Stelle in dieser Fassung; Lesestand und Vorlesestelle des Originals bleiben unberührt."""
    await _fassung(fid)
    stand = await fassung_lesen.merken(p.id, fid, neu.position)
    await db.commit()
    return stand


# -- Begriffsliste ------------------------------------------------------------------------------------------------------------

@router.get("/api/books/{buch_id}/begriffe", response_model=list[BegriffEintrag], dependencies=[KI, Depends(verify_token)])
async def begriffe_des_buchs(buch_id: Nr) -> list[BegriffEintrag]:
    await _buch(buch_id)
    return await begriffsliste.liste(buch_id)


@router.post("/api/books/{buch_id}/begriffe", response_model=BegriffEintrag, status_code=201, dependencies=[KI, Depends(verify_token)])
async def begriff_anlegen(buch_id: Nr, neu: BegriffNeu) -> BegriffEintrag:
    """Ein Begriff von Hand; Blöcke, in denen er vorkommt, werden neu übersetzt."""
    await _buch(buch_id)
    e = await begriffsliste.anlegen(buch_id, neu)
    await _gebucht_und_angestossen()
    return e


@router.post("/api/books/{buch_id}/begriffe/fragwuerdige/entfernen", response_model=FragwuerdigeEntfernt,
             dependencies=[KI, Depends(verify_token)])
async def fragwuerdige_entfernen(buch_id: Nr, weg: FragwuerdigeWeg) -> FragwuerdigeEntfernt:
    """Entfernt die genannten fragwürdigen Einträge (die, die die Vorschau zeigte); was inzwischen nicht mehr fragwürdig ist,
    bleibt. Neu übersetzt wird dafür nichts, sie galten nicht."""
    await _buch(buch_id)
    entfernt = await begriffsliste.fragwuerdige_entfernen(buch_id, weg.ids)
    await db.commit()
    return FragwuerdigeEntfernt(entfernt=entfernt)


@router.get("/api/begriffe", response_model=list[BegriffEintrag], dependencies=[KI, Depends(verify_token)])
async def begriffe_fuer_alle() -> list[BegriffEintrag]:
    """Die Liste für alle Bücher."""
    await begriffsliste.vorgaben_einspielen()
    return await begriffsliste.liste(None)


@router.post("/api/begriffe", response_model=BegriffEintrag, status_code=201, dependencies=[KI, Depends(verify_token)])
async def begriff_fuer_alle_anlegen(neu: BegriffNeu) -> BegriffEintrag:
    e = await begriffsliste.anlegen(None, neu)
    await _gebucht_und_angestossen()
    return e


@router.patch("/api/begriffe/{bid}", response_model=BegriffEintrag, dependencies=[KI, Depends(verify_token)])
async def begriff_aendern(bid: Nr, aenderung: BegriffAenderung) -> BegriffEintrag:
    try:
        e = await begriffsliste.aendern(bid, aenderung)
    except ValueError as f:
        raise HTTPException(status_code=422, detail=str(f)) from f
    if e is None:
        raise HTTPException(status_code=404, detail="Begriff nicht gefunden")
    await _gebucht_und_angestossen()
    return e


@router.delete("/api/begriffe/{bid}", dependencies=[KI, Depends(verify_token)])
async def begriff_loeschen(bid: Nr) -> dict:
    if not await begriffsliste.loeschen(bid):
        raise HTTPException(status_code=404, detail="Begriff nicht gefunden")
    await _gebucht_und_angestossen()
    return {"geloescht": True, "id": bid}

