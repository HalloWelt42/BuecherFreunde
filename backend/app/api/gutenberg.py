"""API-Endpunkte für Gutenberg-Import.

Ermöglicht Suche, Vorschau und Import gemeinfreier Bücher
von Project Gutenberg über die Gutendex-API.
"""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.core.auth import verify_token, verify_token_query
from backend.app.core.database import db
from backend.app.services.gutenberg import download_buch, download_cover, suche
from backend.app.services.import_service import (
    create_import_task,
    import_single_file,
    update_task_status,
)
from backend.app.services.storage import check_duplicate, compute_hash, save_cover

logger = logging.getLogger("buecherfreunde.api.gutenberg")

router = APIRouter(prefix="/api/gutenberg", tags=["Gutenberg"])

# Globaler Status für laufende Gutenberg-Imports
_gutenberg_status: dict = {
    "laeuft": False,
    "gesamt": 0,
    "fertig": 0,
    "fehler": 0,
    "duplikate": 0,
    "aktuell": "",
    "ergebnisse": [],
}


def _reset_status():
    _gutenberg_status.update({
        "laeuft": False,
        "gesamt": 0,
        "fertig": 0,
        "fehler": 0,
        "duplikate": 0,
        "aktuell": "",
        "ergebnisse": [],
    })


@router.get("/status")
async def gutenberg_status(_token: str = Depends(verify_token)) -> dict:
    """Prüft ob die Gutendex-API erreichbar ist."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            resp = await client.get("https://gutendex.com/books/?page=1&search=test")
            return {
                "erreichbar": resp.status_code == 200,
                "url": "https://gutendex.com",
                "info": f"HTTP {resp.status_code}",
            }
    except Exception as e:
        return {
            "erreichbar": False,
            "url": "https://gutendex.com",
            "info": str(e),
        }


@router.get("/suche")
async def gutenberg_suche(
    q: str = Query("", description="Suchbegriff (Titel, Autor)"),
    sprache: str = Query("", description="Sprachfilter (z.B. 'de', 'en', 'de,en')"),
    topic: str = Query("", description="Thema/Kategorie"),
    seite: int = Query(1, ge=1, description="Seitennummer"),
    _token: str = Depends(verify_token),
) -> dict:
    """Sucht Bücher auf Project Gutenberg."""
    try:
        ergebnis = await suche(query=q, sprache=sprache, topic=topic, seite=seite)
        return ergebnis
    except Exception as e:
        logger.error("Gutenberg-Suche fehlgeschlagen: %s", e)
        raise HTTPException(status_code=502, detail=f"Gutendex nicht erreichbar: {e}")


class GutenbergImportRequest(BaseModel):
    """Import-Anfrage für Gutenberg-Bücher."""
    buecher: list[dict]  # Liste von {gutenberg_id, titel, autor, download_url, download_format, cover_url}


@router.post("/import")
async def gutenberg_import(
    request: GutenbergImportRequest,
    background_tasks: BackgroundTasks,
    _token: str = Depends(verify_token),
):
    """Importiert ausgewählte Gutenberg-Bücher.

    Lädt jedes Buch herunter, prüft auf Duplikate und
    importiert es mit der Kategorie 'Gutenberg'.
    """
    if _gutenberg_status["laeuft"]:
        raise HTTPException(
            status_code=409,
            detail="Es läuft bereits ein Gutenberg-Import",
        )

    if not request.buecher:
        raise HTTPException(status_code=400, detail="Keine Bücher ausgewählt")

    _reset_status()
    _gutenberg_status["laeuft"] = True
    _gutenberg_status["gesamt"] = len(request.buecher)

    async def _run_import():
        try:
            await _import_buecher(request.buecher)
        finally:
            _gutenberg_status["laeuft"] = False

    background_tasks.add_task(_run_import)

    return {
        "gestartet": True,
        "anzahl": len(request.buecher),
    }


async def _get_or_create_gutenberg_kategorie() -> int:
    """Holt oder erstellt die Kategorie 'Gutenberg'."""
    row = await db.fetch_one(
        "SELECT id FROM categories WHERE slug = ?", ("gutenberg",)
    )
    if row:
        return row["id"]

    cur = await db.execute(
        """INSERT OR IGNORE INTO categories (name, slug, description, icon, color, spezial)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            "Gutenberg",
            "gutenberg",
            "Gemeinfreie Bücher von Project Gutenberg",
            "fa-landmark-dome",
            "#8b5cf6",
            1,
        ),
    )
    await db.commit()
    if cur.lastrowid:
        return cur.lastrowid
    row = await db.fetch_one(
        "SELECT id FROM categories WHERE slug = ?", ("gutenberg",)
    )
    return row["id"]


async def _import_buecher(buecher: list[dict]):
    """Importiert eine Liste von Gutenberg-Büchern sequentiell."""
    kat_id = await _get_or_create_gutenberg_kategorie()

    for i, buch in enumerate(buecher):
        gutenberg_id = buch.get("gutenberg_id", 0)
        titel = buch.get("titel", f"Gutenberg #{gutenberg_id}")
        _gutenberg_status["aktuell"] = titel

        ergebnis = {
            "gutenberg_id": gutenberg_id,
            "titel": titel,
            "status": "fehler",
            "detail": "",
        }

        try:
            # Prüfen ob bereits importiert (via gutenberg_id in Metadaten)
            existing = await db.fetch_one(
                "SELECT id FROM books WHERE gutenberg_id = ?", (gutenberg_id,)
            )
            if existing:
                ergebnis["status"] = "duplikat"
                ergebnis["detail"] = "Bereits importiert"
                ergebnis["book_id"] = existing["id"]
                _gutenberg_status["duplikate"] += 1
                _gutenberg_status["ergebnisse"].append(ergebnis)
                _gutenberg_status["fertig"] += 1
                continue

            # Buch herunterladen
            download_url = buch.get("download_url", "")
            if not download_url:
                ergebnis["detail"] = "Keine Download-URL"
                _gutenberg_status["fehler"] += 1
                _gutenberg_status["ergebnisse"].append(ergebnis)
                _gutenberg_status["fertig"] += 1
                continue

            temp_path = await download_buch(gutenberg_id, download_url)
            if not temp_path:
                ergebnis["detail"] = "Download fehlgeschlagen"
                _gutenberg_status["fehler"] += 1
                _gutenberg_status["ergebnisse"].append(ergebnis)
                _gutenberg_status["fertig"] += 1
                continue

            try:
                # Hash prüfen
                file_hash = compute_hash(temp_path)
                dup = check_duplicate(file_hash)
                existing_hash = await db.fetch_one(
                    "SELECT id, title FROM books WHERE hash = ?", (file_hash,)
                )
                if dup or existing_hash:
                    ergebnis["status"] = "duplikat"
                    ergebnis["detail"] = f"Datei-Duplikat (Hash)"
                    if existing_hash:
                        ergebnis["book_id"] = existing_hash["id"]
                    _gutenberg_status["duplikate"] += 1
                    _gutenberg_status["ergebnisse"].append(ergebnis)
                    _gutenberg_status["fertig"] += 1
                    continue

                # Import-Task erstellen
                task_id = await create_import_task(
                    f"[Gutenberg] {titel}",
                    str(temp_path),
                )

                # Importieren
                result = await import_single_file(temp_path, task_id)

                if result["status"] == "ok":
                    book_id = result["book_id"]

                    # Gutenberg-ID speichern
                    await db.execute(
                        "UPDATE books SET gutenberg_id = ? WHERE id = ?",
                        (gutenberg_id, book_id),
                    )

                    # Kategorie zuweisen
                    await db.execute(
                        "INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'import')",
                        (book_id, kat_id),
                    )

                    # Cover herunterladen wenn vorhanden
                    cover_url = buch.get("cover_url", "")
                    if cover_url:
                        cover_data = await download_cover(cover_url)
                        if cover_data:
                            book_row = await db.fetch_one(
                                "SELECT hash FROM books WHERE id = ?", (book_id,)
                            )
                            if book_row:
                                save_cover(book_row["hash"], cover_data)
                                await db.execute(
                                    "UPDATE books SET cover_path = 'cover.jpg' WHERE id = ?",
                                    (book_id,),
                                )

                    await db.commit()

                    ergebnis["status"] = "ok"
                    ergebnis["book_id"] = book_id
                    ergebnis["detail"] = "Importiert"

                elif result["status"] == "duplikat":
                    ergebnis["status"] = "duplikat"
                    ergebnis["detail"] = "Duplikat"
                    _gutenberg_status["duplikate"] += 1
                else:
                    ergebnis["detail"] = result.get("fehler", "Unbekannter Fehler")
                    _gutenberg_status["fehler"] += 1

            finally:
                # Temp-Datei aufräumen
                temp_path.unlink(missing_ok=True)

        except Exception as e:
            logger.error("Gutenberg-Import fehlgeschlagen für #%d: %s", gutenberg_id, e)
            ergebnis["detail"] = str(e)
            _gutenberg_status["fehler"] += 1

        _gutenberg_status["ergebnisse"].append(ergebnis)
        _gutenberg_status["fertig"] += 1

        # Kurze Pause zwischen Downloads (Rate-Limiting)
        await asyncio.sleep(0.5)


@router.get("/import/status")
async def gutenberg_import_status(_token: str = Depends(verify_token)) -> dict:
    """Gibt den aktuellen Status des Gutenberg-Imports zurück."""
    return dict(_gutenberg_status)


@router.get("/import/events")
async def gutenberg_import_events(_token: str = Depends(verify_token_query)):
    """SSE-Endpunkt für Echtzeit-Fortschritt des Gutenberg-Imports."""

    async def event_generator():
        last_data = None
        while True:
            data = json.dumps(
                {
                    "laeuft": _gutenberg_status["laeuft"],
                    "gesamt": _gutenberg_status["gesamt"],
                    "fertig": _gutenberg_status["fertig"],
                    "fehler": _gutenberg_status["fehler"],
                    "duplikate": _gutenberg_status["duplikate"],
                    "aktuell": _gutenberg_status["aktuell"],
                    "ergebnisse": _gutenberg_status["ergebnisse"][-20:],
                },
                ensure_ascii=False,
                default=str,
            )

            if data != last_data:
                yield f"data: {data}\n\n"
                last_data = data

            if not _gutenberg_status["laeuft"] and _gutenberg_status["gesamt"] > 0:
                # Letztes Event senden
                yield f"data: {data}\n\n"
                break

            if not _gutenberg_status["laeuft"] and _gutenberg_status["gesamt"] == 0:
                # Noch nicht gestartet - warten
                pass

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/import/reset")
async def gutenberg_reset(_token: str = Depends(verify_token)):
    """Setzt den Gutenberg-Import-Status zurück."""
    if _gutenberg_status["laeuft"]:
        raise HTTPException(status_code=409, detail="Import läuft noch")
    _reset_status()
    return {"zurueckgesetzt": True}
