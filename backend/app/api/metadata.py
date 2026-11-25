"""API-Endpunkte für Metadatenanreicherung."""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.services.seiten import buch_seiten
from backend.app.core.auth import verify_token
from backend.app.core.database import db
from backend.app.quellen import auskunft, bilder, stand
from backend.app.quellen.fehler import QuelleFehler
from backend.app.quellen.regeln import REGELN
from backend.app.quellen.stand import Quellenstand
from backend.app.quellen.vorschlag import frage_aus, vorschlag
from backend.app.services.autorennamen import zerlegen
from backend.app.services.data_cleaner import bereinige_kategorien
from backend.app.services.storage import save_cover

logger = logging.getLogger("buecherfreunde.api.metadata")

router = APIRouter(prefix="/api/metadata", tags=["Metadaten"])


def _slugify(text: str) -> str:
    """Erzeugt einen URL-freundlichen Slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


async def _sync_book_authors(book_id: int, author_str: str) -> None:
    """Synchronisiert die authors/book_authors-Tabelle mit dem Autoren-String eines Buchs.

    Entfernt alte Verknüpfungen, parst den String und erstellt neue.
    """
    if not author_str:
        return

    namen = zerlegen(author_str)

    # Alte Verknüpfungen entfernen
    await db.execute("DELETE FROM book_authors WHERE book_id = ?", (book_id,))

    for i, name in enumerate(namen):
        name = name.strip()
        if not name or len(name) < 2:
            continue

        slug = _slugify(name)
        if not slug:
            continue

        existing = await db.fetch_one("SELECT id FROM authors WHERE slug = ?", (slug,))
        if existing:
            author_id = existing["id"]
        else:
            cursor = await db.execute(
                "INSERT INTO authors (name, slug) VALUES (?, ?)",
                (name, slug),
            )
            author_id = cursor.lastrowid

        await db.execute(
            "INSERT OR IGNORE INTO book_authors (book_id, author_id, sort_order) VALUES (?, ?, ?)",
            (book_id, author_id, i),
        )


async def _ensure_categories(names: list[str]) -> list[int]:
    """Stellt sicher, dass Kategorien existieren und gibt deren IDs zurück.

    Erstellt fehlende Kategorien automatisch.
    """
    cat_ids = []
    for name in names:
        name = name.strip()
        if not name or len(name) < 2:
            continue

        slug = _slugify(name)
        if not slug:
            continue

        existing = await db.fetch_one(
            "SELECT id FROM categories WHERE slug = ?", (slug,)
        )
        if existing:
            cat_ids.append(existing["id"])
        else:
            try:
                cursor = await db.execute(
                    """INSERT INTO categories (name, slug, description, color, icon, sort_order)
                       VALUES (?, ?, '', '#6b7280', '', 0)""",
                    (name, slug),
                )
                cat_ids.append(cursor.lastrowid)
            except Exception:
                # Slug-Kollision bei gleichzeitigem Zugriff
                existing = await db.fetch_one(
                    "SELECT id FROM categories WHERE slug = ?", (slug,)
                )
                if existing:
                    cat_ids.append(existing["id"])

    return cat_ids


async def _assign_categories(book_id: int, cat_ids: list[int]) -> None:
    """Ordnet Kategorien einem Buch zu (addiert, ersetzt nicht)."""
    for cat_id in cat_ids:
        await db.execute(
            "INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'metadaten')",
            (book_id, cat_id),
        )


async def _kategorienamen(book_id: int) -> list[str]:
    zeilen = await db.fetch_all("SELECT c.name FROM categories c JOIN book_categories bc ON bc.category_id = c.id WHERE bc.book_id = ?", (book_id,))
    return [z["name"] for z in zeilen]


def _kein_fund(quelle: str | None, hinweise: list[str]) -> str:
    """Warum es keinen Vorschlag gibt: die Quelle antwortet nicht, oder dort steht nichts."""
    if hinweise:
        return ". ".join(hinweise)
    if quelle in REGELN:
        return f"{REGELN[quelle].name} kennt dieses Buch nicht."
    return "Keine Quelle kennt dieses Buch."


@router.post("/buch/{book_id}/anreichern")
async def enrich_book(
    book_id: int,
    quelle: str | None = Query(None, description="Kennung einer Quelle oder \"alle\"; ohne Angabe die erste, die etwas weiß"),
    _token: str = Depends(verify_token),
):
    """Sucht Angaben zu einem Buch, als Vorschlag zum Vergleichen. Geändert wird nichts.

    `alle` nimmt je Feld die beste Angabe, `vorschlag.herkunft` nennt die Quelle je Feld.
    """
    if quelle not in (None, auskunft.ALLE, *auskunft.QUELLEN):
        raise HTTPException(status_code=422, detail="Diese Quelle gibt es nicht")
    book = await db.fetch_one(
        "SELECT id, hash, isbn, title, author, publisher, year, language, "
        "description, page_count, cover_path FROM books WHERE id = ?",
        (book_id,),
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    antwort = await auskunft.suche(frage_aus(book), quelle)
    if antwort.angaben is None:
        return {"angereichert": False, "grund": _kein_fund(quelle, antwort.hinweise), "hinweise": antwort.hinweise}

    return {
        "angereichert": True,
        "quelle": antwort.angaben.quelle,
        "vorschlag": vorschlag(antwort.angaben, book),
        "hinweise": antwort.hinweise,
        "aktuell": {
            "titel": book["title"],
            "autor": book["author"],
            "isbn": book["isbn"],
            "verlag": book["publisher"],
            "jahr": book["year"],
            "sprache": book["language"],
            "beschreibung": book["description"],
            "seiten": book["page_count"],
            "hat_cover": bool(book["cover_path"]),
            "kategorien": await _kategorienamen(book_id),
        },
    }


async def _umschlag_holen(adresse: str) -> tuple[bytes | None, str]:
    """Das Bild und, wenn es keines gibt, warum."""
    if not adresse:
        return None, ""
    try:
        bild = await bilder.umschlag(adresse)
    except QuelleFehler as f:
        return None, f.grund
    return bild, "" if bild else "Dort liegt kein brauchbares Bild"


@router.post("/buch/{book_id}/uebernehmen")
async def apply_metadata(
    book_id: int, felder: dict, _token: str = Depends(verify_token)
):
    """Übernimmt vorgeschlagene Metadaten für ein Buch.

    Aktualisiert Buchfelder, erstellt/verknüpft Kategorien,
    lädt Cover-Bild herunter und persistiert es.
    """
    book = await db.fetch_one(
        "SELECT id, hash, cover_path FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    cover_data, hinweis = await _umschlag_holen(felder.get("cover_url", ""))      # vor dem Schreiben, es kann dauern

    # Buch-Felder aktualisieren
    allowed = {"title", "author", "isbn", "publisher", "year", "language", "description", "page_count"}
    field_map = {
        "titel": "title",
        "autor": "author",
        "isbn": "isbn",
        "verlag": "publisher",
        "jahr": "year",
        "sprache": "language",
        "beschreibung": "description",
        "seiten": "page_count",
    }

    updates = {}
    for key, value in felder.items():
        if key in ("kategorien", "cover_url", "raw", "identifiers", "excerpts", "links"):
            continue
        db_key = field_map.get(key, key)
        if db_key in allowed and value:
            updates[db_key] = value

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [book_id]
        await db.execute(
            f"UPDATE books SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            tuple(values),
        )

    # Autoren-Tabelle synchronisieren
    if "author" in updates:
        await _sync_book_authors(book_id, updates["author"])

    # Kategorien erstellen und zuordnen (immer bereinigen)
    kategorien = felder.get("kategorien", [])
    if kategorien:
        kategorien = bereinige_kategorien(kategorien)
        cat_ids = await _ensure_categories(kategorien)
        await _assign_categories(book_id, cat_ids)

    if cover_data:
        save_cover(book["hash"], cover_data)
        await db.execute(
            "UPDATE books SET cover_path = 'cover.jpg', updated_at = datetime('now') WHERE id = ?",
            (book_id,),
        )

    await db.commit()

    return {
        "uebernommen": True,
        "felder": list(updates.keys()),
        "kategorien_erstellt": len(kategorien),
        "cover_gespeichert": cover_data is not None,
        "hinweis": hinweis,
    }



@router.get("/buch/{book_id}/volltext")
async def get_fulltext(
    book_id: int,
    seite_von: int = Query(1, ge=1, description="Startseite (1-basiert)"),
    seite_bis: int = Query(5, ge=1, description="Endseite (inklusiv)"),
    _token: str = Depends(verify_token),
):
    """Gibt einen Seitenbereich des Volltextes zurück.

    Der Volltext wird anhand von Seitenumbruch-Markern oder gleichmäßig
    in Seiten aufgeteilt.
    """
    book = await db.fetch_one(
        "SELECT hash, page_count, file_format FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    import asyncio
    seiten, _gedruckt = await asyncio.to_thread(buch_seiten, book["hash"], book["file_format"], book["page_count"])
    if not seiten:
        return {"volltext": "", "seiten_gesamt": 0, "seite_von": 1, "seite_bis": 1}

    seiten_gesamt = len(seiten)
    # Bereich begrenzen
    von = max(1, min(seite_von, seiten_gesamt))
    bis = max(von, min(seite_bis, seiten_gesamt))

    ausschnitt = "\n".join(seiten[von - 1:bis])

    return {
        "volltext": ausschnitt,
        "seiten_gesamt": seiten_gesamt,
        "seite_von": von,
        "seite_bis": bis,
    }


@router.get("/quellen")
async def quellen(_token: str = Depends(verify_token)) -> list[Quellenstand]:
    """Alle Quellen mit ihrem gemerkten Stand; gefragt wird dabei keine."""
    return await stand.alle()


@router.post("/quellen/{kennung}/pruefen")
async def quelle_pruefen(kennung: str, _token: str = Depends(verify_token)) -> Quellenstand:
    """Eine echte Probe bei einer Quelle, höchstens einmal in der Minute; sonst der gemerkte Stand."""
    if kennung not in REGELN:
        raise HTTPException(status_code=404, detail="Diese Quelle gibt es nicht")
    return await stand.pruefe(kennung)


@router.get("/verbindungsstatus")
async def connection_status(_token: str = Depends(verify_token)):
    """Der gemerkte Stand je Quelle in kurzer Form (erreichbar, Grund); gefragt wird dabei keine."""
    return {s.kennung: {"erreichbar": s.erreichbar, "grund": ("Deaktiviert" if not s.aktiv else s.grund or ("" if s.erreichbar else s.wort))} for s in await stand.alle()}
