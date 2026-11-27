"""API-Endpunkte für Metadatenanreicherung."""

import logging
import re

from pydantic import BaseModel, Field, ValidationError
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from backend.app.annahme import dateiangaben
from backend.app.services.seiten import buch_seiten
from backend.app.core.auth import braucht, verify_token
from backend.app.core.database import db
from backend.app.isbnsuche.kandidaten import aus_quelle
from backend.app.isbnsuche.modelle import Einstufung
from backend.app.quellen.abgleich import isbn_abgleich
from backend.app.quellen.alter import Alter
from backend.app.quellen import auskunft, bilder, stand
from backend.app.quellen import isbn as nummern
from backend.app.quellen.fehler import QuelleFehler
from backend.app.quellen.modelle import Angaben, Buchfrage
from backend.app.quellen.regeln import REGELN
from backend.app.quellen.stand import Quellenstand
from backend.app.quellen.vorschlag import frage_aus, vorschlag
from backend.app.services.autorennamen import zerlegen
from backend.app.services.data_cleaner import bereinige_kategorien
from backend.app.services.storage import save_cover
from backend.app.models.grenzen import AUTOR, SEITEN_HOECHSTENS, TITEL, Isbn, Nr

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


def _kein_fund(quelle: str | None, hinweise: list[str], isbn: str | None = None) -> str:
    """Warum es keinen Vorschlag gibt: die Quelle antwortet nicht, oder dort steht nichts."""
    if hinweise:
        return ". ".join(hinweise)
    was = f"die ISBN {nummern.mit_strichen(isbn) or isbn}" if isbn else "dieses Buch"
    if quelle in REGELN:
        return f"{REGELN[quelle].name} kennt {was} nicht."
    return f"Keine Quelle kennt {was}."


class Angabenfrage(BaseModel):
    """Wonach gesucht wird, wenn es nicht das Gespeicherte ist (BF-111). `isbn`: ohne Angabe die gespeicherte, leer heißt ohne ISBN
    (über Titel und Autor), sonst nur diese ISBN. `titel` und `autor`: wie sie gerade im Formular stehen, für die Suche über den
    Titel und die Prüfung, ob ein Fund zum Buch passt."""

    isbn: Isbn | None = None
    titel: str | None = Field(None, max_length=TITEL)
    autor: str | None = Field(None, max_length=AUTOR)


def _frage(book: dict, angaben: Angabenfrage) -> Buchfrage:
    stand_im_formular = {"isbn": angaben.isbn, "title": angaben.titel, "author": angaben.autor}
    return frage_aus({**book, **{k: v for k, v in stand_im_formular.items() if v is not None}})


def _abgleich(frage: Buchfrage, fund: Angaben) -> Einstufung | None:
    """Passt ein Fund über die ISBN zum Buch? Für die Warnung im Vergleich, wenn das gefundene Buch ein anderes ist."""
    return aus_quelle(isbn_abgleich(frage, fund), fund) if fund.fund == "isbn" else None


async def _aus_der_datei(book: dict) -> tuple[Angaben | None, str]:
    gelesen = await dateiangaben.lesen(book["hash"], (book["file_format"] or "").lower())
    return gelesen.angaben, gelesen.grund


@router.post("/buch/{book_id}/anreichern", dependencies=[Depends(braucht("bearbeiten"))])
async def enrich_book(
    book_id: Nr,
    quelle: str | None = Query(None, description="Kennung einer Quelle, \"alle\" oder \"datei\" (Angaben der Datei neu gelesen); ohne Angabe die erste, die etwas weiß"),
    angaben: Angabenfrage | None = Body(None),
    _token: str = Depends(verify_token),
):
    """Sucht Angaben zu einem Buch, als Vorschlag zum Vergleichen. Geändert wird nichts.

    `alle` nimmt je Feld die beste Angabe, `vorschlag.herkunft` nennt die Quelle je Feld. Mit einer ISBN in `angaben` wird nur über
    sie gesucht; `abgleich` sagt dann, ob das gefundene Buch zu Titel und Autor passt.
    """
    if quelle not in (None, auskunft.ALLE, dateiangaben.DATEI, *auskunft.QUELLEN):
        raise HTTPException(status_code=422, detail="Diese Quelle gibt es nicht")
    angaben = angaben or Angabenfrage()
    if angaben.isbn and not nummern.gueltig(angaben.isbn):
        raise HTTPException(status_code=422, detail="Das ist keine gültige ISBN")
    book = await db.fetch_one(
        "SELECT id, hash, isbn, title, author, publisher, year, language, "
        "description, page_count, cover_path, file_format FROM books WHERE id = ?",
        (book_id,),
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    frage = _frage(book, angaben)
    hinweise: list[str] = []
    if quelle == dateiangaben.DATEI:
        fund, grund = await _aus_der_datei(book)
    else:
        antwort = await auskunft.suche(frage, quelle, nur_isbn=bool(angaben.isbn))
        fund, hinweise = antwort.angaben, antwort.hinweise
        grund = "" if fund else _kein_fund(quelle, hinweise, angaben.isbn)
    if fund is None:
        return {"angereichert": False, "grund": grund, "hinweise": hinweise}

    return {
        "angereichert": True,
        "quelle": fund.quelle,
        "vorschlag": vorschlag(fund, book),
        "hinweise": hinweise,
        "abgleich": _abgleich(frage, fund),
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


@router.post("/buch/{book_id}/uebernehmen", dependencies=[Depends(braucht("bearbeiten"))])
async def apply_metadata(
    book_id: Nr, felder: dict, _token: str = Depends(verify_token)
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

    if felder.get("alter_von") is not None or felder.get("alter_bis") is not None:     # Altersangabe mit Herkunft (BF-78)
        try:
            alter = Alter.model_validate({"von": felder.get("alter_von"), "bis": felder.get("alter_bis")})
        except ValidationError:
            raise HTTPException(status_code=422, detail="Alter: zwischen 0 und 99") from None
        herkunft = felder.get("herkunft") if isinstance(felder.get("herkunft"), dict) else {}
        updates |= {"alter_von": alter.von, "alter_bis": alter.bis, "alter_quelle": str(herkunft.get("alter") or felder.get("quelle") or "")[:50]}

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
    book_id: Nr,
    seite_von: int = Query(1, ge=1, le=SEITEN_HOECHSTENS, description="Startseite (1-basiert)"),
    seite_bis: int = Query(5, ge=1, le=SEITEN_HOECHSTENS, description="Endseite (inklusiv)"),
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


@router.get("/quellen", dependencies=[Depends(braucht("bearbeiten"))])
async def quellen(_token: str = Depends(verify_token)) -> list[Quellenstand]:
    """Alle Quellen mit ihrem gemerkten Stand; gefragt wird dabei keine."""
    return await stand.alle()


@router.post("/quellen/{kennung}/pruefen", dependencies=[Depends(braucht("einstellungen"))])
async def quelle_pruefen(kennung: str, _token: str = Depends(verify_token)) -> Quellenstand:
    """Eine echte Probe bei einer Quelle, höchstens einmal in der Minute; sonst der gemerkte Stand."""
    if kennung not in REGELN:
        raise HTTPException(status_code=404, detail="Diese Quelle gibt es nicht")
    return await stand.pruefe(kennung)


@router.get("/verbindungsstatus", dependencies=[Depends(braucht("bearbeiten"))])
async def connection_status(_token: str = Depends(verify_token)):
    """Der gemerkte Stand je Quelle in kurzer Form (erreichbar, Grund); gefragt wird dabei keine."""
    return {s.kennung: {"erreichbar": s.erreichbar, "grund": ("Deaktiviert" if not s.aktiv else s.grund or ("" if s.erreichbar else s.wort))} for s in await stand.alle()}
