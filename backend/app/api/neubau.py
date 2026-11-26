"""Wege des Neubaus rund um Ablage und Verbindungen: Suche nach Bedeutung, Verbindungen, Orte, Ablage eines Buchs."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.ablage import originale, orte
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core.anschluesse import anschluesse
from backend.app.core.auth import verify_token
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services import bedeutung
from backend.app.services.ausfuehren import NICHT_ZUGELASSEN, sandbox
from backend.app.services.ki import ki
from backend.app.services.storage import get_sidecar_path

router = APIRouter(prefix="/api", tags=["Neubau"])


@router.get("/suche/bedeutung")
async def suche_bedeutung(q: str = Query(min_length=1, max_length=1000), n: int = Query(20, ge=1, le=50), buch: int | None = None, _=Depends(verify_token)):
    return await bedeutung.suchen(q, n, buch)


async def _kellerwolke() -> dict:
    eintrag = {"kennung": "kellerwolke", "name": "Kellerwolke"}
    if not wolke.bereit:
        return eintrag | {"stand": "schlecht", "text": "der App-Zugang fehlt, Dateien liegen auf dem Gerät"}
    try:
        s = await wolke.speicher()
    except WolkeFehler as f:
        return eintrag | {"stand": "schlecht", "text": f.meldung}
    if not s.get("verfuegbar"):
        return eintrag | {"stand": "schlecht", "text": "Datenträger fehlt"}
    return eintrag | {"stand": "gut", "text": f"{(s.get('frei') or 0) / 1e12:.1f} TB frei".replace(".", ",")}


async def _codeschmiede() -> dict:
    eintrag = {"kennung": "codeschmiede", "name": "Codeschmiede"}
    s = await sandbox.stand()
    if s.bereit:
        return eintrag | {"stand": "gut", "text": "Sandbox für " + ", ".join(a.sprache for a in s.sprachen)}
    return eintrag | {"stand": "schlecht" if s.grund == NICHT_ZUGELASSEN else "warn", "text": s.grund}


async def _leitstelle() -> dict:
    eintrag = {"kennung": "leitstelle", "name": "Leitstelle"}
    s = await ki.stand()
    if s.nutzbar:
        return eintrag | ({"stand": "warn", "text": s.grund} if s.grund else {"stand": "gut", "text": f"KI mit {s.modell}"})
    return eintrag | {"stand": "schlecht", "text": s.grund}


@router.get("/verbindungen")
async def verbindungen(_=Depends(verify_token)):
    """Nur, was angeschlossen ist."""
    a, aus = anschluesse(), []
    if settings.kellerwolke_url:
        aus.append(await _kellerwolke())
    if a.bedeutung:
        aus.append(await bedeutung.stand())
        probe = await bedeutung.suchen("Buch", 1)
        aus.append({"kennung": "rechner", "name": "MacBook", "stand": "gut" if probe["verfuegbar"] else "warn", "text": "rechnet die Bedeutung" if probe["verfuegbar"] else probe["grund"] or "schläft"})
    if a.ausfuehren:
        aus.append(await _codeschmiede())
    if settings.leitstelle_adresse.strip():
        aus.append(await _leitstelle())
    return aus


@router.get("/orte")
async def orte_stand(_=Depends(verify_token)):
    return await asyncio.to_thread(orte.stand)


@router.get("/config/oberflaeche")
async def oberflaeche(_=Depends(verify_token)):
    a = anschluesse()
    return {"assistent": a.assistent, "anschluesse": a}


@router.get("/books/{buch}/ablage")
async def ablage(buch: int, _=Depends(verify_token)):
    z = await db.fetch_one("SELECT hash, page_count, file_size FROM books WHERE id = ?", (buch,))
    if z is None:
        raise HTTPException(404, "Buch nicht gefunden")
    e = await asyncio.to_thread(originale.eintrag, z["hash"])
    pfad = (await db.fetch_one("SELECT pfad FROM ablage_datei WHERE hash = ?", (z["hash"],)) or {}).get("pfad", "")
    text = get_sidecar_path(z["hash"], "fulltext.txt")
    zeichen = text.stat().st_size if text.exists() else 0
    mit_bedeutung = anschluesse().bedeutung
    wissen = await bedeutung.buch_stand(buch) if zeichen and mit_bedeutung else None
    gut = bool(wissen and wissen["zustand"] == "durchsuchbar")
    tausend = f"{wissen['abschnitte']:,}".replace(",", ".") if wissen else ""
    return {"wolke": {"pfad": pfad or ("auf dem Gerät" if e is None else e["name"]), "groesse": z["file_size"], "sha256": z["hash"], "in_der_wolke": e is not None},
            "volltext": {"seiten": z["page_count"] or 0, "zeichen": zeichen},
            "wissen": None if not mit_bedeutung else {"stand": "gut" if gut else "warn", "abschnitte": wissen["abschnitte"] if wissen else None,
                       "text": f"{tausend} Abschnitte nach Bedeutung erfasst" if gut else "folgt mit dem nächsten Abgleich" if zeichen else "kein Text, nicht nach Bedeutung zu finden"}}
