"""Schutz der Wege: Menschen mit einer Anmeldung der Kellerwolke (Sitzung oder gekoppeltes Gerät), andere Apps mit
ihrem App-Schlüssel nur für `fundus/*`. Geprüft wird über den Baustein des Appkern (`core/anmeldung.py`).

Familie (BF-78): nach dem Konto des Geräts gilt das gewählte Profil (`familie/sitzung.py`, Kopf `X-Profil`). `verify_token`
löst es je Anfrage auf, legt es mit seiner Sicht auf die Bücher an die Anfrage (`request.state`) und weist jeden Weg ab, dessen
Pfad ein Buch nennt, das dieses Profil nicht sieht (404, wie ein Buch, das es nicht gibt). Was ein Weg darüber hinaus braucht,
sagt `braucht("fähigkeit")` (403). Fehlt ein gültiges Profil, kommt 401 mit `code` "profil_waehlen" (das Konto bleibt
angemeldet). Nur die Profilwahl selbst kommt mit dem Konto allein aus (`verify_konto`)."""

from fastapi import Depends, HTTPException, Request, status
from appkern.anmeldung import AnmeldungsFehler, Konto
from appkern.anmeldung.api import COOKIE

from backend.app.core.anmeldung import anmeldung, eigener_zugang, erlaubte_apps
from backend.app.core.fehlerantworten import MitCode
from backend.app.familie import profile as familie_profile, rechte, sichtbar, sitzung
from backend.app.familie.modelle import Profil
from backend.app.familie.stufen import stufenbuch

KOPF = "x-kellerwolke-sitzung"
PROFIL_WAEHLEN = "profil_waehlen"        # 401 mit diesem code: das Gerät bleibt angemeldet, nur ein Profil fehlt (BF-78)


def _aus_kopf(request: Request) -> str:
    art, _, wert = request.headers.get("authorization", "").partition(" ")
    return request.headers.get(KOPF) or (wert.strip() if art.lower() == "bearer" else "")


async def _konto(token: str) -> Konto:
    try:
        konto = await anmeldung.pruefen(token)
    except AnmeldungsFehler as f:
        raise HTTPException(status_code=f.status, detail=f.meldung) from f
    if konto is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Anmeldung erforderlich", headers={"WWW-Authenticate": "Bearer"})
    return konto


async def _mensch(token: str) -> Konto:
    konto = await _konto(token)
    if not konto.mensch:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Andere Apps nutzen die Wege fundus/*")
    return konto


async def _profil_anlegen(request: Request, konto: Konto, inhalt: bool) -> None:
    """Profil und Sicht dieser Anfrage; ein Buch im Pfad, das das Profil nicht sieht, gibt es nicht."""
    try:
        p = await sitzung.aufloesen(request, inhalt)
    except sitzung.ProfilNoetig as f:
        raise MitCode(status.HTTP_401_UNAUTHORIZED, f.meldung, PROFIL_WAEHLEN, headers={"WWW-Authenticate": "Profil"}) from f
    if p.name_vom_konto:
        p = await familie_profile.name_vom_konto(p, konto.name)
    request.state.profil, request.state.sicht = p, sichtbar.Sicht.von(p)
    try:
        await sichtbar.pfad_pruefen(request.state.sicht, request.path_params)
    except sichtbar.Verborgen as f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f.meldung) from f


async def verify_konto(request: Request) -> Konto:
    """Nur das Konto des Geräts, ohne Profil: für die Profilwahl."""
    return await _mensch(_aus_kopf(request))


async def verify_konto_inhalt(request: Request) -> Konto:
    """Nur das Konto, für Bilder ohne Kopf, die nichts Persönliches zeigen (Hintergründe der Gestaltung, auch vor der Wahl)."""
    return await _mensch(_aus_kopf(request) or request.cookies.get(COOKIE, ""))


async def verify_token(request: Request) -> Konto:
    """Ein Mensch mit gültiger Anmeldung der Kellerwolke und einem Profil."""
    konto = await _mensch(_aus_kopf(request))
    await _profil_anlegen(request, konto, inhalt=False)
    return konto


async def verify_token_inhalt(request: Request) -> Konto:
    """Wie `verify_token`, für Adressen ohne Kopf (Bilder, Dateien, Ereignisströme): die Anmeldung kommt dann aus dem
    Inhalts-Cookie, das `POST /api/anmeldung/zugang` setzt, das Profil aus dem Cookie der Profilwahl. In Adressen steht beides
    nie, sonst landet es in Verläufen, Protokollen und Fehlermeldungen. Nur für lesende Wege."""
    konto = await _mensch(_aus_kopf(request) or request.cookies.get(COOKIE, ""))
    await _profil_anlegen(request, konto, inhalt=True)
    return konto


async def profil(request: Request, _konto: Konto = Depends(verify_token)) -> Profil:
    """Das Profil dieser Anfrage."""
    return request.state.profil


async def sicht(request: Request, _konto: Konto = Depends(verify_token)) -> sichtbar.Sicht:
    """Welche Bücher das Profil dieser Anfrage sieht."""
    return request.state.sicht


async def sicht_inhalt(request: Request, _konto: Konto = Depends(verify_token_inhalt)) -> sichtbar.Sicht:
    return request.state.sicht


def braucht(faehigkeit: str, *, inhalt: bool = False):
    """Der Weg braucht diese Fähigkeit (stufen.json); sonst 403. `inhalt`: für Wege ohne Kopf (Cookie)."""
    beschreibung = stufenbuch().faehigkeiten[faehigkeit]           # ein Tippfehler fällt beim Start auf
    anmelden = verify_token_inhalt if inhalt else verify_token

    async def pruefen(request: Request, _konto: Konto = Depends(anmelden)) -> Profil:
        p: Profil = request.state.profil
        if not rechte.darf(p, faehigkeit):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Das darf dieses Profil nicht: {beschreibung}")
        return p

    pruefen.__name__ = f"braucht_{faehigkeit}"
    return pruefen


async def app_pruefen(request: Request) -> Konto:
    """Eine andere App mit ihrem App-Schlüssel der Kellerwolke, die laut `FUNDUS_APPS` den Bestand lesen darf."""
    await eigener_zugang.erfragen()              # das Konto, dem BücherFreunde gehört, muss bekannt sein
    token = _aus_kopf(request)
    if not token.startswith("kw_app_"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "App-Schlüssel der Kellerwolke erwartet",
                            headers={"WWW-Authenticate": "Bearer"})
    konto = await _konto(token)
    if (konto.app or "").lower() not in erlaubte_apps():
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Die App {konto.app or 'ohne Namen'} darf den Bestand nicht lesen")
    try:
        await sichtbar.pfad_pruefen(sichtbar.APPS, request.path_params)       # private Bücher gibt es für Apps nicht
    except sichtbar.Verborgen as f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f.meldung) from f
    return konto


__all__ = ["app_pruefen", "braucht", "profil", "sicht", "sicht_inhalt", "verify_konto", "verify_konto_inhalt", "verify_token", "verify_token_inhalt"]
