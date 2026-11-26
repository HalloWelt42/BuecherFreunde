"""Wege des Neubaus rund um Ablage und Verbindungen: Suche nach Bedeutung, Verbindungen, Orte, Ablage eines Buchs."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.ablage import originale, orte
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core.anschluesse import anschluesse
from backend.app.core.auth import braucht, sicht, verify_konto, verify_token
from backend.app.familie import sichtbar
from backend.app.familie.sichtbar import Sicht
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services import bedeutung, gespraech, nachschlagen
from backend.app.services.ausfuehren import NICHT_ZUGELASSEN, sandbox
from backend.app.services.ki import ki
from backend.app.services.lexikon import Lexikon
from backend.app.services.storage import get_sidecar_path
from backend.app.models.grenzen import Nr

router = APIRouter(prefix="/api", tags=["Neubau"])


@router.get("/suche/bedeutung", dependencies=[Depends(braucht("ki"))])
async def suche_bedeutung(q: str = Query(min_length=1, max_length=1000), n: int = Query(20, ge=1, le=50), buch: Nr | None = None,
                          s: Sicht = Depends(sicht)):
    """Treffer nur in Büchern, die das Profil sieht (BF-78)."""
    ergebnis = await bedeutung.suchen(q, n, buch)
    sieht = set(await sichtbar.nur_sichtbare(s, [t["buch_id"] for t in ergebnis["treffer"]]))
    return ergebnis | {"treffer": [t for t in ergebnis["treffer"] if t["buch_id"] in sieht]}


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


async def _assistent() -> dict:
    farbe, text = await gespraech.stand()
    return {"kennung": "assistent", "name": "Assistent", "stand": farbe, "text": text}


async def _nachschlag(lexikon: Lexikon) -> dict:
    farbe, text = await lexikon.stand()
    return {"kennung": "nachschlag", "name": "Nachschlag" if lexikon.art == "nachschlag" else "Lexikon im Netz", "stand": farbe, "text": text}


FRIST_S = 8.0                     # so lange darf eine Prüfung dauern; die Liste wartet nie auf einen hängenden Dienst


async def _mit_frist(kennung: str, name: str, pruefung: Awaitable[dict]) -> dict:
    try:
        return await asyncio.wait_for(pruefung, FRIST_S)
    except TimeoutError:
        return {"kennung": kennung, "name": name, "stand": "schlecht", "text": f"antwortet nicht binnen {FRIST_S:.0f} Sekunden"}


@router.get("/verbindungen", dependencies=[Depends(braucht("ki"))])
async def verbindungen(_=Depends(verify_token)):
    """Nur, was angeschlossen ist; alle zugleich geprüft, jede mit Frist."""
    a, pruefungen = anschluesse(), []
    if settings.kellerwolke_url:
        pruefungen.append(("kellerwolke", "Kellerwolke", _kellerwolke()))
    if a.bedeutung:
        pruefungen.append(("fundus", "Fundus", bedeutung.stand()))
    if a.ausfuehren:
        pruefungen.append(("codeschmiede", "Codeschmiede", _codeschmiede()))
    if settings.leitstelle_adresse.strip():
        pruefungen.append(("leitstelle", "Leitstelle", _leitstelle()))
    if settings.assistent_url:
        pruefungen.append(("assistent", "Assistent", _assistent()))
    if lexikon := nachschlagen.lexikon():
        pruefungen.append(("nachschlag", "Nachschlag", _nachschlag(lexikon)))
    return list(await asyncio.gather(*(_mit_frist(*p) for p in pruefungen)))


@router.get("/orte", dependencies=[Depends(braucht("einstellungen"))])
async def orte_stand(_=Depends(verify_token)):
    return await asyncio.to_thread(orte.stand)


@router.get("/config/oberflaeche")
async def oberflaeche(_=Depends(verify_konto)):
    a = anschluesse()
    return {"assistent": a.assistent, "anschluesse": a}


@router.get("/books/{buch}/ablage", dependencies=[Depends(braucht("bearbeiten"))])
async def ablage(buch: Nr, _=Depends(verify_token)):
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
