"""API-Endpunkte für Sammlungen."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.auth import verify_token
from backend.app.core.database import db

router = APIRouter(prefix="/api/collections", tags=["Sammlungen"])

# Feste Systemtypen (nicht löschbar, nicht editierbar)
SYSTEM_TYPEN = [
    {"id": "heft", "name": "Heft", "beschreibung": "Zeitschrift, Magazin oder Heft"},
    {"id": "katalog", "name": "Katalog", "beschreibung": "Produktkatalog oder Verzeichnis"},
    {"id": "broschuere", "name": "Broschüre", "beschreibung": "Informationsbroschüre oder Flyer"},
]


class CollectionCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#2563eb"


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


class BuchZuordnung(BaseModel):
    band_nummer: str = ""


# --- Systemtypen ---

@router.get("/typen")
async def liste_typen(_: str = Depends(verify_token)):
    """Gibt die verfügbaren Systemtypen zurück."""
    return SYSTEM_TYPEN


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
    collection_id: int, _: str = Depends(verify_token)
):
    """Einzelne Sammlung mit Büchern."""
    sammlung = await db.fetch_one(
        "SELECT * FROM collections WHERE id = ?", (collection_id,)
    )
    if not sammlung:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")

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
    collection_id: int,
    data: CollectionUpdate,
    _: str = Depends(verify_token),
):
    """Sammlung aktualisieren."""
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
    collection_id: int, _: str = Depends(verify_token)
):
    """Sammlung löschen. Setzt sammlung_id bei zugehörigen Büchern auf NULL."""
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
    collection_id: int,
    book_id: int,
    data: BuchZuordnung = BuchZuordnung(),
    _: str = Depends(verify_token),
):
    """Buch einer Sammlung zuordnen (ersetzt vorherige Zuordnung)."""
    sammlung = await db.fetch_one(
        "SELECT id FROM collections WHERE id = ?", (collection_id,)
    )
    if not sammlung:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")

    buch = await db.fetch_one("SELECT id FROM books WHERE id = ?", (book_id,))
    if not buch:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    await db.execute(
        "UPDATE books SET sammlung_id = ?, band_nummer = ? WHERE id = ?",
        (collection_id, data.band_nummer, book_id),
    )
    await db.commit()
    return {"message": "Buch zur Sammlung zugeordnet"}


@router.delete("/{collection_id}/buch/{book_id}")
async def buch_aus_sammlung(
    collection_id: int, book_id: int, _: str = Depends(verify_token)
):
    """Buch aus Sammlung entfernen."""
    await db.execute(
        "UPDATE books SET sammlung_id = NULL, band_nummer = '' WHERE id = ? AND sammlung_id = ?",
        (book_id, collection_id),
    )
    await db.commit()
    return {"message": "Buch aus Sammlung entfernt"}
