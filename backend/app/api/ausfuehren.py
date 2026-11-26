"""Schnittstelle zum Ausführen von Codestellen (BF-29): Stand der Sandbox, ein Lauf mit Aufzeichnung, Funktionen je
PHP-Fassung für den Editor, die Codestellen eines Buchs mit ihrer Vorprüfung, Stand und Steuerung der Vorprüfung."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.codestellen.dienst import Stand, codestellen
from backend.app.codestellen.modelle import Codestelle, Vorpruefung
from backend.app.codestellen.vorpruefung import VorpruefungStand, ergebnisse, vorpruefer
from backend.app.core.auth import verify_token
from backend.app.services.ausfuehren import HOECHSTENS_ZEICHEN, Ausfuehrstand, Lauf, sandbox
from backend.app.models.grenzen import SEITEN_HOECHSTENS, Nr

router = APIRouter(prefix="/api", tags=["Ausführen"], dependencies=[Depends(verify_token)])


class Probe(BaseModel):
    code: str = Field(min_length=1, max_length=HOECHSTENS_ZEICHEN)
    sprache: Literal["python", "javascript", "php"]
    fassung: str = Field("", max_length=10, description="PHP-Fassung, etwa 8.3; leer: die neueste")
    eingabe: list[str] = Field(default_factory=list, max_length=50, description="Zeilen für input(), prompt() oder STDIN")


class StelleAntwort(Codestelle):
    ausfuehrbar: bool                          # Sprache der Sandbox mit sicherem Befund, die Sandbox antwortet
    vorpruefung: Vorpruefung | None = None     # nur bei ausführbaren Stellen; "offen", solange nicht geprüft


class CodestellenAntwort(BaseModel):
    buch: int
    stand: Stand                               # erkannt; ausstehend (kommt gleich dran); ohne (Format ohne Codeblöcke)
    format: str | None = None
    grund: str = ""                            # warum die Datei nicht gelesen werden konnte
    anzahl: int = 0                            # Stellen im ganzen Buch
    stellen: list[StelleAntwort] = Field(default_factory=list)


@router.get("/ausfuehren", response_model=Ausfuehrstand)
async def stand() -> Ausfuehrstand:
    """Ob die Sandbox bereitsteht, welche Sprachen (bei PHP mit Fassungen) und ob aufgezeichnet wird; sonst der Grund."""
    return await sandbox.stand()


@router.post("/ausfuehren", response_model=Lauf)
async def laufen(probe: Probe) -> Lauf:
    """Den Code in der Sandbox laufen lassen, mit Aufzeichnung für den Debugger, wo die Sprache sie hat. Geht es nicht,
    steht der Grund in `grund`."""
    return await sandbox.laufen(probe.code, probe.sprache, probe.fassung, probe.eingabe)


@router.get("/ausfuehren/funktionen/php", response_model=dict[str, list[str]])
async def funktionen_php() -> dict[str, list[str]]:
    """Je PHP-Fassung die eingebauten Funktionen (klein geschrieben); leer, wenn die Codeschmiede nicht antwortet."""
    return await sandbox.funktionen_php()


@router.get("/ausfuehren/vorpruefung", response_model=VorpruefungStand)
async def vorpruefung_stand() -> VorpruefungStand:
    return await vorpruefer.stand()


@router.post("/ausfuehren/vorpruefung/anhalten", response_model=VorpruefungStand)
async def vorpruefung_anhalten() -> VorpruefungStand:
    vorpruefer.anhalten()
    return await vorpruefer.stand()


@router.post("/ausfuehren/vorpruefung/fortsetzen", response_model=VorpruefungStand)
async def vorpruefung_fortsetzen() -> VorpruefungStand:
    vorpruefer.fortsetzen()
    return await vorpruefer.stand()


@router.get("/books/{buch}/codestellen", response_model=CodestellenAntwort)
async def buch_codestellen(buch: Nr, von: int | None = Query(None, ge=1, le=SEITEN_HOECHSTENS, description="erste Dateiseite (nur PDF)"),
                           bis: int | None = Query(None, ge=1, le=SEITEN_HOECHSTENS, description="letzte Dateiseite (nur PDF)")) -> CodestellenAntwort:
    """Die Codestellen eines Buchs; mit `von` und `bis` nur die, die in diese Seiten hineinreichen (Ketten ganz). Fehlt
    die Erkennung noch, kommt das Buch sofort an die Reihe (`stand: ausstehend`)."""
    try:
        art, begleiter = await codestellen.stellen(buch)
    except KeyError:
        raise HTTPException(404, "Buch nicht gefunden") from None
    if begleiter is None:
        return CodestellenAntwort(buch=buch, stand=art)
    unten, oben = von or 1, bis or 10**9
    gewaehlt = [s for s in begleiter.stellen
                if begleiter.format != "pdf" or any(t.seite is not None and unten <= t.seite <= oben for t in s.teile)]
    sprachen = await sandbox.sprachen()
    laufbar = {id(s) for s in gewaehlt if s.sicher and s.sprache in sprachen}
    gemerkt = await ergebnisse([(s.sprache, s.pruefsumme) for s in gewaehlt if id(s) in laufbar and s.sprache])
    offen = Vorpruefung()
    return CodestellenAntwort(
        buch=buch, stand=art, format=begleiter.format, grund=begleiter.grund, anzahl=len(begleiter.stellen),
        stellen=[StelleAntwort(**s.model_dump(), ausfuehrbar=id(s) in laufbar,
                               vorpruefung=gemerkt.get((s.sprache or "", s.pruefsumme), offen) if id(s) in laufbar else None)
                 for s in gewaehlt])
