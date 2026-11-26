"""Wege der Ersteinrichtung (BF-82, docs/neubau/SCHNITTSTELLE.md, Ersteinrichtung): Zustand und Schritte, Anschlüsse, Katalog,
Familie, Wiederherstellen, Neuaufbau, Umzug, Aufträge und Wartung; dazu die Wege des alten Geräts beim Umzug (`/api/umzug`) und
die Einstellungen der Kellerwolke (`/api/kellerwolke`). Die Arbeit tut `backend/app/einrichtung/`."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Annotated, Literal, TypeVar

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from backend.app.ablage import persoenlich, sicherungen as wolke_sicherungen
from backend.app.ablage.wolke import WolkeFehler
from backend.app.core.auth import braucht, sicht
from backend.app.einrichtung import (
    anschluesse, hochladen, katalog_schritt, neuaufbau, nachfuehren as nachfuehren_modul, orte, pruefung as pruefung_modul, umzug, wartung,
    wiederherstellen, zustand,
)
from backend.app.einrichtung.auftrag import auftraege
from backend.app.einrichtung.hochladen import Hochladen, Hochladestand
from backend.app.einrichtung.modelle import (
    Aenderungen, Anschluss, AnschlussEingabe, AnschlussPruefen, Anschlussart, Auftragsstand, AusgangslageWahl, Einloesen,
    Einrichtung, KatalogWahl, Kellerwolkeneinstellungen, KellerwolkeneinstellungenEingabe, Kontostand, Kontoverbindung, Neuaufbaubericht,
    OrdnerWahl, Ordnerpruefung, OriginaleWahl, Orte, Persoenlichfolgen, Pruefbericht, PruefungStarten, Schritt, SchrittAktion, Sicherungsliste, Uebernehmen,
    Uebernommen, UmzugVerbinden, Umzugsergebnis, Umzugspaket, Umzugsstand, UmzugVorbereitet, Verbindungspruefung, Vorgemerkt,
    Wiederherstellen, Wiederherstellfolgen, Wiederherstellstand,
)
from backend.app.einrichtung.nachfuehren import nachfuehren
from backend.app.einrichtung.zugang import Zugang, ZuOft, angemeldet, vor_dem_konto, zugang
from backend.app.einrichtung.zustand import Einrichtungsfehler
from backend.app.familie import sichtbar
from backend.app.familie.modelle import Profil, ProfilNeu, Stimmeingabe

router = APIRouter(prefix="/api/einrichtung", tags=["Ersteinrichtung"])
umzug_router = APIRouter(prefix="/api/umzug", tags=["Umzug"])
kellerwolke_router = APIRouter(prefix="/api/kellerwolke", tags=["Kellerwolke"])
EINSTELLUNGEN = Depends(braucht("einstellungen"))
Z = TypeVar("Z")


async def _tun(arbeit: Awaitable[Z]) -> Z:
    """Fehler der Einrichtung als deutsche Antwort mit ihrem Status (429 mit Retry-After); antwortet die Kellerwolke nicht, 502 mit
    ihrem Grund."""
    try:
        return await arbeit
    except ZuOft as f:
        raise HTTPException(f.status, f.meldung, headers={"Retry-After": str(f.nochmal_in)}) from f
    except Einrichtungsfehler as f:
        raise HTTPException(f.status, f.meldung) from f
    except WolkeFehler as f:
        raise HTTPException(404 if f.status == 404 else 502, f.meldung) from f


async def _nach_dem_konto(z: Zugang) -> Profil:
    if z.profil is None:
        raise HTTPException(409, "Erst ein Konto anlegen oder mit der Kellerwolke anmelden")
    return z.profil


# -- Zustand und Schritte -------------------------------------------------------------------------------------------------

@router.get("", response_model=Einrichtung)
async def einrichtung_lesen(request: Request) -> Einrichtung:
    """Ohne Anmeldung erreichbar: die Oberfläche fragt hier vor der Anmeldung, ob sie den Assistenten zeigt."""
    return await zustand.lesen(angemeldet=await angemeldet(request))


@router.post("/ausgangslage", response_model=Einrichtung)
async def ausgangslage(w: AusgangslageWahl, _z: Zugang = Depends(zugang)) -> Einrichtung:
    return await _tun(zustand.ausgangslage_waehlen(w.ausgangslage))


@router.post("/schritte/{schritt}", response_model=Einrichtung)
async def schritt_setzen(schritt: str, a: SchrittAktion, _z: Zugang = Depends(zugang)) -> Einrichtung:
    return await _tun(zustand.schritt_setzen(schritt, a.aktion))


@router.post("/abschliessen", response_model=Einrichtung)
async def abschliessen(z: Zugang = Depends(zugang)) -> Einrichtung:
    await _nach_dem_konto(z)
    return await _tun(zustand.abschliessen())


@router.get("/uebersicht", response_model=list[Schritt], dependencies=[EINSTELLUNGEN])
async def uebersicht() -> list[Schritt]:
    """Was eingerichtet und was übersprungen ist, auch nach dem Abschluss."""
    return await zustand.uebersicht()


@router.get("/orte", response_model=Orte)
async def orte_lesen(_z: Zugang = Depends(zugang)) -> Orte:
    """Misst jedes Mal neu ("Neu suchen")."""
    return await orte.stand()


@router.post("/konto/kellerwolke", response_model=Kontostand)
async def konto_kellerwolke(k: Kontoverbindung, z: Zugang = Depends(zugang)) -> Kontostand:
    """Schritt Konto mit der Kellerwolke: prüft den App-Zugang und trägt Adresse und Schlüssel gleich ein; danach meldet man sich
    mit dem Konto der Kellerwolke an (`/api/anmeldung`). Nur, solange es noch kein Konto gibt."""
    await _tun(zustand.nur_neu())
    if not z.ohne_konto:
        raise HTTPException(409, "Es gibt schon ein Konto")
    await _pruefweg(z, k.adresse)
    p, _wert = await _tun(anschluesse.vorbereiten("kellerwolke", AnschlussEingabe(adresse=k.adresse, schluessel=k.schluessel)))
    await anschluesse.anwenden_eintrag("kellerwolke", k.adresse, k.schluessel)
    return Kontostand(anmeldung="kellerwolke", app=p.app, besitzer=p.konto)


# -- Anschlüsse -----------------------------------------------------------------------------------------------------------

async def _pruefweg(z: Zugang, adresse: str) -> None:
    async def pruefen() -> None:
        vor_dem_konto(z, adresse)
    await _tun(pruefen())


async def _offen_oder_wartung() -> None:
    if await zustand.modus() == "aus":
        raise HTTPException(409, "Die Einrichtung ist abgeschlossen; unter Wartung lässt sich der Assistent wieder öffnen")


@router.get("/anschluesse", response_model=list[Anschluss])
async def anschluesse_lesen(_z: Zugang = Depends(zugang)) -> list[Anschluss]:
    return await anschluesse.liste()


@router.post("/anschluesse/{art}/pruefen", response_model=Verbindungspruefung)
async def anschluss_pruefen(art: Anschlussart, p: AnschlussPruefen, z: Zugang = Depends(zugang)) -> Verbindungspruefung:
    """Prüft die genannten Werte, sonst die eingetragenen; merkt nichts."""
    await _pruefweg(z, p.adresse if p.adresse is not None else (await anschluesse.eintrag(art)).adresse)
    return await anschluesse.pruefen(art, p.adresse, p.schluessel)


@router.put("/anschluesse/{art}", response_model=Vorgemerkt)
async def anschluss_eintragen(art: Anschlussart, e: AnschlussEingabe, z: Zugang = Depends(zugang)) -> Vorgemerkt:
    """Gilt erst nach bestandener Prüfung; der Schlüssel geht nur in die Schlüsseldatei. Unter Wartung nur vorgemerkt."""
    await _offen_oder_wartung()
    await _pruefweg(z, e.adresse)
    await _tun(anschluesse.vorbereiten(art, e))
    return await _tun(wartung.anschluss(art, e.adresse, e.schluessel))


# -- Katalog, Familie -----------------------------------------------------------------------------------------------------

@router.post("/katalog", response_model=Vorgemerkt)
async def katalog(w: KatalogWahl, z: Zugang = Depends(zugang)) -> Vorgemerkt:
    await _nach_dem_konto(z)
    v = await _tun(wartung.katalog(w.wahl))
    if v.angewandt:
        await zustand.vermerken("katalog", text=katalog_schritt.NAMEN[w.wahl])
    return v


@router.post("/familie/profile", response_model=Vorgemerkt)
async def profil_anlegen(neu: ProfilNeu, z: Zugang = Depends(zugang)) -> Vorgemerkt:
    """Wie `POST /api/familie/profile`; unter Wartung nur vorgemerkt. PIN und Bild-PIN danach über die Wege der Familie."""
    von = await _nach_dem_konto(z)
    return await _tun(wartung.profil(neu, von))


@router.put("/familie/stimme", response_model=Vorgemerkt)
async def stimme(s: Stimmeingabe, z: Zugang = Depends(zugang)) -> Vorgemerkt:
    await _nach_dem_konto(z)
    return await _tun(wartung.stimme(s.stimme))


# -- Sicherungen und Wiederherstellen -------------------------------------------------------------------------------------

@router.get("/sicherungen", response_model=Sicherungsliste)
async def sicherungen(quelle: Literal["geraet", "kellerwolke"] = "geraet", _z: Zugang = Depends(zugang)) -> Sicherungsliste:
    """Neueste zuerst, mit Datum, Größe, Zahl der Bücher und Profile."""
    return await wiederherstellen.liste(quelle)


@router.post("/sicherungen/hochladen", response_model=Hochladestand)
async def hochladen_anmelden(h: Hochladen, _z: Zugang = Depends(zugang)) -> Hochladestand:
    """Eine Sicherung in Teilen hochladen; gleicher Name und gleiche Prüfsumme finden den angefangenen Stand wieder."""
    return await _tun(hochladen.anmelden(h))


@router.get("/sicherungen/hochladen/{kennung}", response_model=Hochladestand)
async def hochladen_stand(kennung: str, _z: Zugang = Depends(zugang)) -> Hochladestand:
    return await _tun(hochladen.stand(kennung))


@router.patch("/sicherungen/hochladen/{kennung}", response_model=Hochladestand)
async def hochladen_teil(kennung: str, request: Request, _z: Zugang = Depends(zugang)):
    """Das nächste Teil, Kopf `Upload-Offset`, Körper roh; 409 `{detail, empfangen}` nennt den wahren Stand."""
    try:
        versatz, laenge = int(request.headers.get("upload-offset", "")), int(request.headers.get("content-length", ""))
    except ValueError:
        raise HTTPException(400, "Es fehlen Upload-Offset oder Content-Length") from None
    try:
        return await _tun(hochladen.teil(kennung, versatz, request.stream(), laenge))
    except HTTPException as f:
        if isinstance(f.__cause__, hochladen.Versatz):
            return JSONResponse({"detail": f.detail, "empfangen": f.__cause__.empfangen}, status_code=409)
        raise


@router.get("/wiederherstellen/folgen", response_model=Wiederherstellfolgen)
async def wiederherstellen_folgen(quelle: Literal["datei", "geraet", "kellerwolke"], kennung: str,
                                  _z: Zugang = Depends(zugang)) -> Wiederherstellfolgen:
    """Was die Sicherung enthält und was sie ersetzen würde (etwa ein schon angelegtes Konto), mit `stand`."""
    return await _tun(wiederherstellen.folgen(quelle, kennung))


@router.post("/wiederherstellen", response_model=Auftragsstand)
async def wiederherstellen_aus(w: Wiederherstellen, _z: Zugang = Depends(zugang)) -> Auftragsstand:
    """Nur mit dem `stand` der Folgen; das Einspielen läuft als Auftrag "Sicherung einspielen", danach die Prüfung der Originale."""
    return await _tun(wiederherstellen.beginnen(w.quelle, w.kennung, w.stand))


@router.get("/wiederherstellen", response_model=Wiederherstellstand)
async def wiederherstellen_stand(_z: Zugang = Depends(zugang)) -> Wiederherstellstand:
    return Wiederherstellstand(auftrag=await wiederherstellen.einspielen.stand(), ergebnis=await wiederherstellen.einspielen.ergebnis())


# -- Aufträge, Prüfung, Neuaufbau -----------------------------------------------------------------------------------------

@router.get("/auftraege", response_model=list[Auftragsstand])
async def auftraege_lesen(_z: Zugang = Depends(zugang)) -> list[Auftragsstand]:
    """Einspielen, Prüfung, Neuaufbau, Kopieren und das Nachführen des Persönlichen; ohne Lauf `stand` leer."""
    return [await a.stand() for a in auftraege().values()] + [await nachfuehren.stand()]


@router.post("/auftraege/{art}/{aktion}", response_model=Auftragsstand)
async def auftrag_steuern(art: Literal["einspielen", "pruefung", "neuaufbau", "kopieren"], aktion: Literal["pause", "fortsetzen"],
                          _z: Zugang = Depends(zugang)) -> Auftragsstand:
    a = auftraege()[art]
    return await (a.pause() if aktion == "pause" else a.fortsetzen())


@router.post("/pruefung", response_model=Auftragsstand)
async def pruefung_starten(p: PruefungStarten, _z: Zugang = Depends(zugang)) -> Auftragsstand:
    """Prüft jedes Original (neu von vorn, der alte Bericht fällt weg; Bücher bleiben). Nur in der Ersteinrichtung, weil die Prüfung
    wiedergefundene Orte einträgt; eine laufende Installation prüft unter Wartung mit "Dateien prüfen"."""
    await _tun(zustand.nur_neu())
    return await pruefung_modul.pruefung.beginnen(pruefsummen=p.pruefsummen)


async def _nur_sichtbare(request: Request, ids: list[int]) -> set[int]:
    s = await sicht(request)
    return set(await sichtbar.nur_sichtbare(s, ids))


@router.get("/pruefung/bericht", response_model=Pruefbericht)
async def pruefbericht(request: Request, herunterladen: bool = False, z: Zugang = Depends(zugang)):
    """Erreichbar, wiedergefunden, fehlend; Bücher, die das Profil nicht sieht, fehlen in der Liste. `herunterladen`: als Datei."""
    b = await pruefung_modul.bericht()
    if not z.ohne_konto:
        sieht = await _nur_sichtbare(request, [e.buch_id for e in b.eintraege])
        b.eintraege = [e for e in b.eintraege if e.buch_id in sieht]
    if herunterladen:
        return JSONResponse(b.model_dump(mode="json"), headers={"Content-Disposition": 'attachment; filename="pruefbericht.json"'})
    return b


@router.post("/neuaufbau/ordner", response_model=Ordnerpruefung)
async def neuaufbau_ordner(w: OrdnerWahl, _z: Zugang = Depends(zugang)) -> Ordnerpruefung:
    """Zählt, was im Ordner liegt (unter dem Ordner der App); in der Kellerwolke ändert sich nichts."""
    return await _tun(neuaufbau.ordner_pruefen(w.pfad))


@router.post("/neuaufbau", response_model=Auftragsstand)
async def neuaufbau_starten(z: Zugang = Depends(zugang)) -> Auftragsstand:
    await _nach_dem_konto(z)
    await _tun(zustand.nur_neu())
    return await _tun(neuaufbau.neuaufbau.beginnen())


@router.get("/neuaufbau/bericht", response_model=Neuaufbaubericht)
async def neuaufbau_bericht(request: Request, z: Zugang = Depends(zugang)) -> Neuaufbaubericht:
    b = await neuaufbau.bericht()
    if not z.ohne_konto:
        sieht = await _nur_sichtbare(request, [e.buch_id for e in b.ohne_auszug + b.fehler if e.buch_id])
        b.ohne_auszug = [e for e in b.ohne_auszug if e.buch_id is None or e.buch_id in sieht]
        b.fehler = [e for e in b.fehler if e.buch_id is None or e.buch_id in sieht]
    return b


# -- Umzug auf dem neuen Gerät --------------------------------------------------------------------------------------------

@router.post("/umzug/verbinden", response_model=Umzugsergebnis)
async def umzug_verbinden(v: UmzugVerbinden, z: Zugang = Depends(zugang)) -> Umzugsergebnis:
    """Holt mit Adresse und Einmalcode Sicherung, Einstellungen und Schlüssel vom alten Gerät (nur über https) und beginnt das
    Einspielen als Auftrag."""
    await _pruefweg(z, v.adresse)
    return await _tun(umzug.verbinden(v.adresse, v.code))


@router.post("/originale", response_model=Auftragsstand)
async def originale(w: OriginaleWahl, _z: Zugang = Depends(zugang)) -> Auftragsstand:
    """Ohne Kellerwolke: "kopieren" holt die Originale vom alten Gerät, "ort" prüft nur den übernommenen Ort mit Prüfsummen."""
    return await _tun(umzug.originale_waehlen(w.weg))


# -- Wartung --------------------------------------------------------------------------------------------------------------

@router.post("/oeffnen", response_model=Einrichtung, dependencies=[EINSTELLUNGEN])
async def oeffnen() -> Einrichtung:
    """Unter Einstellungen, Wartung: dieselben Schritte wie "Neu beginnen" ohne Konto; ändert erst nach `uebernehmen`."""
    await _tun(wartung.oeffnen())
    return await zustand.lesen()


@router.post("/schliessen", response_model=Einrichtung, dependencies=[EINSTELLUNGEN])
async def schliessen() -> Einrichtung:
    """Ohne Übernehmen; alles Vorgemerkte fällt weg."""
    await wartung.schliessen()
    return await zustand.lesen()


@router.get("/aenderungen", response_model=Aenderungen, dependencies=[EINSTELLUNGEN])
async def aenderungen() -> Aenderungen:
    return await _tun(wartung.aenderungen())


@router.post("/uebernehmen", response_model=Uebernommen)
async def uebernehmen(u: Uebernehmen, p: Profil = EINSTELLUNGEN) -> Uebernommen:
    """Nur die genannten Änderungen, nur mit dem `stand` der Liste; danach ist der Assistent geschlossen."""
    return await _tun(wartung.uebernehmen(u.stand, u.ids, p))


# -- altes Gerät beim Umzug -----------------------------------------------------------------------------------------------

@umzug_router.post("/vorbereiten", response_model=UmzugVorbereitet, dependencies=[EINSTELLUNGEN])
async def umzug_vorbereiten() -> UmzugVorbereitet:
    """Frische Sicherung und Einmalcode; der Code steht nur in dieser Antwort."""
    return await umzug.vorbereiten()


@umzug_router.get("", response_model=Umzugsstand, dependencies=[EINSTELLUNGEN])
async def umzug_stand() -> Umzugsstand:
    return await umzug.stand()


@umzug_router.delete("", response_model=Umzugsstand, dependencies=[EINSTELLUNGEN])
async def umzug_beenden() -> Umzugsstand:
    """Code und Sitzung gelten nicht mehr; Bestand und Sicherung bleiben."""
    return await umzug.beenden()


@umzug_router.post("/einloesen", response_model=Umzugspaket)
async def umzug_einloesen(c: Einloesen) -> Umzugspaket:
    """Für das neue Gerät, ohne Konto: einmal, nur bis zum Ablauf, mit wenigen Versuchen (403 mit Grund)."""
    return await _tun(umzug.einloesen(c.code))


SitzungKopf = Annotated[str, Header(alias=umzug.KOPF)]


@umzug_router.get("/sicherung")
async def umzug_sicherung(sitzung: SitzungKopf = "") -> FileResponse:
    datei = await _tun(umzug.sicherungsdatei(sitzung))
    return FileResponse(datei, media_type="application/zip", filename=datei.name)


@umzug_router.get("/originale")
async def umzug_originale(sitzung: SitzungKopf = "") -> list[dict]:
    """`[{hash, name, groesse}]`: die Originale auf diesem Gerät."""
    return await _tun(umzug.originale(sitzung))


@umzug_router.get("/originale/{pruefsumme}")
async def umzug_original(pruefsumme: str, sitzung: SitzungKopf = "") -> FileResponse:
    """Mit Bereichen, damit ein unterbrochenes Kopieren an seinem Ende fortsetzt."""
    datei = await _tun(umzug.originaldatei(sitzung, pruefsumme))
    return FileResponse(datei, media_type="application/octet-stream", filename=datei.name, headers={"Accept-Ranges": "bytes"})


# -- Einstellungen der Kellerwolke ----------------------------------------------------------------------------------------

async def _einstellungen() -> Kellerwolkeneinstellungen:
    return Kellerwolkeneinstellungen(persoenlich=await persoenlich.an(), sicherungen_ablegen=await wolke_sicherungen.an())


@kellerwolke_router.get("/einstellungen", response_model=Kellerwolkeneinstellungen, dependencies=[EINSTELLUNGEN])
async def kellerwolke_einstellungen() -> Kellerwolkeneinstellungen:
    return await _einstellungen()


@kellerwolke_router.put("/einstellungen", response_model=Kellerwolkeneinstellungen, dependencies=[EINSTELLUNGEN])
async def kellerwolke_einstellen(e: KellerwolkeneinstellungenEingabe) -> Kellerwolkeneinstellungen:
    """Persönliches einschalten und mit `entfernen` ausschalten nur mit dem `stand` aus den Folgen; ausschalten ohne Entfernen
    lässt alles in der Kellerwolke, wie es ist."""
    if e.persoenlich is not None:
        await _tun(nachfuehren_modul.schalten(e.persoenlich, e.entfernen, e.stand))
    elif e.entfernen:
        raise HTTPException(422, "Entfernen: nur zusammen mit persoenlich false")
    if e.sicherungen_ablegen is not None:
        await wolke_sicherungen.setzen(e.sicherungen_ablegen)
    return await _einstellungen()


@kellerwolke_router.get("/persoenlich/folgen", response_model=Persoenlichfolgen, dependencies=[EINSTELLUNGEN])
async def persoenlich_folgen() -> Persoenlichfolgen:
    """Was Einschalten schreibt und Ausschalten mit Entfernen in den Papierkorb legt; die Daten in der App bleiben immer."""
    return await nachfuehren_modul.folgen()


@kellerwolke_router.get("/persoenlich/stand", response_model=Auftragsstand, dependencies=[EINSTELLUNGEN])
async def persoenlich_stand() -> Auftragsstand:
    return await nachfuehren.stand()
