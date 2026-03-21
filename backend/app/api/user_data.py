"""API-Endpunkte für Nutzerdaten (Favoriten, Lesestand, Bewertung)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.auth import verify_token
from backend.app.core.database import db

router = APIRouter(prefix="/api/books", tags=["Nutzerdaten"])


class RatingUpdate(BaseModel):
    bewertung: int = Field(ge=0, le=5)


class ReadingPositionUpdate(BaseModel):
    position: str


async def _ensure_user_data(book_id: int) -> None:
    """Stellt sicher, dass ein Eintrag in user_book_data existiert."""
    existing = await db.fetch_one(
        "SELECT book_id FROM user_book_data WHERE book_id = ?", (book_id,)
    )
    if not existing:
        await db.execute(
            "INSERT INTO user_book_data (book_id) VALUES (?)", (book_id,)
        )


async def _check_book_exists(book_id: int) -> None:
    """Prüft ob das Buch existiert."""
    book = await db.fetch_one("SELECT id FROM books WHERE id = ?", (book_id,))
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")


@router.patch("/{book_id}/favorit")
async def toggle_favorite(book_id: int, _token: str = Depends(verify_token)):
    """Wechselt den Favoriten-Status eines Buches."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id)

    current = await db.fetch_one(
        "SELECT is_favorite FROM user_book_data WHERE book_id = ?", (book_id,)
    )
    new_value = 0 if current and current["is_favorite"] else 1

    await db.execute(
        "UPDATE user_book_data SET is_favorite = ? WHERE book_id = ?",
        (new_value, book_id),
    )
    await db.commit()

    return {"book_id": book_id, "ist_favorit": bool(new_value)}


@router.patch("/{book_id}/zu-lesen")
async def toggle_to_read(book_id: int, _token: str = Depends(verify_token)):
    """Wechselt den Zum-Lesen-Status eines Buches."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id)

    current = await db.fetch_one(
        "SELECT is_to_read FROM user_book_data WHERE book_id = ?", (book_id,)
    )
    new_value = 0 if current and current["is_to_read"] else 1

    await db.execute(
        "UPDATE user_book_data SET is_to_read = ? WHERE book_id = ?",
        (new_value, book_id),
    )
    await db.commit()

    return {"book_id": book_id, "zu_lesen": bool(new_value)}


@router.patch("/{book_id}/bewertung")
async def set_rating(
    book_id: int, data: RatingUpdate, _token: str = Depends(verify_token)
):
    """Setzt die Bewertung eines Buches (0-5 Sterne)."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id)

    await db.execute(
        "UPDATE user_book_data SET rating = ? WHERE book_id = ?",
        (data.bewertung, book_id),
    )
    await db.commit()

    return {"book_id": book_id, "bewertung": data.bewertung}


@router.patch("/{book_id}/leseposition")
async def set_reading_position(
    book_id: int, data: ReadingPositionUpdate, _token: str = Depends(verify_token)
):
    """Speichert die Leseposition (Seitenzahl, CFI oder Prozent)."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id)

    await db.execute(
        "UPDATE user_book_data SET reading_position = ?, last_read_at = datetime('now') WHERE book_id = ?",
        (data.position, book_id),
    )
    await db.commit()

    return {"book_id": book_id, "position": data.position}
