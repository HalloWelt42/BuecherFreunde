"""Wege der Familie (BF-78, docs/neubau/FAMILIE.md, Schnittstelle; Ergänzungen in docs/neubau/SCHNITTSTELLE.md, Familie).
Die Arbeit tut das Paket backend/app/familie; hier stehen nur die Wege. Die Profilwahl braucht nur das Konto des Geräts, alles
andere ein Profil."""

from __future__ import annotations

from appkern.anmeldung import AnmeldungsFehler, Konto
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from backend.app.api.books import buecher_mit_nummern
from backend.app.core import auth
from backend.app.core.auth import braucht, profil, verify_konto
from backend.app.familie import einblick, freigaben, geraet, ich, lesezeit, profile, rechte, sitzung
from backend.app.familie.fehler import Familienfehler, ZuVieleVersuche
from backend.app.familie.modelle import (
    Einblicksantwort, Familie, Freigabeauftrag, Freigaben, Geraetestand, GeraetBinden, GeraetLoesen, Gewaehlt, Ich, Katze, KatzeName,
    Lesezeitmeldung, Lesezeitstand, Loeschfolgen, PinSetzen, PinVergessen, Profil, ProfilAenderung, ProfilEintrag, ProfilNeu,
    Stufenansicht, Verlassen, Wahl,
)

router = APIRouter(prefix="/api/familie", tags=["Familie"])
COOKIE_DAUER = 400 * 24 * 60 * 60                  # das Cookie gilt so lange wie der Schlüssel; abgemeldet wird mit verlassen


def _http(f: Familienfehler) -> HTTPException:
    kopf = {"Retry-After": str(f.nochmal_in)} if isinstance(f, ZuVieleVersuche) else None
    return HTTPException(f.status, f.meldung, headers=kopf)


def _https(request: Request) -> bool:
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"


async def _ziel(pid: str) -> Profil:
    try:
        return await profile.noetig(pid)
    except Familienfehler as f:
        raise _http(f) from f


async def _einsehbar(pid: str, von: Profil) -> Profil:
    ziel = await _ziel(pid)
    if not rechte.darf_einsehen(von, ziel):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Das sehen nur die Eltern und das Kind selbst")
    return ziel


async def _kind_zum_freigeben(pid: str, von: Profil) -> Profil:
    ziel = await _ziel(pid)
    if not ziel.kind:
        raise HTTPException(422, "Freigaben gibt es nur für Kinder")
    if not rechte.darf(von, "freigeben"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Freigeben dürfen nur Erwachsene")
    return ziel


async def _betrachter(s: sitzung.Sitzung | None) -> Profil | None:
    """Wer fragt, ohne dass ein Profil sein muss: das des Schlüssels, sonst im Einzelbetrieb das einzige."""
    if s is not None:
        return s.profil
    return None if await profile.braucht_wahl() else await profile.einziges()


# -- Profilwahl (nur mit dem Konto des Geräts) --------------------------------------------------------------------------------

@router.get("", response_model=Familie)
async def familie(request: Request, _konto: Konto = Depends(verify_konto)) -> Familie:
    """Die Profile zur Wahl, ohne Geheimnisse; ein fest gestelltes Gerät zeigt nur sein Profil, außer die Wahl ist nach der PIN
    der Eltern offen oder hier ist ein Erwachsener so angemeldet. Geburtsjahr und Einstellungen sieht, wer ändern darf."""
    b = await geraet.bindung(sitzung.geraet_aus(request))
    s = await sitzung.zum_schluessel(sitzung.schluessel_aus(request, inhalt=True))
    frei = b is None or b.offen or (s is not None and s.ueber_bindung)
    gebunden = None if frei else b.profil_id
    betrachter = await _betrachter(s)
    alle = [p for p in await profile.alle() if gebunden is None or p.id == gebunden]
    return Familie(profile=[ich.eintrag_fuer(p, betrachter) for p in alle], braucht_wahl=await profile.braucht_wahl(),
                   aktiv=s.profil.id if s and (gebunden is None or s.profil.id == gebunden) else None,
                   geraet=Geraetestand(gebunden_an=gebunden, fest_auf=b.profil_id if b else None, offen=bool(b and b.offen)))


@router.get("/stufen", response_model=Stufenansicht)
async def stufen(_konto: Konto = Depends(verify_konto)) -> Stufenansicht:
    return ich.stufenansicht()


@router.post("/wahl", response_model=Gewaehlt)
async def waehlen(w: Wahl, request: Request, response: Response, _konto: Konto = Depends(verify_konto)) -> Gewaehlt:
    """PIN oder Bild-PIN prüfen und einen Profilschlüssel ausgeben, auch im Einzelbetrieb; für Bilder, Dateien und Ströme auch
    als Cookie."""
    try:
        schluessel, p = await sitzung.waehlen(w, sitzung.geraet_aus(request), sitzung.schluessel_aus(request, inhalt=True))
    except Familienfehler as f:
        raise _http(f) from f
    response.set_cookie(sitzung.COOKIE, schluessel, max_age=COOKIE_DAUER, path="/api", httponly=True, samesite="strict", secure=_https(request))
    return Gewaehlt(schluessel=schluessel, profil=await ich.ich(p))


@router.post("/verlassen", status_code=204, response_model=None)
async def verlassen(request: Request, response: Response, v: Verlassen | None = None, _konto: Konto = Depends(verify_konto)) -> Response:
    """Profil verlassen; auf einem fest gestellten Gerät nur mit der PIN der Eltern, dann ist die Profilwahl hier eine Weile
    offen (die Bindung bleibt, lösen nur mit DELETE /api/familie/geraet)."""
    try:
        await sitzung.verlassen(sitzung.schluessel_aus(request, inhalt=True), sitzung.geraet_aus(request), (v or Verlassen()).eltern_pin)
    except Familienfehler as f:
        raise _http(f) from f
    response.delete_cookie(sitzung.COOKIE, path="/api", httponly=True, samesite="strict", secure=_https(request))
    response.status_code = 204
    return response


@router.post("/geraet", status_code=204, response_model=None)
async def geraet_binden(g: GeraetBinden, request: Request, _konto: Konto = Depends(verify_konto)) -> None:
    """Dieses Gerät fest auf ein Kind stellen; nur mit der PIN der Eltern."""
    try:
        await geraet.binden(sitzung.geraet_aus(request), g.profil_id, g.eltern_pin)
    except Familienfehler as f:
        raise _http(f) from f


@router.delete("/geraet", status_code=204, response_model=None)
async def geraet_loesen(request: Request, g: GeraetLoesen | None = None, _konto: Konto = Depends(verify_konto)) -> None:
    """Die Bindung lösen: mit der PIN der Eltern, oder als Verwaltung ohne sie."""
    try:
        await geraet.loesen(sitzung.geraet_aus(request), (g or GeraetLoesen()).eltern_pin,
                            await sitzung.profil_zum_schluessel(sitzung.schluessel_aus(request)))
    except Familienfehler as f:
        raise _http(f) from f


@router.post("/profile/{pid}/pin/vergessen", response_model=Familie)
async def pin_vergessen(pid: str, v: PinVergessen, request: Request, konto: Konto = Depends(verify_konto)) -> Familie:
    """Die PIN der Verwaltung fällt weg, wenn sich das Konto des Geräts erneut anmeldet (Kennung und Passwort)."""
    try:
        token, neu = await auth.anmeldung.anmelden(v.kennung, v.passwort)
    except AnmeldungsFehler as f:
        raise HTTPException(f.status, f.meldung) from f
    await auth.anmeldung.abmelden(token)
    if neu.id != konto.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Das ist nicht das Konto, mit dem dieses Gerät angemeldet ist")
    try:
        await profile.pin_vergessen(pid)
    except Familienfehler as f:
        raise _http(f) from f
    return await familie(request, konto)


# -- Das eigene Profil ---------------------------------------------------------------------------------------------------------

@router.get("/ich", response_model=Ich)
async def ich_lesen(p: Profil = Depends(profil)) -> Ich:
    return await ich.ich(p)


@router.patch("/ich/katze", response_model=Katze)
async def katze_benennen(k: KatzeName, p: Profil = Depends(profil)) -> Katze:
    """Das Kind gibt seiner Katze einen Namen."""
    return ich.katze(await profile.katze_benennen(p, k.name))


@router.post("/lesezeit", response_model=Lesezeitstand)
async def lesezeit_melden(m: Lesezeitmeldung, p: Profil = Depends(profil)) -> Lesezeitstand:
    """Der Leser meldet im Takt, wie lange gelesen oder vorgelesen wurde."""
    return await lesezeit.melden(p, m)


# -- Profile verwalten ---------------------------------------------------------------------------------------------------------

@router.post("/profile", response_model=ProfilEintrag, status_code=201)
async def profil_anlegen(neu: ProfilNeu, p: Profil = Depends(profil)) -> ProfilEintrag:
    try:
        return ich.eintrag(await profile.anlegen(neu, p), mit_angaben=True)
    except Familienfehler as f:
        raise _http(f) from f


@router.get("/profile/{pid}", response_model=ProfilEintrag)
async def profil_lesen(pid: str, p: Profil = Depends(profil)) -> ProfilEintrag:
    ziel = await _ziel(pid)
    if not (ziel.id == p.id or rechte.darf_aendern(p, ziel, None)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dieses Profil sehen nur die Verwaltung und die Eltern")
    return ich.eintrag(ziel, mit_angaben=True)


@router.patch("/profile/{pid}", response_model=ProfilEintrag)
async def profil_aendern(pid: str, a: ProfilAenderung, p: Profil = Depends(profil)) -> ProfilEintrag:
    try:
        return ich.eintrag(await profile.aendern(pid, a, p), mit_angaben=True)
    except Familienfehler as f:
        raise _http(f) from f


@router.put("/profile/{pid}/pin", response_model=ProfilEintrag)
async def pin_setzen(pid: str, eingabe: PinSetzen, p: Profil = Depends(profil)) -> ProfilEintrag:
    try:
        return ich.eintrag(await profile.pin_setzen(pid, eingabe, p), mit_angaben=True)
    except Familienfehler as f:
        raise _http(f) from f


@router.get("/profile/{pid}/loeschfolgen", response_model=Loeschfolgen)
async def loeschfolgen(pid: str, _p: Profil = Depends(braucht("profile"))) -> Loeschfolgen:
    """Was mit dem Profil geht; seine privaten Bücher bleiben und sind danach für alle sichtbar."""
    try:
        return await profile.loeschfolgen(pid)
    except Familienfehler as f:
        raise _http(f) from f


@router.delete("/profile/{pid}", status_code=204, response_model=None)
async def profil_loeschen(pid: str, stand: str = Query(max_length=64), p: Profil = Depends(braucht("profile"))) -> None:
    """Nur nach den Folgen: `stand` aus GET .../loeschfolgen; hat sich seitdem etwas geändert, 409."""
    try:
        await profile.loeschen(pid, stand, p)
    except Familienfehler as f:
        raise _http(f) from f


# -- Freigaben und Einblick ----------------------------------------------------------------------------------------------------

async def _freigaben(kind: Profil, betrachter: Profil) -> Freigaben:
    nummern = await freigaben.buecher(kind)
    buecher = await buecher_mit_nummern(nummern, betrachter)
    return Freigaben(kategorien=await freigaben.kategorien(kind), buecher=[buecher[n] for n in nummern if n in buecher])


@router.get("/profile/{pid}/freigaben", response_model=Freigaben)
async def freigaben_lesen(pid: str, p: Profil = Depends(profil)) -> Freigaben:
    """Freigegebene Kategorien mit ihrer Zahl und die einzeln freigegebenen Bücher, mit Altersangabe."""
    return await _freigaben(await _einsehbar(pid, p), p)


@router.post("/profile/{pid}/freigaben", response_model=Freigaben)
async def freigeben(pid: str, auftrag: Freigabeauftrag, p: Profil = Depends(profil)) -> Freigaben:
    kind = await _kind_zum_freigeben(pid, p)
    try:
        await freigaben.hinzufuegen(kind, auftrag, p)
    except Familienfehler as f:
        raise _http(f) from f
    return await _freigaben(kind, p)


@router.delete("/profile/{pid}/freigaben", response_model=Freigaben)
async def freigabe_zuruecknehmen(pid: str, auftrag: Freigabeauftrag, p: Profil = Depends(profil)) -> Freigaben:
    kind = await _kind_zum_freigeben(pid, p)
    await freigaben.entfernen(kind, auftrag)
    return await _freigaben(kind, p)


@router.get("/profile/{pid}/einblick", response_model=Einblicksantwort)
async def einblick_lesen(pid: str, p: Profil = Depends(profil)) -> Einblicksantwort:
    ziel = await _einsehbar(pid, p)
    if not ziel.kind:
        raise HTTPException(422, "Einblick gibt es nur in Kinderprofile")
    return await einblick.einblick(ziel)
