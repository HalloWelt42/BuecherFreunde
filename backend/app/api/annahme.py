"""Wege der Annahme (Hochladen, Vorschau, Einstellungen), Vertrag in docs/neubau/SCHNITTSTELLE.md. Nur mit der Fähigkeit
`hinzufuegen` (die Einstellungen mit `einstellungen`); Aufnahmen zu Büchern, die das Profil nicht sieht (privat eines anderen),
fehlen in Liste, Vorschau und Ereignissen (BF-78)."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.app.ablage.wolke import WolkeFehler
from backend.app.annahme import eingangsordner, einstellungen, uebernehmen, verwerfen, vorschau
from backend.app.annahme.dienst import QUELLEN, STAENDE, TEIL, Versatz, ZuViel, annahme
from backend.app.annahme.einstellungen import Hinzufuegen
from backend.app.annahme.modelle import Aenderung, Auswahl, Verwerffolgen, Vorschauansicht, Vorschaukurz, VorschauNeu
from backend.app.core.auth import braucht
from backend.app.core.database import db
from backend.app.familie import sichtbar
from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht
from backend.app.models.grenzen import AUSWAHL_HOECHSTENS, DATEINAME, GROESSTE_ZAHL, Nr
from backend.app.services.storage import get_sidecar_path

Quelle = Literal[QUELLEN]                         # type: ignore[valid-type]
Stand = Literal[STAENDE]                          # type: ignore[valid-type]
UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

router = APIRouter(prefix="/api/annahme", tags=["Annahme"])
HINZUFUEGEN = braucht("hinzufuegen")


class Neu(BaseModel):
    name: str = Field(min_length=1, max_length=DATEINAME)
    groesse: int = Field(ge=0, le=GROESSTE_ZAHL)
    sha256: str = Field("", pattern=r"^([0-9a-f]{64})?$")
    anreichern: bool = False
    vorschau: str | None = Field(None, pattern=UUID)   # mehrere Dateien in eine Vorschau (POST /vorschau); sonst je Datei eine


class Uebernommen(BaseModel):
    weiter: int                                   # so viele gehen weiter ins Regal, als Format oder als Material
    vorschau: Vorschauansicht


async def _da(nr: int, p: Profil) -> dict:
    z = await annahme.einer(nr)
    if z is None or (z["buch_id"] and not await sichtbar.sieht(Sicht.von(p), z["buch_id"])):
        raise HTTPException(404, "Diese Aufnahme gibt es nicht")
    return z


async def _fuer(p: Profil, stand: dict) -> dict:
    """Die Liste ohne Aufnahmen zu Büchern, die das Profil nicht sieht; die Zähler zählen Aufnahmen, keine Titel. Dazu die
    Vorschauen, die auf die Bestätigung warten."""
    buecher = [e["buch_id"] for e in stand["eintraege"] if e["buch_id"]]
    sieht = set(await sichtbar.nur_sichtbare(Sicht.von(p), buecher))
    return stand | {"eintraege": [e for e in stand["eintraege"] if not e["buch_id"] or e["buch_id"] in sieht],
                    "vorschauen": [v.model_dump() for v in await vorschau.uebersicht(Sicht.von(p))]}


@router.get("")
async def alle(p: Profil = Depends(HINZUFUEGEN)):
    return await _fuer(p, await annahme.alle())


@router.post("")
async def anlegen(n: Neu, _: Profil = Depends(HINZUFUEGEN)):
    if n.vorschau:
        await _offene_vorschau(n.vorschau)
    return await annahme.anlegen(n.name, n.groesse, n.sha256, n.anreichern, vorschau_id=n.vorschau)


@router.delete("")
async def aufraeumen(quelle: Quelle | None = None, stand: list[Stand] | None = Query(None), p: Profil = Depends(HINZUFUEGEN)):
    """Viele auf einmal entfernen, wie einzeln mit DELETE /{nr}: nach Quelle, nach Stand (mehrfach) oder beidem."""
    if quelle is None and not stand:
        raise HTTPException(422, "Quelle oder Stand: fehlt, ohne beides wäre es die ganze Liste")
    return {"entfernt": await annahme.aufraeumen(quelle, stand), **await _fuer(p, await annahme.alle())}


@router.post("/ausblenden")
async def ausblenden(p: Profil = Depends(HINZUFUEGEN)):
    await annahme.ausblenden()
    return await _fuer(p, await annahme.alle())


@router.get("/eingangsordner")
async def eingang(_: Profil = Depends(HINZUFUEGEN)):
    try:
        return await eingangsordner.inhalt()
    except WolkeFehler as f:
        raise HTTPException(503, f.meldung) from f


@router.post("/eingangsordner")
async def eingang_aufnehmen(_: Profil = Depends(HINZUFUEGEN)):
    try:
        return {"neu": await eingangsordner.aufnehmen()}
    except WolkeFehler as f:
        raise HTTPException(503, f.meldung) from f


@router.get("/ereignisse")
async def ereignisse(p: Profil = Depends(braucht("hinzufuegen", inhalt=True))):
    async def strom():
        async for d in annahme.ereignisse():
            yield f"data: {json.dumps(await _fuer(p, d), ensure_ascii=False)}\n\n"
    return StreamingResponse(strom(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# -- Einstellungen (BF-80) --------------------------------------------------------------------------------------------------

@router.get("/einstellungen", response_model=Hinzufuegen)
async def einstellungen_lesen(_: Profil = Depends(braucht("einstellungen"))) -> Hinzufuegen:
    return await einstellungen.lesen()


@router.put("/einstellungen", response_model=Hinzufuegen)
async def einstellungen_schreiben(neu: Hinzufuegen, _: Profil = Depends(braucht("einstellungen"))) -> Hinzufuegen:
    return await einstellungen.schreiben(neu)


# -- Vorschau (BF-80) -------------------------------------------------------------------------------------------------------

async def _offene_vorschau(nr: str) -> dict:
    try:
        v = await vorschau.offene(nr)
    except vorschau.VorschauFehlt as f:
        raise HTTPException(404, str(f)) from f
    if v["stand"] != "offen":
        raise HTTPException(409, "Diese Vorschau ist schon erledigt")
    return v


async def _ansicht(nr: str, p: Profil) -> Vorschauansicht:
    try:
        return await vorschau.ansicht(nr, Sicht.von(p))
    except vorschau.VorschauFehlt as f:
        raise HTTPException(404, str(f)) from f


@router.get("/vorschau", response_model=list[Vorschaukurz])
async def vorschauen(p: Profil = Depends(HINZUFUEGEN)) -> list[Vorschaukurz]:
    return await vorschau.uebersicht(Sicht.von(p))


@router.post("/vorschau", response_model=Vorschauansicht)
async def vorschau_anlegen(neu: VorschauNeu, p: Profil = Depends(HINZUFUEGEN)) -> Vorschauansicht:
    """Eine leere Vorschau für mehrere Dateien oder eine Lücke (`vorgabe`); die Dateien nennen sie beim Anlegen."""
    if neu.vorgabe.sammlung_id and await db.fetch_one("SELECT 1 AS da FROM collections WHERE id = ?", (neu.vorgabe.sammlung_id,)) is None:
        raise HTTPException(422, "Vorgabe, Sammlung: diese Sammlung gibt es nicht")
    nr = await vorschau.anlegen(neu.name, "hochladen", neu.vorgabe)
    return await _ansicht(nr, p)


@router.get("/vorschau/{vid}", response_model=Vorschauansicht)
async def vorschau_zeigen(vid: str, p: Profil = Depends(HINZUFUEGEN)) -> Vorschauansicht:
    return await _ansicht(vid, p)


@router.patch("/vorschau/{vid}", response_model=Vorschauansicht)
async def vorschau_aendern(vid: str, a: Aenderung, p: Profil = Depends(HINZUFUEGEN)) -> Vorschauansicht:
    """Felder einer oder mehrerer Dateien setzen (Herkunft danach `nutzer`); geht eine nicht, ändert sich keine."""
    await _offene_vorschau(vid)
    try:
        v = await vorschau.aendern(vid, a, Sicht.von(p))
    except vorschau.VorschauFehlt as f:
        raise HTTPException(404, str(f)) from f
    except vorschau.Unpassend as f:
        raise HTTPException(422, f.meldung) from f
    except vorschau.Vorbei as f:
        raise HTTPException(409, f.meldung) from f
    annahme.melden()
    return v


@router.post("/vorschau/{vid}/uebernehmen", response_model=Uebernommen)
async def vorschau_uebernehmen(vid: str, auswahl: Auswahl | None = None, p: Profil = Depends(HINZUFUEGEN)) -> Uebernommen:
    """Die gewählten Dateien (ohne Wahl alle) übernehmen; was weggelassen oder nicht übernommen wird, bleibt im Eingang."""
    await _offene_vorschau(vid)
    try:
        weiter = await uebernehmen.bestaetigen(vid, auswahl.ids if auswahl else None, p.id)
    except vorschau.VorschauFehlt as f:
        raise HTTPException(404, str(f)) from f
    except uebernehmen.Unvollstaendig as f:
        raise HTTPException(422, f.meldung) from f
    annahme.melden()
    return Uebernommen(weiter=weiter, vorschau=await _ansicht(vid, p))


@router.get("/vorschau/{vid}/folgen", response_model=Verwerffolgen)
async def vorschau_folgen(vid: str, ids: list[Nr] | None = Query(None, max_length=AUSWAHL_HOECHSTENS), _: Profil = Depends(HINZUFUEGEN)) -> Verwerffolgen:
    """Was Verwerfen bewirkt, je Datei: Papierkorb der Kellerwolke, endgültig gelöscht oder bleibt im Ordner."""
    await _offene_vorschau(vid)
    try:
        return await verwerfen.folgen(vid, ids)
    except vorschau.VorschauFehlt as f:
        raise HTTPException(404, str(f)) from f


@router.delete("/vorschau/{vid}")
async def vorschau_verwerfen(vid: str, stand: str = Query(max_length=64), ids: list[Nr] | None = Query(None, max_length=AUSWAHL_HOECHSTENS),
                             p: Profil = Depends(HINZUFUEGEN)):
    """Nur nach den Folgen: `stand` aus GET .../folgen; hat sich seitdem etwas geändert, 409."""
    await _offene_vorschau(vid)
    try:
        n = await verwerfen.verwerfen(vid, ids, stand)
    except vorschau.VorschauFehlt as f:
        raise HTTPException(404, str(f)) from f
    except verwerfen.StandVeraltet as f:
        raise HTTPException(409, str(f)) from f
    except verwerfen.NichtVerworfen as f:
        raise HTTPException(502, f"Nicht alles verworfen: {f}") from f
    finally:
        annahme.melden()
    return {"verworfen": n, "vorschau": await _ansicht(vid, p)}


# -- eine Aufnahme ----------------------------------------------------------------------------------------------------------

@router.get("/{nr}")
async def einer(nr: Nr, p: Profil = Depends(HINZUFUEGEN)):
    return await _da(nr, p)


@router.get("/{nr}/umschlag")
async def umschlag(nr: Nr, p: Profil = Depends(braucht("hinzufuegen", inhalt=True))):
    """Der Umschlag, den das Lesen fand, für die Vorschau (vor dem Übernehmen gibt es noch kein Buch)."""
    z = await _da(nr, p)
    bild = get_sidecar_path(z["sha256"], "cover.jpg") if z["sha256"] else None
    if bild is None or not bild.is_file():
        raise HTTPException(404, "Kein Umschlag")
    return FileResponse(bild, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.patch("/{nr}")
async def teil(nr: Nr, request: Request, p: Profil = Depends(HINZUFUEGEN)):
    await _da(nr, p)
    try:
        versatz, laenge = int(request.headers.get("upload-offset", "")), int(request.headers.get("content-length", ""))
    except ValueError:
        raise HTTPException(400, "Es fehlen Upload-Offset oder Content-Length") from None
    if laenge > TEIL:
        raise HTTPException(413, "Das Teil ist größer als vereinbart")
    try:
        return await annahme.teil(nr, versatz, request.stream(), laenge)
    except ZuViel as f:
        raise HTTPException(413, "Mehr Daten als die angesagte Größe der Datei") from f
    except Versatz as f:
        return JSONResponse({"detail": str(f), "empfangen": f.empfangen}, status_code=409)
    except WolkeFehler as f:
        raise HTTPException(503, f.meldung) from f


@router.post("/{nr}/erneut")
async def erneut(nr: Nr, p: Profil = Depends(HINZUFUEGEN)):
    await _da(nr, p)
    return await annahme.erneut(nr)


@router.delete("/{nr}")
async def entfernen(nr: Nr, p: Profil = Depends(HINZUFUEGEN)):
    await _da(nr, p)
    await annahme.entfernen(nr)
    return {"entfernt": nr}
