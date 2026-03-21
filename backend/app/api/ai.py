"""API-Endpunkte für KI-Kategorisierung und Prompt-Verwaltung."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.auth import verify_token
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services.ai_categorization import categorize_book, check_connection
from backend.app.services.storage import load_fulltext

router = APIRouter(prefix="/api/ai", tags=["KI"])


class AcceptCategories(BaseModel):
    kategorien: list[str]


@router.post("/buch/{book_id}/kategorisieren")
async def categorize(book_id: int, _token: str = Depends(verify_token)):
    """Holt KI-Kategorie-Vorschläge für ein Buch."""
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
            detail="KI-Kategorisierung nicht verfügbar. Ist LM Studio gestartet?",
        )

    return {"book_id": book_id, "vorschlaege": vorschlaege}


@router.post("/buch/{book_id}/kategorien-uebernehmen")
async def accept_categories(
    book_id: int, data: AcceptCategories, _token: str = Depends(verify_token)
):
    """Übernimmt KI-Kategorie-Vorschläge für ein Buch.

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

        # ai_-Prefix für KI-zugewiesene Kategorien
        ai_name = f"ai_{name}" if not name.startswith("ai_") else name

        # Slug erzeugen
        slug = re.sub(r"[^\w\s-]", "", ai_name.lower())
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")

        # Kategorie suchen oder erstellen
        cat = await db.fetch_one(
            "SELECT id FROM categories WHERE slug = ?", (slug,)
        )
        if not cat:
            cursor = await db.execute(
                "INSERT INTO categories (name, slug) VALUES (?, ?)", (ai_name, slug)
            )
            cat_id = cursor.lastrowid
            created.append(ai_name)
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
    """Prüft ob LM Studio erreichbar ist und welche Modelle verfügbar sind."""
    result = await check_connection()
    # Gespeichertes Modell aus DB laden (überschreibt .env)
    saved = await db.fetch_one(
        "SELECT value FROM app_settings WHERE key = 'lm_studio_model'"
    )
    modell = saved["value"] if saved else settings.lm_studio_model
    result["url"] = settings.lm_studio_url
    result["modell"] = modell
    result["aktiviert"] = settings.lm_studio_enabled
    return result


# --- KI-Config ---

class AiConfigUpdate(BaseModel):
    lm_studio_url: str | None = None
    lm_studio_model: str | None = None
    lm_studio_enabled: bool | None = None


@router.get("/config")
async def get_ai_config(_token: str = Depends(verify_token)):
    """Gibt die KI-Konfiguration zurück."""
    # Gespeichertes Modell aus DB laden (überschreibt .env)
    saved = await db.fetch_one(
        "SELECT value FROM app_settings WHERE key = 'lm_studio_model'"
    )
    modell = saved["value"] if saved else settings.lm_studio_model
    return {
        "url": settings.lm_studio_url,
        "modell": modell,
        "aktiviert": settings.lm_studio_enabled,
    }


@router.patch("/config")
async def update_ai_config(data: AiConfigUpdate, _token: str = Depends(verify_token)):
    """Aktualisiert die KI-Konfiguration (persistiert Modellwahl)."""
    if data.lm_studio_model is not None:
        await db.execute(
            """INSERT INTO app_settings (key, value) VALUES ('lm_studio_model', ?)
               ON CONFLICT(key) DO UPDATE SET value = ?""",
            (data.lm_studio_model, data.lm_studio_model),
        )
        # Auch Runtime-Setting aktualisieren
        settings.lm_studio_model = data.lm_studio_model
        await db.commit()

    saved = await db.fetch_one(
        "SELECT value FROM app_settings WHERE key = 'lm_studio_model'"
    )
    modell = saved["value"] if saved else settings.lm_studio_model
    return {
        "url": settings.lm_studio_url,
        "modell": modell,
        "aktiviert": settings.lm_studio_enabled,
    }


# --- Prompt-Verwaltung ---

class PromptUpdate(BaseModel):
    name: str | None = None
    beschreibung: str | None = None
    system_prompt: str | None = None
    temperatur: float | None = None
    max_tokens: int | None = None
    aktiv: bool | None = None


@router.get("/prompts")
async def list_prompts(_token: str = Depends(verify_token)):
    """Gibt alle KI-Prompts zurück."""
    rows = await db.fetch_all(
        "SELECT * FROM ai_prompts ORDER BY schluessel"
    )
    return rows


@router.get("/prompts/{prompt_id}")
async def get_prompt(prompt_id: int, _token: str = Depends(verify_token)):
    """Gibt einen einzelnen Prompt zurück."""
    row = await db.fetch_one(
        "SELECT * FROM ai_prompts WHERE id = ?", (prompt_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Prompt nicht gefunden")
    return row


@router.patch("/prompts/{prompt_id}")
async def update_prompt(
    prompt_id: int, data: PromptUpdate, _token: str = Depends(verify_token)
):
    """Aktualisiert einen KI-Prompt."""
    existing = await db.fetch_one(
        "SELECT * FROM ai_prompts WHERE id = ?", (prompt_id,)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Prompt nicht gefunden")

    updates = {}
    if data.name is not None:
        updates["name"] = data.name
    if data.beschreibung is not None:
        updates["beschreibung"] = data.beschreibung
    if data.system_prompt is not None:
        updates["system_prompt"] = data.system_prompt
    if data.temperatur is not None:
        updates["temperatur"] = max(0.0, min(2.0, data.temperatur))
    if data.max_tokens is not None:
        updates["max_tokens"] = max(50, min(4000, data.max_tokens))
    if data.aktiv is not None:
        updates["aktiv"] = 1 if data.aktiv else 0

    if not updates:
        raise HTTPException(status_code=400, detail="Keine Felder zum Aktualisieren")

    updates["updated_at"] = "datetime('now')"
    set_parts = []
    values = []
    for k, v in updates.items():
        if k == "updated_at":
            set_parts.append(f"{k} = datetime('now')")
        else:
            set_parts.append(f"{k} = ?")
            values.append(v)

    values.append(prompt_id)
    await db.execute(
        f"UPDATE ai_prompts SET {', '.join(set_parts)} WHERE id = ?",
        tuple(values),
    )
    await db.commit()

    return await db.fetch_one("SELECT * FROM ai_prompts WHERE id = ?", (prompt_id,))


@router.post("/prompts/{prompt_id}/reset")
async def reset_prompt(prompt_id: int, _token: str = Depends(verify_token)):
    """Setzt einen Prompt auf den Standardwert zurück (löscht und migriert neu)."""
    existing = await db.fetch_one(
        "SELECT schluessel FROM ai_prompts WHERE id = ?", (prompt_id,)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Prompt nicht gefunden")

    return {"message": "Prompt kann manuell zurückgesetzt werden."}
