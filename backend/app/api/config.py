"""API-Endpunkte für Konfiguration und Systemstatus."""

from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse

from backend.app.core.auth import verify_token, verify_token_query
from backend.app.core.config import settings
from backend.app.core.database import db

router = APIRouter(prefix="/api/config", tags=["Konfiguration"])


@router.get("")
async def get_config(_token: str = Depends(verify_token)) -> dict:
    """Gibt die öffentliche Konfiguration zurück (ohne sensible Daten)."""
    return settings.public_config()


@router.get("/version")
async def get_version() -> dict:
    """Gibt die aktuelle Version zurück (ohne Authentifizierung)."""
    return {"version": settings.version}


@router.get("/paths")
async def get_paths(_token: str = Depends(verify_token)) -> dict:
    """Gibt die konfigurierten Verzeichnispfade zurück."""
    return {
        "datenbank": str(settings.database_path.resolve()),
        "speicher": str(settings.storage_dir.resolve()),
        "import": str(settings.import_dir.resolve()),
        "extern": str(settings.external_dir.resolve()) if settings.external_dir else "",
    }


@router.get("/stats")
async def get_stats(_token: str = Depends(verify_token)) -> dict:
    """Gibt Zähler für Sidebar und Dashboard zurück."""
    total = await db.fetch_one("SELECT COUNT(*) as n FROM books")
    favs = await db.fetch_one(
        "SELECT COUNT(*) as n FROM user_book_data WHERE is_favorite = 1"
    )
    to_read = await db.fetch_one(
        "SELECT COUNT(*) as n FROM user_book_data WHERE is_to_read = 1"
    )
    gelesen = await db.fetch_one(
        "SELECT COUNT(*) as n FROM user_book_data WHERE last_read_at IS NOT NULL"
    )
    mit_isbn = await db.fetch_one(
        "SELECT COUNT(*) as n FROM books WHERE isbn IS NOT NULL AND isbn != ''"
    )
    ohne_isbn = await db.fetch_one(
        "SELECT COUNT(*) as n FROM books WHERE isbn IS NULL OR isbn = ''"
    )
    weiterlesen = await db.fetch_one(
        """SELECT COUNT(*) as n FROM user_book_data
           WHERE reading_position IS NOT NULL AND reading_position != ''
           AND last_read_at IS NOT NULL"""
    )
    autoren = await db.fetch_one("SELECT COUNT(*) as n FROM authors")
    mit_labels = await db.fetch_one(
        "SELECT COUNT(DISTINCT book_id) as n FROM book_labels"
    )
    mit_highlights = await db.fetch_one(
        "SELECT COUNT(DISTINCT book_id) as n FROM book_highlights"
    )
    total_n = total["n"] if total else 0
    gelesen_n = gelesen["n"] if gelesen else 0
    return {
        "buecher_gesamt": total_n,
        "favoriten": favs["n"] if favs else 0,
        "leseliste": to_read["n"] if to_read else 0,
        "gelesen": gelesen_n,
        "ungelesen": total_n - gelesen_n,
        "buecher_mit_isbn": mit_isbn["n"] if mit_isbn else 0,
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
async def list_bg_images(_token: str = Depends(verify_token)) -> dict:
    """Listet alle Hintergrundbilder auf."""
    bilder = _bg_liste()
    return {"bilder": bilder, "anzahl": len(bilder)}


@router.post("/design/hintergrund")
async def upload_bg_image(
    datei: UploadFile = File(...),
    _token: str = Depends(verify_token),
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
async def delete_bg_image(dateiname: str, _token: str = Depends(verify_token)):
    """Loescht ein Hintergrundbild."""
    from fastapi import HTTPException

    pfad = _bg_dir() / dateiname
    if not pfad.exists() or not pfad.parent.samefile(_bg_dir()):
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    pfad.unlink()
    return {"geloescht": True}


@router.delete("/design/hintergrund")
async def delete_all_bg_images(_token: str = Depends(verify_token)):
    """Loescht alle Hintergrundbilder."""
    d = _bg_dir()
    for p in d.iterdir():
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            p.unlink()
    return {"geloescht": True}


@router.get("/design/hintergrund/status")
async def bg_image_status(_token: str = Depends(verify_token)):
    """Prueft ob Hintergrundbilder vorhanden sind."""
    bilder = _bg_liste()
    return {
        "vorhanden": len(bilder) > 0,
        "anzahl": len(bilder),
        "bilder": bilder,
    }


@router.get("/design/hintergrund/{dateiname}")
async def get_bg_image_by_name(dateiname: str, token: str = Depends(verify_token_query)):
    """Liefert ein Hintergrundbild nach Dateiname."""
    from fastapi import HTTPException

    pfad = _bg_dir() / dateiname
    if not pfad.exists() or not pfad.parent.samefile(_bg_dir()):
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    suffix = pfad.suffix.lower()
    media = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    return FileResponse(pfad, media_type=media.get(suffix.lstrip("."), "image/jpeg"))


@router.get("/design/hintergrund")
async def get_bg_image(token: str = Depends(verify_token_query)):
    """Liefert das erste Hintergrundbild (Fallback)."""
    from fastapi import HTTPException

    bilder = _bg_liste()
    if not bilder:
        raise HTTPException(status_code=404, detail="Kein Hintergrundbild vorhanden")
    pfad = _bg_dir() / bilder[0]["dateiname"]
    return FileResponse(pfad, media_type="image/jpeg")
