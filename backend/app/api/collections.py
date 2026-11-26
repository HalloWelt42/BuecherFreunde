"""API-Endpunkte für Sammlungen."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.api import vorhanden
from backend.app.core.auth import verify_token
from backend.app.core.database import db
from backend.app.models.book import GATTUNGEN, TYPEN
from backend.app.models.grenzen import Band, Farbe, Nr, Sammlungsbeschreibung, Sammlungsname

router = APIRouter(prefix="/api/collections", tags=["Sammlungen"])



FEHLT = "Sammlung nicht gefunden"


class CollectionCreate(BaseModel):
    name: Sammlungsname
    description: Sammlungsbeschreibung = ""
    color: Farbe = "#2563eb"


class CollectionUpdate(BaseModel):
    name: Sammlungsname | None = None
    description: Sammlungsbeschreibung | None = None
    color: Farbe | None = None


class BuchZuordnung(BaseModel):
    band_nummer: Band = ""


# --- Systemtypen ---

@router.get("/typen")
async def liste_typen(_: str = Depends(verify_token)):
    """Gibt die verfügbaren Systemtypen zurück."""
    return TYPEN


@router.get("/gattungen")
async def liste_gattungen(_: str = Depends(verify_token)):
    """Die festen Gattungen eines Buchs, in der Reihenfolge, in der sie angeboten werden (BF-59)."""
    return GATTUNGEN


# --- Sammlungen CRUD ---

@router.get("")
async def liste_sammlungen(_: str = Depends(verify_token)):
    """Alle Sammlungen mit Buchanzahl."""
    rows = await db.fetch_all("""
        SELECT c.*, COUNT(b.id) AS buch_anzahl
        FROM collections c
        LEFT JOIN books b ON b.sammlung_id = c.id
        GROUP BY c.id
        ORDER BY c.sort_order, c.name
    """)
    return [dict(r) for r in rows]


@router.post("")
async def erstelle_sammlung(
    data: CollectionCreate, _: str = Depends(verify_token)
):
    """Neue Sammlung erstellen."""
    cursor = await db.execute(
        """INSERT INTO collections (name, description, color)
        VALUES (?, ?, ?)""",
        (data.name, data.description, data.color),
    )
    await db.commit()
    return await db.fetch_one(
        "SELECT * FROM collections WHERE id = ?", (cursor.lastrowid,)
    )


@router.get("/{collection_id}")
async def hole_sammlung(
    collection_id: Nr, _: str = Depends(verify_token)
):
    """Einzelne Sammlung mit Büchern."""
    sammlung = await vorhanden.eintrag("collections", collection_id, FEHLT)
    buecher = await db.fetch_all("""
        SELECT id, title, author, isbn, file_format, cover_path, year, band_nummer
        FROM books
        WHERE sammlung_id = ?
        ORDER BY band_nummer, title
    """, (collection_id,))

    result = dict(sammlung)
    result["books"] = [dict(b) for b in buecher]
    return result


@router.patch("/{collection_id}")
async def aktualisiere_sammlung(
    collection_id: Nr,
    data: CollectionUpdate,
    _: str = Depends(verify_token),
):
    """Sammlung aktualisieren."""
    await vorhanden.eintrag("collections", collection_id, FEHLT, "id")
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Keine Änderungen")

    sets = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [collection_id]
    await db.execute(
        f"UPDATE collections SET {sets} WHERE id = ?", tuple(values)
    )
    await db.commit()
    return await db.fetch_one(
        "SELECT * FROM collections WHERE id = ?", (collection_id,)
    )


@router.delete("/{collection_id}")
async def loesche_sammlung(
    collection_id: Nr, _: str = Depends(verify_token)
):
    """Sammlung löschen. Setzt sammlung_id bei zugehörigen Büchern auf NULL."""
    await vorhanden.eintrag("collections", collection_id, FEHLT, "id")
    await db.execute(
        "UPDATE books SET sammlung_id = NULL, band_nummer = '' WHERE sammlung_id = ?",
        (collection_id,),
    )
    await db.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
    await db.commit()
    return {"message": "Sammlung gelöscht"}


# --- Buch-Zuordnung (1:1) ---

@router.post("/{collection_id}/buch/{book_id}")
async def buch_zuordnen(
    collection_id: Nr,
    book_id: Nr,
    data: BuchZuordnung = BuchZuordnung(),
    _: str = Depends(verify_token),
):
    """Buch einer Sammlung zuordnen (ersetzt vorherige Zuordnung)."""
    await vorhanden.eintrag("collections", collection_id, FEHLT, "id")
    await vorhanden.buch(book_id)

    await db.execute(
        "UPDATE books SET sammlung_id = ?, band_nummer = ? WHERE id = ?",
        (collection_id, data.band_nummer, book_id),
    )
    await db.commit()
    return {"message": "Buch zur Sammlung zugeordnet"}


@router.delete("/{collection_id}/buch/{book_id}")
async def buch_aus_sammlung(
    collection_id: Nr, book_id: Nr, _: str = Depends(verify_token)
):
    """Buch aus Sammlung entfernen."""
    c = await db.execute(
        "UPDATE books SET sammlung_id = NULL, band_nummer = '' WHERE id = ? AND sammlung_id = ?",
        (book_id, collection_id),
    )
    vorhanden.getroffen(c, "Das Buch gehört nicht zu dieser Sammlung")
    await db.commit()
    return {"message": "Buch aus Sammlung entfernt"}
