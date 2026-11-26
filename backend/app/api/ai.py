"""Schnittstelle der KI-Einordnung (BF-10): Vorschläge, Übernahme, Stand und Modellwahl über die Leitstelle, Anweisungen."""

from appkern.leitstelle import LeitstellenFehler
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.auth import verify_token
from backend.app.core.database import db
from backend.app.services.ai_categorization import categorize_book
from backend.app.services.ki import KiFehler, ki
from backend.app.services.storage import load_fulltext
from backend.app.models.grenzen import Nr, Prompt, Promptbeschreibung, Promptname, Regalname

router = APIRouter(prefix="/api/ai", tags=["KI"])


class AcceptCategories(BaseModel):
    kategorien: list[Regalname] = Field(max_length=50)


@router.post("/buch/{book_id}/kategorisieren")
async def categorize(book_id: Nr, _token: str = Depends(verify_token)):
    """Holt KI-Kategorie-Vorschläge für ein Buch."""
    book = await db.fetch_one(
        "SELECT id, hash, title, author FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    # Textauszug laden
    fulltext = load_fulltext(book["hash"]) or ""

    try:
        vorschlaege = await categorize_book(title=book["title"], author=book["author"], text_excerpt=fulltext[:2000])
    except KiFehler as f:
        raise HTTPException(status_code=503, detail=f.grund) from f
    if not vorschlaege:
        raise HTTPException(status_code=503, detail="Die KI hat keine passenden Kategorien vorgeschlagen")

    return {"book_id": book_id, "vorschlaege": vorschlaege}


@router.post("/buch/{book_id}/kategorien-uebernehmen")
async def accept_categories(
    book_id: Nr, data: AcceptCategories, _token: str = Depends(verify_token)
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

        # Buch zuordnen mit Quelle 'ki'
        await db.execute(
            "INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'ki')",
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
    """Ob die KI über die Leitstelle antwortet und welche Modelle sie anbietet (lädt nie ein Modell)."""
    stand = await ki.stand()
    return {"erreichbar": stand.nutzbar, "grund": stand.grund, "modelle": stand.modelle, "url": ki.adresse, "modell": stand.modell,
            "gewaehlt": stand.gewaehlt, "aktiviert": stand.bereit}


# --- KI-Config ---

class AiConfigUpdate(BaseModel):
    """Feldnamen der Oberfläche (frontend/src/lib/api/ai.ts). Die Adresse steht in der Einrichtung, nicht hier."""
    lm_studio_model: str | None = Field(None, min_length=1, max_length=200)
    lm_studio_url: str | None = None


async def _ki_config() -> dict:
    """`modell`: das Modell, das gilt (die Wahl, wenn die Leitstelle sie anbietet, sonst die Vorgabe)."""
    modell = ki.modell()
    if ki.bereit:
        try:
            modell, _ = await ki.gilt()
        except LeitstellenFehler:
            pass
    return {"url": ki.adresse, "modell": modell, "aktiviert": ki.bereit}


@router.get("/config")
async def get_ai_config(_token: str = Depends(verify_token)):
    """Adresse der Leitstelle, gewähltes Modell und ob die KI eingerichtet ist."""
    return await _ki_config()


@router.patch("/config")
async def update_ai_config(data: AiConfigUpdate, _token: str = Depends(verify_token)):
    """Das Modell wählen (bleibt über einen Neustart); die Leitstelle wählt nie eins."""
    if data.lm_studio_url is not None:
        raise HTTPException(status_code=422, detail="Die Adresse der KI steht in der Einrichtung (LEITSTELLE_ADRESSE)")
    if data.lm_studio_model is not None:
        await ki.waehlen(data.lm_studio_model)
    return await _ki_config()


# --- Prompt-Verwaltung ---

class PromptUpdate(BaseModel):
    name: Promptname | None = None
    beschreibung: Promptbeschreibung | None = None
    system_prompt: Prompt | None = None
    temperatur: float | None = Field(None, ge=0, le=2)
    max_tokens: int | None = Field(None, ge=50, le=4000)
    aktiv: bool | None = None


@router.get("/prompts")
async def list_prompts(_token: str = Depends(verify_token)):
    """Gibt alle KI-Prompts zurück."""
    rows = await db.fetch_all(
        "SELECT * FROM ai_prompts ORDER BY schluessel"
    )
    return rows


@router.get("/prompts/{prompt_id}")
async def get_prompt(prompt_id: Nr, _token: str = Depends(verify_token)):
    """Gibt einen einzelnen Prompt zurück."""
    row = await db.fetch_one(
        "SELECT * FROM ai_prompts WHERE id = ?", (prompt_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Prompt nicht gefunden")
    return row


@router.patch("/prompts/{prompt_id}")
async def update_prompt(
    prompt_id: Nr, data: PromptUpdate, _token: str = Depends(verify_token)
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
        updates["temperatur"] = data.temperatur
    if data.max_tokens is not None:
        updates["max_tokens"] = data.max_tokens
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
async def reset_prompt(prompt_id: Nr, _token: str = Depends(verify_token)):
    """Setzt einen Prompt auf den Standardwert zurück (löscht und migriert neu)."""
    existing = await db.fetch_one(
        "SELECT schluessel FROM ai_prompts WHERE id = ?", (prompt_id,)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Prompt nicht gefunden")

    return {"message": "Prompt kann manuell zurückgesetzt werden."}
