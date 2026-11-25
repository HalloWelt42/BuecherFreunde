"""Wege des Neubaus rund um Ablage und Verbindungen: Suche nach Bedeutung, Verbindungen, Orte, Ablage eines Buchs."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.ablage import originale, orte
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core.auth import verify_token
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services import bedeutung
from backend.app.services.storage import get_sidecar_path

router = APIRouter(prefix="/api", tags=["Neubau"])


@router.get("/suche/bedeutung")
async def suche_bedeutung(q: str = Query(min_length=1, max_length=1000), n: int = Query(20, ge=1, le=50), buch: int | None = None, _=Depends(verify_token)):
    return await bedeutung.suchen(q, n, buch)


@router.get("/verbindungen")
async def verbindungen(_=Depends(verify_token)):
    aus = []
    if not wolke.bereit:
        aus.append({"kennung": "kellerwolke", "name": "Kellerwolke", "stand": "warn", "text": "nicht verbunden, Dateien liegen auf dem Gerät"})
    else:
        try:
            s = await wolke.speicher()
            aus.append({"kennung": "kellerwolke", "name": "Kellerwolke", "stand": "gut" if s.get("verfuegbar") else "schlecht",
                        "text": f"{(s.get('frei') or 0) / 1e12:.1f} TB frei".replace(".", ",") if s.get("verfuegbar") else "Datenträger fehlt"})
        except WolkeFehler as f:
            aus.append({"kennung": "kellerwolke", "name": "Kellerwolke", "stand": "schlecht", "text": f.meldung})
    aus.append(await bedeutung.stand())
    probe = await bedeutung.suchen("Buch", 1)
    aus.append({"kennung": "rechner", "name": "MacBook", "stand": "gut" if probe["verfuegbar"] else "warn", "text": "rechnet die Bedeutung" if probe["verfuegbar"] else probe["grund"] or "schläft"})
    return aus


@router.get("/orte")
async def orte_stand(_=Depends(verify_token)):
    return await asyncio.to_thread(orte.stand)


@router.get("/config/oberflaeche")
async def oberflaeche(_=Depends(verify_token)):
    return {"assistent": settings.assistent_url}


@router.get("/books/{buch}/ablage")
async def ablage(buch: int, _=Depends(verify_token)):
    z = await db.fetch_one("SELECT hash, page_count, file_size FROM books WHERE id = ?", (buch,))
    if z is None:
        raise HTTPException(404, "Buch nicht gefunden")
    e = await asyncio.to_thread(originale.eintrag, z["hash"])
    pfad = (await db.fetch_one("SELECT pfad FROM ablage_datei WHERE hash = ?", (z["hash"],)) or {}).get("pfad", "")
    text = get_sidecar_path(z["hash"], "fulltext.txt")
    zeichen = text.stat().st_size if text.exists() else 0
    return {"wolke": {"pfad": pfad or ("auf dem Gerät" if e is None else e["name"]), "groesse": z["file_size"], "sha256": z["hash"], "in_der_wolke": e is not None},
            "volltext": {"seiten": z["page_count"] or 0, "zeichen": zeichen},
            "wissen": {"stand": "gut" if zeichen and settings.fundus_url else "warn", "text": "nach Bedeutung erfasst, sobald der Fundus abgeglichen hat" if zeichen else "kein Text, nicht nach Bedeutung zu finden"}}
