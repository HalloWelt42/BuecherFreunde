"""API-Endpunkte für Konfiguration und Systemstatus."""

import asyncio
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse

from backend.app.core.auth import braucht, profil, verify_konto, verify_konto_inhalt
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.drittanbieter.pakete import Paket, pakete
from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht
from backend.app.services import buchliste, schnellfilter

logger = logging.getLogger("buecherfreunde")

GITHUB_VERSION_URL = (
    "https://raw.githubusercontent.com/HalloWelt42/BuecherFreunde/main/VERSION"
)

router = APIRouter(prefix="/api/config", tags=["Konfiguration"])
EINSTELLUNGEN = braucht("einstellungen")


@router.get("")
async def get_config(_konto=Depends(verify_konto)) -> dict:
    """Gibt die öffentliche Konfiguration zurück (ohne sensible Daten); nichts Persönliches, darum auch vor der Profilwahl."""
    return settings.public_config()


@router.get("/version")
async def get_version() -> dict:
    """Gibt die aktuelle Version zurück (ohne Authentifizierung)."""
    return {"version": settings.version}


@router.get("/drittanbieter")
async def get_drittanbieter(_konto=Depends(verify_konto)) -> list[Paket]:
    """Die installierten Pakete des Servers für die Seite Drittanbieter (BF-90); nichts Persönliches, darum ohne Profil."""
    return await asyncio.to_thread(pakete)


@router.get("/paths")
async def get_paths(_p: Profil = Depends(EINSTELLUNGEN)) -> dict:
    """Gibt die konfigurierten Verzeichnispfade zurück.

    Zeigt Host-Pfade wenn verfügbar (Docker), sonst die lokalen Pfade.
    """
    return {
        "datenbank": settings.host_database_dir or str(settings.database_path.resolve()),
        "speicher": settings.host_storage_dir or str(settings.storage_dir.resolve()),
        "import": settings.host_import_dir or str(settings.import_dir.resolve()),
        "extern": settings.host_external_dir or (str(settings.external_dir.resolve()) if settings.external_dir else ""),
    }


@router.get("/update-check")
async def check_for_updates(_p: Profil = Depends(EINSTELLUNGEN)) -> dict:
    """Prüft ob eine neuere Version auf GitHub verfügbar ist."""
    lokale_version = settings.version
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(GITHUB_VERSION_URL)
            resp.raise_for_status()
            remote_version = resp.text.strip()
        update_verfuegbar = remote_version != lokale_version
        return {
            "lokale_version": lokale_version,
            "remote_version": remote_version,
            "update_verfuegbar": update_verfuegbar,
        }
    except Exception as e:
        logger.debug("Update-Check fehlgeschlagen: %s", e)
        return {
            "lokale_version": lokale_version,
            "remote_version": None,
            "update_verfuegbar": False,
            "fehler": "GitHub nicht erreichbar",
        }


@router.get("/stats")
async def get_stats(p: Profil = Depends(profil)) -> dict:
    """Gibt Zähler für Sidebar und Dashboard zurück: nur Bücher, die das Profil sieht, mit seinen Nutzerdaten (BF-78)."""
    sicht, sw = Sicht.von(p).bedingung("b.id")

    async def buecher(bedingung: str = "1", werte: tuple = ()) -> dict | None:
        return await db.fetch_one(f"SELECT COUNT(*) as n FROM books b WHERE {sicht} AND {bedingung}", (*sw, *werte))

    async def eigene(bedingung: str) -> dict | None:
        return await buecher(f"b.id IN (SELECT book_id FROM user_book_data WHERE profil_id = ? AND {bedingung})", (p.id,))

    total = await buecher()
    favs = await eigene("is_favorite = 1")
    to_read = await eigene("is_to_read = 1")
    gelesen = await eigene("fertig_am IS NOT NULL")                      # fertig gelesen (familie/lesestand.py)
    mit_isbn = await buecher("b.isbn IS NOT NULL AND b.isbn != ''")
    ohne_isbn = await buecher("(b.isbn IS NULL OR b.isbn = '')")
    weiterlesen = await eigene("reading_position IS NOT NULL AND reading_position != '' AND last_read_at IS NOT NULL")
    autoren = await db.fetch_one(f"""SELECT COUNT(*) as n FROM authors a WHERE EXISTS (SELECT 1 FROM book_authors x JOIN books b ON b.id = x.book_id
                                     WHERE x.author_id = a.id AND {sicht}){'' if p.kind else ' OR NOT EXISTS (SELECT 1 FROM book_authors y WHERE y.author_id = a.id)'}""", sw)
    mit_labels = await buecher(f"b.id IN ({schnellfilter.MIT_ETIKETTEN})", (p.id, p.id))
    mit_highlights = await buecher("b.id IN (SELECT book_id FROM book_highlights WHERE profil_id = ?)", (p.id,))
    je_art = {art: await buecher(bedingung, werte)
              for art, (bedingung, werte) in (("buch", buchliste.nach_art("buch")), ("besonderes", buchliste.nach_art("besonderes")))}
    total_n = total["n"] if total else 0
    gelesen_n = gelesen["n"] if gelesen else 0
    return {
        "buecher_gesamt": total_n,
        "favoriten": favs["n"] if favs else 0,
        "leseliste": to_read["n"] if to_read else 0,
        "gelesen": gelesen_n,
        "ungelesen": total_n - gelesen_n,
        "buecher": je_art["buch"]["n"],                  # Art Buch (BF-77)
        "besonderes": je_art["besonderes"]["n"],         # alles, was kein Buch ist
        "buecher_mit_isbn": mit_isbn["n"] if mit_isbn else 0,        # bis die Oberfläche nur noch nach Art zählt
        "dokumente": ohne_isbn["n"] if ohne_isbn else 0,
        "weiterlesen": weiterlesen["n"] if weiterlesen else 0,
        "autoren": autoren["n"] if autoren else 0,
        "mit_labels": mit_labels["n"] if mit_labels else 0,
        "mit_highlights": mit_highlights["n"] if mit_highlights else 0,
    }


def _bg_dir() -> Path:
    """Verzeichnis fuer Hintergrundbilder."""
    d = settings.database_path.parent / "design_bg"
    d.mkdir(exist_ok=True)
    return d


def _bg_image_path() -> Path:
    """Pfad zum ersten Hintergrundbild (Abwaertskompatibilitaet)."""
    return settings.database_path.parent / "design_bg.jpg"


def _bg_liste() -> list[dict]:
    """Gibt alle Hintergrundbilder zurueck, sortiert nach Dateiname."""
    bilder = []
    # Altes einzelnes Bild migrieren
    alt = _bg_image_path()
    d = _bg_dir()
    if alt.exists():
        ziel = d / "bg_001.jpg"
        if not ziel.exists():
            alt.rename(ziel)
        else:
            alt.unlink()
    for p in sorted(d.iterdir()):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            bilder.append({
                "dateiname": p.name,
                "groesse": p.stat().st_size,
            })
    return bilder


@router.get("/design/hintergruende")
async def list_bg_images(_konto=Depends(verify_konto)) -> dict:
    """Listet alle Hintergrundbilder auf."""
    bilder = _bg_liste()
    return {"bilder": bilder, "anzahl": len(bilder)}


@router.post("/design/hintergrund")
async def upload_bg_image(
    datei: UploadFile = File(...),
    _p: Profil = Depends(EINSTELLUNGEN),
):
    """Laedt ein Hintergrundbild hoch."""
    from fastapi import HTTPException

    data = await datei.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Datei zu gross (max. 10 MB)")

    d = _bg_dir()
    # Naechste freie Nummer finden
    bestehend = sorted(d.iterdir())
    nr = 1
    for p in bestehend:
        if p.stem.startswith("bg_"):
            try:
                n = int(p.stem.split("_")[1])
                nr = max(nr, n + 1)
            except (IndexError, ValueError):
                pass

    # Endung aus Upload uebernehmen
    suffix = Path(datei.filename).suffix.lower() if datei.filename else ".jpg"
    if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
        suffix = ".jpg"
    pfad = d / f"bg_{nr:03d}{suffix}"
    pfad.write_bytes(data)

    return {"gespeichert": True, "dateiname": pfad.name, "groesse": len(data)}


@router.delete("/design/hintergrund/{dateiname}")
async def delete_bg_image(dateiname: str, _p: Profil = Depends(EINSTELLUNGEN)):
    """Loescht ein Hintergrundbild."""
    from fastapi import HTTPException

    pfad = _bg_dir() / dateiname
    if not pfad.exists() or not pfad.parent.samefile(_bg_dir()):
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    pfad.unlink()
    return {"geloescht": True}


@router.delete("/design/hintergrund")
async def delete_all_bg_images(_p: Profil = Depends(EINSTELLUNGEN)):
    """Loescht alle Hintergrundbilder."""
    d = _bg_dir()
    for p in d.iterdir():
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            p.unlink()
    return {"geloescht": True}


@router.get("/design/hintergrund/status")
async def bg_image_status(_konto=Depends(verify_konto)):
    """Prueft ob Hintergrundbilder vorhanden sind."""
    bilder = _bg_liste()
    return {
        "vorhanden": len(bilder) > 0,
        "anzahl": len(bilder),
        "bilder": bilder,
    }


@router.get("/design/hintergrund/{dateiname}")
async def get_bg_image_by_name(dateiname: str, _konto=Depends(verify_konto_inhalt)):
    """Liefert ein Hintergrundbild nach Dateiname."""
    from fastapi import HTTPException

    pfad = _bg_dir() / dateiname
    if not pfad.exists() or not pfad.parent.samefile(_bg_dir()):
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    suffix = pfad.suffix.lower()
    media = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    return FileResponse(pfad, media_type=media.get(suffix.lstrip("."), "image/jpeg"))


@router.get("/design/hintergrund")
async def get_bg_image(_konto=Depends(verify_konto_inhalt)):
    """Liefert das erste Hintergrundbild (Fallback)."""
    from fastapi import HTTPException

    bilder = _bg_liste()
    if not bilder:
        raise HTTPException(status_code=404, detail="Kein Hintergrundbild vorhanden")
    pfad = _bg_dir() / bilder[0]["dateiname"]
    return FileResponse(pfad, media_type="image/jpeg")
