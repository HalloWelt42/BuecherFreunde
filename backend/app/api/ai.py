"""API-Endpunkte fuer KI-Kategorisierung."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.auth import verify_token
from backend.app.core.database import db
from backend.app.services.ai_categorization import categorize_book, check_connection
from backend.app.services.storage import load_fulltext

router = APIRouter(prefix="/api/ai", tags=["KI"])


class AcceptCategories(BaseModel):
    kategorien: list[str]


@router.post("/buch/{book_id}/kategorisieren")
async def categorize(book_id: int, _token: str = Depends(verify_token)):
    """Holt KI-Kategorie-Vorschlaege fuer ein Buch."""
    book = await db.fetch_one(
        "SELECT id, hash, title, author FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    # Textauszug laden
    fulltext = load_fulltext(book["hash"]) or ""

    vorschlaege = await categorize_book(
        title=book["title"],
        author=book["author"],
        text_excerpt=fulltext[:2000],
    )

    if not vorschlaege:
        raise HTTPException(
            status_code=503,
            detail="KI-Kategorisierung nicht verfuegbar. Ist LM Studio gestartet?",
        )

    return {"book_id": book_id, "vorschlaege": vorschlaege}


@router.post("/buch/{book_id}/kategorien-uebernehmen")
async def accept_categories(
    book_id: int, data: AcceptCategories, _token: str = Depends(verify_token)
):
    """Uebernimmt KI-Kategorie-Vorschlaege fuer ein Buch.

    Erstellt fehlende Kategorien automatisch und ordnet sie dem Buch zu.
    """
    book = await db.fetch_one("SELECT id FROM books WHERE id = ?", (book_id,))
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    import re

    created = []
    assigned = []

    for name in data.kategorien:
        name = name.strip()
        if not name:
            continue

        # Slug erzeugen
        slug = re.sub(r"[^\w\s-]", "", name.lower())
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")

        # Kategorie suchen oder erstellen
        cat = await db.fetch_one(
            "SELECT id FROM categories WHERE slug = ?", (slug,)
        )
        if not cat:
            cursor = await db.execute(
                "INSERT INTO categories (name, slug) VALUES (?, ?)", (name, slug)
            )
            cat_id = cursor.lastrowid
            created.append(name)
        else:
            cat_id = cat["id"]

        # Buch zuordnen
        await db.execute(
            "INSERT OR IGNORE INTO book_categories (book_id, category_id) VALUES (?, ?)",
            (book_id, cat_id),
        )
        assigned.append(name)

    await db.commit()

    return {
        "book_id": book_id,
        "zugeordnet": assigned,
        "neu_erstellt": created,
    }


@router.get("/status")
async def ai_status(_token: str = Depends(verify_token)):
    """Prueft ob LM Studio erreichbar ist und welche Modelle verfuegbar sind."""
    return await check_connection()
