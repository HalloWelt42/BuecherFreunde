"""API-Endpunkte für Bücher. Jede Liste und jedes Buch nur, wie es das Profil sieht (BF-78, familie/sichtbar.py); Lesestand,
Favoriten und Sterne sind die des Profils."""

import asyncio
import logging
import math
from pathlib import Path
from xml.sax.saxutils import escape

from typing import Annotated, Literal

from fastapi import Request, APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, StringConstraints

from backend.app.services.seiten import buch_seiten
from backend.app.core.auth import braucht, profil, verify_token_inhalt
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.core.fehlerantworten import BEZUG_FEHLT
from backend.app.familie import rechte, sichtbar
from backend.app.familie.ansagelauf import ansagelauf
from backend.app.familie.stufen import stufenbuch
from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht
from backend.app.api import vorhanden
from backend.app.models.book import (
    DARSTELLUNG, FELDER_DER_EINORDNUNG, FELDER_DES_ALTERS, LEERBAR, VON_HAND, BookListResponse, BookListItem, BookResponse, BookUpdate, BuchEintrag,
    Listeneintrag, SammlungsEintrag, Sammlungsstapel, Werkart, typ_pruefen,
)
from backend.app.models.textansicht import TextBaustein, TextSeite, TextSeitenAntwort
from backend.app.services.textansicht import Baustein, Codeteil, abbildung_png, seiten_lesen
import fitz

from backend.app.codestellen.dienst import codestellen
from backend.app.texterkennung import ablage as erkennungsablage
from backend.app.texterkennung.auftrag import texterkennung
from backend.app.ablage import formate
from backend.app.ablage.antwort import FEHLT, original_antwort
from backend.app.material import dienst as material_dienst
from backend.app.annahme.eintragen import autoren_verknuepfen
from backend.app.einrichtung import pruefung as original_pruefung
from backend.app.services import buch_loeschen, buchliste, buchsuche, deckblatt, sammlungen, schnellfilter
from backend.app.katalog import kategorien as katalog_kategorien
from backend.app.katalog.merkmale import IN_KATEGORIE
from backend.app.services.storage import get_original_file, get_sidecar_path, save_cover
from backend.app.models.grenzen import AUSWAHL_HOECHSTENS, GROESSTE_ZAHL, JAHR_BIS, LEBENSJAHR_AB, LISTENSEITE, SEITEN_HOECHSTENS, Index, Nr

router = APIRouter(prefix="/api/books", tags=["Bücher"])

# Die Spalten eines Buchs in der Liste (BookListItem), für jede Abfrage, die Listeneinträge liefert
LISTENSPALTEN = ("id", "hash", "title", "author", "publisher", "file_format", "file_size", "cover_path", "page_count", "year", "isbn",
                 "typ", "gattung", "umschlag_wahl", "umschlag_schlicht", "sammlung_id", "band_nummer", "alter_von", "alter_bis", "alter_quelle",
                 "created_at", "updated_at")


def listenspalten(tabelle: str = "b") -> str:
    return ", ".join(f"{tabelle}.{s}" for s in LISTENSPALTEN)


async def _get_book_categories(book_id: int) -> list[dict]:
    """Kategorien und Regale eines Buchs, je mit Art, Zeichen, Farbe und Bereich (BF-69)."""
    return await katalog_kategorien.kategorien_eines_buchs(book_id)


async def _get_book_sammlung(book: dict) -> dict | None:
    """Lädt die Sammlung eines Buches (1:1 über FK)."""
    if not book.get("sammlung_id"):
        return None
    row = await db.fetch_one(
        "SELECT id, name, color FROM collections WHERE id = ?",
        (book["sammlung_id"],),
    )
    if row:
        result = dict(row)
        result["band_nummer"] = book.get("band_nummer", "")
        return result
    return None


async def _get_book_authors(book_id: int) -> list[dict]:
    """Lädt Autoren eines Buches."""
    rows = await db.fetch_all(
        """SELECT a.id, a.name, a.slug, a.photo_path, ba.role
           FROM authors a
           JOIN book_authors ba ON ba.author_id = a.id
           WHERE ba.book_id = ?
           ORDER BY ba.sort_order ASC""",
        (book_id,),
    )
    return rows


async def _get_user_data(book_id: int, p: Profil) -> dict:
    """Lädt die Nutzerdaten des Profils zu einem Buch."""
    row = await db.fetch_one(
        "SELECT * FROM user_book_data WHERE profil_id = ? AND book_id = ?", (p.id, book_id)
    )
    if row:
        return row
    return {
        "is_favorite": False,
        "is_to_read": False,
        "rating": 0,
        "reading_position": "",
        "last_read_at": None,
    }


async def _enrich_book_list_item(book: dict, p: Profil) -> BookListItem:
    """Reichert ein Buch-Dict mit Relationen an (Einzelbuch-Fallback)."""
    ud = await _get_user_data(book["id"], p)
    cats = await _get_book_categories(book["id"])
    sammlung = await _get_book_sammlung(book)
    return BookListItem(
        **book,
        is_favorite=bool(ud.get("is_favorite")),
        is_to_read=bool(ud.get("is_to_read")),
        rating=ud.get("rating", 0),
        reading_position=ud.get("reading_position", ""),
        last_read_at=ud.get("last_read_at"),
        fertig_am=ud.get("fertig_am"),
        categories=cats,
        sammlung=sammlung,
        privat=bool(await sichtbar.private(p.id, [book["id"]])),
        material=(await material_dienst.anzahlen([book["id"]])).get(book["id"], 0),
    )


async def listenbuecher(rows: list[dict], p: Profil) -> list[BookListItem]:
    """Buchzeilen als Listeneinträge, die Relationen je Art in einer Abfrage für alle (statt N+1); Nutzerdaten des Profils."""
    if not rows:
        return []

    book_ids = [r["id"] for r in rows]
    ph = ",".join("?" * len(book_ids))

    # 1. user_book_data batch, die des Profils
    ud_rows = await db.fetch_all(
        f"SELECT * FROM user_book_data WHERE profil_id = ? AND book_id IN ({ph})",
        (p.id, *book_ids),
    )
    ud_map = {r["book_id"]: r for r in ud_rows}
    privat = await sichtbar.private(p.id, book_ids)
    material = await material_dienst.anzahlen(book_ids)

    # 2. Kategorien batch
    cat_rows = await db.fetch_all(
        f"""SELECT bc.book_id, c.id, c.name, c.slug
            FROM book_categories bc
            JOIN categories c ON c.id = bc.category_id
            WHERE bc.book_id IN ({ph})""",
        tuple(book_ids),
    )
    cat_map: dict[int, list] = {}
    for r in cat_rows:
        cat_map.setdefault(r["book_id"], []).append(
            {"id": r["id"], "name": r["name"], "slug": r["slug"]}
        )

    # 3. Sammlungen batch (nur fuer Buecher mit sammlung_id)
    samml_ids = list({r["sammlung_id"] for r in rows if r.get("sammlung_id")})
    samml_map: dict[int, dict] = {}
    if samml_ids:
        sph = ",".join("?" * len(samml_ids))
        samml_rows = await db.fetch_all(
            f"SELECT id, name, color FROM collections WHERE id IN ({sph})",
            tuple(samml_ids),
        )
        samml_map = {r["id"]: dict(r) for r in samml_rows}

    # Zusammenbauen
    result = []
    for book in rows:
        bid = book["id"]
        ud = ud_map.get(bid, {})
        cats = cat_map.get(bid, [])
        sammlung = None
        if book.get("sammlung_id") and book["sammlung_id"] in samml_map:
            sammlung = {**samml_map[book["sammlung_id"]], "band_nummer": book.get("band_nummer", "")}

        result.append(BookListItem(
            **book,
            is_favorite=bool(ud.get("is_favorite")),
            is_to_read=bool(ud.get("is_to_read")),
            rating=ud.get("rating", 0),
            reading_position=ud.get("reading_position", ""),
            last_read_at=ud.get("last_read_at"),
            fertig_am=ud.get("fertig_am"),
            categories=cats,
            sammlung=sammlung,
            privat=bid in privat,
            material=material.get(bid, 0),
        ))
    return result


@router.get("", response_model=BookListResponse)
async def list_books(
    p: Profil = Depends(profil),
    seite: int = Query(1, ge=1, le=LISTENSEITE, description="Seitennummer"),
    pro_seite: int = Query(24, ge=1, le=100, description="Einträge pro Seite"),
    kategorie: str | None = Query(None, description="Kategorie-ID(s), kommagetrennt"),
    sammlung: Nr | None = Query(None, description="Sammlungs-ID Filter"),
    ohne_sammlung: bool | None = Query(None, description="True: nur Bücher ohne Sammlung, False: nur die in einer"),
    nicht_kategorie: Nr | None = Query(None, description="Nur Bücher, die nicht in diesem Regal stehen"),
    ohne_kategorie: bool | None = Query(None, description="True: nur Bücher in keiner Kategorie des Katalogs, False: nur die in einer"),
    typ: str | None = Query(None, description="Typ-Filter (dokument, heft, katalog, broschuere)"),
    art: Werkart | None = Query(None, description="buch: nur Bücher (Art leer), besonderes: alles, was kein Buch ist"),
    favorit: bool | None = Query(None, description="Nur Favoriten"),
    zu_lesen: bool | None = Query(None, description="Nur Zum-Lesen"),
    bewertung_min: int | None = Query(None, ge=0, le=5, description="Mindestbewertung"),
    format: str | None = Query(None, description="Dateiformat (.pdf, .epub, ...)"),
    gelesen: bool | None = Query(None, description="Nur fertig gelesene Bücher (familie/lesestand.py)"),
    hat_isbn: bool | None = Query(None, description="True=mit ISBN, False=ohne ISBN"),
    weiterlesen: bool | None = Query(None, description="Bücher mit Leseposition"),
    hat_labels: bool | None = Query(None, description="Bücher mit Labels"),
    hat_highlights: bool | None = Query(None, description="Bücher mit Textmarkierungen"),
    autor: str | None = Query(None, description="Autor-Filter (exakter Match oder LIKE)"),
    verlag: str | None = Query(None, description="Verlag-Filter (exakter Match oder LIKE)"),
    jahr_von: int | None = Query(None, ge=LEBENSJAHR_AB, le=JAHR_BIS, description="Erscheinungsjahr ab"),
    jahr_bis: int | None = Query(None, ge=LEBENSJAHR_AB, le=JAHR_BIS, description="Erscheinungsjahr bis"),
    suche: str | None = Query(None, description="Schnellfilter: jedes Wort in Titel, Autor, ISBN oder Etikett"),
    sortierung: str = Query("titel", description="Sortierung: titel, autor, datum, bewertung, groesse, jahr, verlag, band"),
    richtung: str = Query("asc", description="Sortierrichtung: asc, desc"),
    zusammenfassen: bool = Query(False, description="Große Sammlungen als ein Eintrag (BF-66)"),
):
    """Listet Bücher paginiert und filterbar auf. Jeder Schalter filtert in beide Richtungen: true nur die mit, false nur
    die ohne. Nur Bücher, die das Profil sieht; Favorit, Lesesofa, Sterne, Lesestand, Etiketten und Markierungen sind seine."""
    # Basis-Query aufbauen: zuerst die Sichtbarkeit (BF-78)
    sicht_sql, sicht_werte = Sicht.von(p).bedingung("b.id")
    conditions = [sicht_sql]
    params: list = [*sicht_werte]

    def eigene(bedingung: str) -> str:
        """Bücher, zu denen das Profil Nutzerdaten mit dieser Bedingung hat."""
        params.append(p.id)
        return f"SELECT book_id FROM user_book_data WHERE profil_id = ? AND {bedingung}"

    def ob(wert: bool, buecher: str) -> str:
        return f"b.id {'' if wert else 'NOT '}IN ({buecher})"

    if kategorie is not None:
        kat_ids = [int(k) for k in kategorie.split(",") if k.strip().isdigit() and 0 < int(k) <= GROESSTE_ZAHL]
        if len(kat_ids) == 1:
            conditions.append("b.id IN (SELECT book_id FROM book_categories WHERE category_id = ?)")
            params.append(kat_ids[0])
        elif len(kat_ids) > 1:
            ph = ",".join("?" * len(kat_ids))
            conditions.append(f"b.id IN (SELECT book_id FROM book_categories WHERE category_id IN ({ph}))")
            params.extend(kat_ids)

    if sammlung is not None:
        conditions.append("b.sammlung_id = ?")
        params.append(sammlung)

    if ohne_sammlung is not None:
        conditions.append(f"b.sammlung_id IS {'' if ohne_sammlung else 'NOT '}NULL")

    if nicht_kategorie is not None:
        conditions.append("b.id NOT IN (SELECT book_id FROM book_categories WHERE category_id = ?)")
        params.append(nicht_kategorie)

    if ohne_kategorie is not None:
        conditions.append(f"{'NOT ' if ohne_kategorie else ''}{IN_KATEGORIE}")

    if typ is not None and typ.strip():
        conditions.append("b.typ = ?")
        params.append(typ.strip())

    if art is not None:
        bedingung, werte = buchliste.nach_art(art)
        conditions.append(bedingung)
        params.extend(werte)

    if favorit is not None:
        conditions.append(ob(favorit, eigene("is_favorite = 1")))

    if zu_lesen is not None:
        conditions.append(ob(zu_lesen, eigene("is_to_read = 1")))

    if bewertung_min is not None:
        conditions.append(f"b.id IN ({eigene('rating >= ?')})")
        params.append(bewertung_min)

    if gelesen is not None:
        if not rechte.darf(p, "gelesen"):
            raise HTTPException(status_code=403, detail=f"Das darf dieses Profil nicht: {stufenbuch().faehigkeiten['gelesen']}")
        conditions.append(ob(gelesen, eigene("fertig_am IS NOT NULL")))

    if weiterlesen is not None:
        conditions.append(ob(weiterlesen, eigene("reading_position IS NOT NULL AND reading_position != '' AND last_read_at IS NOT NULL")))

    if hat_labels is not None:
        conditions.append(ob(hat_labels, schnellfilter.MIT_ETIKETTEN))
        params.extend((p.id, p.id))

    if hat_highlights is not None:
        conditions.append(ob(hat_highlights, "SELECT book_id FROM book_highlights WHERE profil_id = ?"))
        params.append(p.id)

    if hat_isbn is not None:
        if hat_isbn:
            conditions.append("b.isbn IS NOT NULL AND b.isbn != ''")
        else:
            conditions.append("(b.isbn IS NULL OR b.isbn = '')")

    if autor is not None and autor.strip():
        conditions.append("b.author LIKE ?")
        params.append(f"%{autor.strip()}%")

    if verlag is not None and verlag.strip():
        conditions.append("b.publisher LIKE ?")
        params.append(f"%{verlag.strip()}%")

    if jahr_von is not None:
        conditions.append("b.year >= ?")
        params.append(jahr_von)

    if jahr_bis is not None:
        conditions.append("b.year <= ?")
        params.append(jahr_bis)

    if format is not None:
        formats = [f.lower().lstrip(".") for f in format.split(",") if f.strip()]
        if len(formats) == 1:
            conditions.append("b.file_format = ?")
            params.append(formats[0])
        elif len(formats) > 1:
            placeholders = ",".join("?" * len(formats))
            conditions.append(f"b.file_format IN ({placeholders})")
            params.extend(formats)

    where = " AND ".join(conditions) if conditions else "1=1"

    # Schnellfilter zuletzt: die Zahl davor sagt, wie viele die Ansicht ohne ihn zeigt
    gesamt_ohne_suche = None
    if suche and suche.strip() and not rechte.darf(p, "suche"):
        raise HTTPException(status_code=403, detail=f"Das darf dieses Profil nicht: {stufenbuch().faehigkeiten['suche']}")
    filter_sql, filter_werte = schnellfilter.bedingung(suche, p.id)
    if filter_sql:
        ohne_row = await db.fetch_one(f"SELECT COUNT(*) as total FROM books b WHERE {where}", tuple(params))
        gesamt_ohne_suche = ohne_row["total"] if ohne_row else 0
        where = f"{where} AND {filter_sql}"
        params.extend(filter_werte)

    o = buchliste.ordnung(sortierung, richtung, p.id)
    if zusammenfassen:
        return await _zusammengefasst(where, tuple(params), o, seite, pro_seite, gesamt_ohne_suche, p)

    # Gesamt zählen
    count_sql = f"SELECT COUNT(*) as total FROM books b WHERE {where}"
    count_row = await db.fetch_one(count_sql, tuple(params))
    gesamt = count_row["total"] if count_row else 0

    # Seite abfragen
    offset = (seite - 1) * pro_seite
    select_sql = f"""
        SELECT {listenspalten()}
        FROM books b
        {o.verbindung}
        WHERE {where}
        ORDER BY {o.sql()}
        LIMIT ? OFFSET ?
    """
    rows = await db.fetch_all(select_sql, (*o.werte, *params, pro_seite, offset))

    buecher = await listenbuecher(rows, p)

    return BookListResponse(
        buecher=buecher,
        gesamt=gesamt,
        seite=seite,
        pro_seite=pro_seite,
        seiten_gesamt=math.ceil(gesamt / pro_seite) if gesamt > 0 else 0,
        gesamt_ohne_suche=gesamt_ohne_suche,
    )


async def buecher_mit_nummern(nummern: list[int], p: Profil) -> dict[int, BookListItem]:
    """Die Bücher mit diesen Nummern als Listeneinträge, je Nummer; nur die, die das Profil sieht."""
    if not nummern:
        return {}
    bedingung, werte = Sicht.von(p).bedingung("b.id")
    zeilen = await db.fetch_all(f"SELECT {listenspalten()} FROM books b WHERE b.id IN ({','.join('?' * len(nummern))}) AND {bedingung}",
                                (*nummern, *werte))
    return {b.id: b for b in await listenbuecher(zeilen, p)}


async def _stapel(where: str, werte: tuple, seite: list[buchliste.Eintrag], p: Profil) -> dict[int, Sammlungsstapel]:
    """Die Sammlungseinträge der Seite mit ihren ersten Umschlägen."""
    eintraege = [e for e in seite if e.art == "sammlung"]
    roh = await buchliste.stapel(where, werte, [e.nr for e in eintraege], listenspalten())
    umschlaege = await listenbuecher([z for e in eintraege for z in roh.get(e.nr, [])], p)
    return {e.nr: Sammlungsstapel(id=e.nr, name=e.name, anzahl=e.anzahl, autor=e.autor,
                                  umschlaege=[b for b in umschlaege if b.sammlung_id == e.nr]) for e in eintraege}


async def _zusammengefasst(where: str, werte: tuple, o: buchliste.Ordnung, seite: int, pro_seite: int,
                           gesamt_ohne_suche: int | None, p: Profil) -> BookListResponse:
    """Die Liste mit großen Sammlungen als je einem Eintrag (BF-66); `buecher` trägt nur die einzeln gezeigten."""
    ab = await sammlungen.als_eintrag_ab()
    zahlen = await buchliste.zahlen(where, werte, ab)
    seite_ = await buchliste.eintraege(where, werte, o, ab, pro_seite, (seite - 1) * pro_seite)
    einzeln = [e.nr for e in seite_ if e.art == "buch"]
    buecher = await buecher_mit_nummern(einzeln, p)
    stapel = await _stapel(where, werte, seite_, p)
    eintraege: list[Listeneintrag] = [BuchEintrag(buch=buecher[e.nr]) if e.art == "buch" else SammlungsEintrag(sammlung=stapel[e.nr])
                                      for e in seite_]
    return BookListResponse(
        buecher=[buecher[n] for n in einzeln],
        eintraege=eintraege,
        gesamt=zahlen.buecher,
        gesamt_eintraege=zahlen.eintraege,
        in_sammlungen=zahlen.in_sammlungen,
        sammlungen_zusammengefasst=zahlen.sammlungen,
        seite=seite,
        pro_seite=pro_seite,
        seiten_gesamt=math.ceil(zahlen.eintraege / pro_seite),
        gesamt_ohne_suche=gesamt_ohne_suche,
    )


@router.get("/recently-read", response_model=list[BookListItem])
async def recently_read(
    p: Profil = Depends(profil),
    limit: int = Query(10, ge=1, le=50),
):
    """Gibt die zuletzt gelesenen Bücher des Profils zurück."""
    bedingung, werte = Sicht.von(p).bedingung("b.id")
    sql = f"""
        SELECT {listenspalten()}
        FROM books b
        JOIN user_book_data ud ON ud.book_id = b.id AND ud.profil_id = ?
        WHERE ud.last_read_at IS NOT NULL AND {bedingung}
        ORDER BY ud.last_read_at DESC
        LIMIT ?
    """
    rows = await db.fetch_all(sql, (p.id, *werte, limit))
    return await listenbuecher(rows, p)


@router.get("/{book_id}/aehnliche")
async def similar_books(
    book_id: Nr,
    p: Profil = Depends(profil),
    limit: int = Query(6, ge=1, le=20),
):
    """Gibt aehnliche Buecher zurueck (gleicher Autor, gleiche Kategorie), nur solche, die das Profil sieht."""
    bedingung, werte = Sicht.von(p).bedingung("b.id")
    book = await db.fetch_one(
        "SELECT id, author FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    result = {"vom_autor": [], "in_kategorie": []}

    # Vom selben Autor (ueber authors-Tabelle oder author-Feld)
    author_ids = await db.fetch_all(
        "SELECT author_id FROM book_authors WHERE book_id = ?", (book_id,)
    )
    if author_ids:
        placeholders = ",".join("?" for _ in author_ids)
        ids = [a["author_id"] for a in author_ids]
        rows = await db.fetch_all(
            f"""SELECT DISTINCT {listenspalten()}
                FROM books b
                JOIN book_authors ba ON ba.book_id = b.id
                WHERE ba.author_id IN ({placeholders}) AND b.id != ? AND {bedingung}
                ORDER BY b.title LIMIT ?""",
            (*ids, book_id, *werte, limit),
        )
        result["vom_autor"] = await listenbuecher(rows, p)
    elif book["author"]:
        rows = await db.fetch_all(
            f"""SELECT {listenspalten()}
               FROM books b WHERE b.author = ? AND b.id != ? AND {bedingung}
               ORDER BY b.title LIMIT ?""",
            (book["author"], book_id, *werte, limit),
        )
        result["vom_autor"] = await listenbuecher(rows, p)

    # Im selben Regal; "Ungeordnet" ist keins
    cat_ids = await db.fetch_all(
        "SELECT x.category_id FROM book_categories x JOIN categories c ON c.id = x.category_id "
        "WHERE x.book_id = ? AND c.slug != 'ungeordnet'", (book_id,)
    )
    if cat_ids:
        regale = [c["category_id"] for c in cat_ids]
        already = {book_id} | {b.id for b in result["vom_autor"]}
        placeholders = ",".join("?" for _ in regale)
        exclude_ph = ",".join("?" for _ in already)
        rows = await db.fetch_all(
            f"""SELECT DISTINCT {listenspalten()}
                FROM books b
                JOIN book_categories bc ON bc.book_id = b.id
                WHERE bc.category_id IN ({placeholders}) AND b.id NOT IN ({exclude_ph}) AND {bedingung}
                ORDER BY b.title COLLATE NOCASE LIMIT ?""",
            (*regale, *already, *werte, limit),
        )
        result["in_kategorie"] = await listenbuecher(rows, p)

    return result


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: Nr, p: Profil = Depends(profil)):
    """Gibt die vollständigen Details eines Buches zurück, mit den Nutzerdaten des Profils."""
    row = await db.fetch_one("SELECT * FROM books WHERE id = ?", (book_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    ud = await _get_user_data(book_id, p)
    cats = await _get_book_categories(book_id)
    sammlung = await _get_book_sammlung(row)
    authors = await _get_book_authors(book_id)

    return BookResponse(
        **row,
        is_favorite=bool(ud.get("is_favorite")),
        is_to_read=bool(ud.get("is_to_read")),
        rating=ud.get("rating", 0),
        reading_position=ud.get("reading_position", ""),
        last_read_at=ud.get("last_read_at"),
        fertig_am=ud.get("fertig_am"),
        categories=cats,
        sammlung=sammlung,
        authors=authors,
        privat=bool(await sichtbar.private(p.id, [book_id])),
        dateien=await formate.dateien(book_id),
        material=(await material_dienst.anzahlen([book_id])).get(book_id, 0),
        original=await original_pruefung.hinweis(book_id),
    )


@router.patch("/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: Nr, update: BookUpdate, p: Profil = Depends(braucht("bearbeiten"))
):
    """Aktualisiert Metadaten eines Buches."""
    await vorhanden.buch(book_id)
    updates = {k: v for k, v in update.model_dump(exclude_unset=True).items() if v is not None or k in LEERBAR}
    if not updates:
        raise HTTPException(status_code=400, detail="Keine Felder zum Aktualisieren")
    if "sammlung_id" in updates:
        await vorhanden.eintrag("collections", updates["sammlung_id"], "Sammlung nicht gefunden", "id")

    zuweisungen = [f"{k} = ?" for k in updates]
    if updates.keys() - DARSTELLUNG:                 # die Wahl der Darstellung allein bearbeitet keine Angabe
        zuweisungen += ["manuell_bearbeitet = 1", "updated_at = datetime('now')"]
    if updates.keys() & FELDER_DER_EINORDNUNG:
        zuweisungen.append(f"einordnung = '{VON_HAND}', einordnung_grund = ''")
    if updates.keys() & FELDER_DES_ALTERS:
        zuweisungen.append(f"alter_quelle = '{VON_HAND}'")            # überschrieben: die Quelle zählt nicht mehr (BF-78)
    await db.execute(f"UPDATE books SET {', '.join(zuweisungen)} WHERE id = ?", (*updates.values(), book_id))

    if "author" in updates:
        await autoren_verknuepfen(book_id, updates["author"])
    await db.commit()                 # der Suchindex zieht Titel und Autor selbst nach (core/suchindex.py)
    if "title" in updates:
        ansagelauf.anstossen()        # der Titel als Ansage für die Kinder, die das Buch sehen (BF-78)
    return await get_book(book_id, p)


@router.get("/{book_id}/loeschfolgen", response_model=buch_loeschen.Folgen)
async def loeschfolgen(book_id: Nr, _p: Profil = Depends(braucht("loeschen"))):
    """Was verloren geht, wenn das Buch gelöscht wird (BF-60): für die Rückfrage vor dem Löschen."""
    f = await buch_loeschen.folgen(book_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")
    f.material = [buch_loeschen.Datei(pfad=m.pfad if m.ort == "kellerwolke" else m.name, groesse=m.groesse, papierkorb=m.ort == "kellerwolke")
                  for m in await material_dienst.des_buchs(book_id)]          # das Material geht mit dem Buch (BF-81)
    return f


@router.delete("/{book_id}")
async def delete_book(book_id: Nr, _p: Profil = Depends(braucht("loeschen"))):
    """Löscht ein Buch mit allem, was an ihm hängt; die Datei geht in den Papierkorb der Kellerwolke (BF-60)."""
    try:
        if not await buch_loeschen.loeschen(book_id):
            raise HTTPException(status_code=404, detail="Buch nicht gefunden")
    except buch_loeschen.NichtGeloescht as f:
        raise HTTPException(status_code=502, detail=f"Nicht gelöscht, das Buch bleibt: {f}") from f
    return {"geloescht": True, "id": book_id}


class BulkAction(BaseModel):
    """Massenbearbeitung für mehrere Bücher."""
    book_ids: list[Nr] = Field(max_length=AUSWAHL_HOECHSTENS)
    aktion: Literal["loeschen", "kategorie_zuweisen", "kategorie_entfernen", "sammlung_zuweisen", "sammlung_entfernen", "typ_setzen",
                    "favorit", "zu_lesen"]
    wert: Nr | bool | Annotated[str, StringConstraints(max_length=50)] | None = None  # Nummer von Regal oder Sammlung, Typ, true/false


async def _nummer(wert: object, tabelle: str, meldung: str) -> int:
    """Die Nummer eines Regals oder einer Sammlung für eine Sammelaktion; es muss sie geben."""
    if isinstance(wert, bool) or not isinstance(wert, int | str) or not str(wert).isdigit() or not 0 < int(wert) <= GROESSTE_ZAHL:
        raise HTTPException(status_code=422, detail="Wert: keine Nummer")
    return (await vorhanden.eintrag(tabelle, int(wert), meldung, "id"))["id"]


def _typ(wert: object) -> str:
    try:
        return typ_pruefen(str(wert) if wert else "")
    except ValueError as f:
        raise HTTPException(status_code=422, detail=f"Wert: {f}") from None


# Was eine Sammelaktion braucht (stufen.json); Favorit und Lesesofa betreffen nur das eigene Profil
FAEHIGKEIT_DER_AKTION = {"loeschen": "loeschen", "favorit": "favoriten", "zu_lesen": "sammeln"}
# Aktionen, bei denen ein fehlendes Buch 404 ist (die übrigen übergehen es); ein unsichtbares gilt als fehlend
MUSS_ES_GEBEN = frozenset({"favorit", "zu_lesen", "kategorie_zuweisen"})


@router.post("/bulk")
async def bulk_action(
    action: BulkAction,
    p: Profil = Depends(profil),
):
    """Führt eine Massenbearbeitung für mehrere Bücher durch; Bücher, die das Profil nicht sieht, gibt es dabei nicht."""
    if not action.book_ids:
        raise HTTPException(status_code=400, detail="Keine Bücher ausgewählt")
    faehigkeit = FAEHIGKEIT_DER_AKTION.get(action.aktion, "bearbeiten")
    if not rechte.darf(p, faehigkeit):
        raise HTTPException(status_code=403, detail=f"Das darf dieses Profil nicht: {stufenbuch().faehigkeiten[faehigkeit]}")
    sichtbare = await sichtbar.nur_sichtbare(Sicht.von(p), action.book_ids)
    if len(sichtbare) != len(action.book_ids) and action.aktion in MUSS_ES_GEBEN:
        raise HTTPException(status_code=404, detail=BEZUG_FEHLT)        # wie die Datenbank für ein Buch, das es nicht gibt
    action.book_ids = sichtbare

    betroffen = 0

    if action.aktion == "loeschen":
        for bid in action.book_ids:
            betroffen += (await db.execute("DELETE FROM books WHERE id = ?", (bid,))).rowcount
        await db.commit()

    elif action.aktion == "kategorie_zuweisen":
        if action.wert is None:
            raise HTTPException(status_code=400, detail="Kategorie-ID fehlt")
        kat_id = await _nummer(action.wert, "categories", "Regal nicht gefunden")
        for bid in action.book_ids:
            betroffen += (await db.execute(
                "INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'manuell')",
                (bid, kat_id),
            )).rowcount
        await db.commit()

    elif action.aktion == "kategorie_entfernen":
        if action.wert is None:
            raise HTTPException(status_code=400, detail="Kategorie-ID fehlt")
        kat_id = await _nummer(action.wert, "categories", "Regal nicht gefunden")
        for bid in action.book_ids:
            betroffen += (await db.execute(
                "DELETE FROM book_categories WHERE book_id = ? AND category_id = ?", (bid, kat_id),
            )).rowcount
        await db.commit()

    elif action.aktion == "sammlung_zuweisen":
        if action.wert is None:
            raise HTTPException(status_code=400, detail="Sammlungs-ID fehlt")
        samml_id = await _nummer(action.wert, "collections", "Sammlung nicht gefunden")
        betroffen = await sammlungen.anhaengen(samml_id, action.book_ids)

    elif action.aktion == "sammlung_entfernen":
        betroffen = await sammlungen.entfernen(action.book_ids)

    elif action.aktion == "typ_setzen":
        typ_wert = _typ(action.wert)
        for bid in action.book_ids:
            betroffen += (await db.execute(
                f"UPDATE books SET typ = ?, einordnung = '{VON_HAND}', einordnung_grund = '' WHERE id = ?",
                (typ_wert, bid),
            )).rowcount
        await db.commit()

    elif action.aktion == "favorit":
        fav = 1 if action.wert in (True, "true", 1) else 0
        for bid in action.book_ids:
            betroffen += (await db.execute(
                """INSERT INTO user_book_data (profil_id, book_id, is_favorite)
                   VALUES (?, ?, ?)
                   ON CONFLICT(profil_id, book_id) DO UPDATE SET is_favorite = ?""",
                (p.id, bid, fav, fav),
            )).rowcount
        await db.commit()

    elif action.aktion == "zu_lesen":
        val = 1 if action.wert in (True, "true", 1) else 0
        for bid in action.book_ids:
            betroffen += (await db.execute(
                """INSERT INTO user_book_data (profil_id, book_id, is_to_read)
                   VALUES (?, ?, ?)
                   ON CONFLICT(profil_id, book_id) DO UPDATE SET is_to_read = ?""",
                (p.id, bid, val, val),
            )).rowcount
        await db.commit()


    return {"betroffen": betroffen, "aktion": action.aktion}


@router.delete("/kategorie/{category_id}/buecher")
async def delete_books_by_category(
    category_id: Nr,
    datei_loeschen: bool = Query(False, description="Auch Dateien im Speicher löschen"),
    p: Profil = Depends(braucht("loeschen")),
):
    """Löscht alle Bücher einer Kategorie, die das Profil sieht.

    Entfernt die Bücher aus der DB. Optional werden auch die
    Dateien im Hash-Speicher gelöscht.
    """
    # Bücher in dieser Kategorie finden
    bedingung, werte = Sicht.von(p).bedingung("b.id")
    rows = await db.fetch_all(
        f"SELECT b.id, b.hash FROM books b JOIN book_categories bc ON bc.book_id = b.id WHERE bc.category_id = ? AND {bedingung}",
        (category_id, *werte),
    )
    if not rows:
        return {"geloescht": 0, "kategorie_id": category_id}

    if datei_loeschen:
        from backend.app.services.storage import delete_stored_file

    for row in rows:
        await db.execute("DELETE FROM books WHERE id = ?", (row["id"],))
        if datei_loeschen:
            try:
                delete_stored_file(row["hash"])
            except Exception:
                pass
    await db.commit()

    return {"geloescht": len(rows), "kategorie_id": category_id}


def _platzhalter_cover_svg(title: str, file_format: str) -> str:
    """Erzeugt ein schlichtes Platzhalter-Cover als SVG (immer verfügbar)."""
    titel = (title or "Ohne Titel").strip() or "Ohne Titel"
    fmt = (file_format or "").upper()
    farbton = sum(ord(c) for c in titel) % 360
    # Titel grob auf Zeilen umbrechen (max. 7 Zeilen)
    zeilen: list[str] = []
    akt = ""
    for wort in titel.split():
        if akt and len(akt) + len(wort) + 1 > 16:
            zeilen.append(akt)
            akt = wort
        else:
            akt = (akt + " " + wort).strip()
        if len(zeilen) >= 7:
            break
    if akt and len(zeilen) < 7:
        zeilen.append(akt)
    if not zeilen:
        zeilen = ["Ohne Titel"]
    start_y = 300 - (len(zeilen) - 1) * 21
    tspans = "".join(
        f'<tspan x="200" y="{start_y + i * 42}">{escape(z)}</tspan>'
        for i, z in enumerate(zeilen)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="600" '
        'viewBox="0 0 400 600" preserveAspectRatio="xMidYMid slice">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="hsl({farbton},42%,32%)"/>'
        f'<stop offset="1" stop-color="hsl({(farbton + 40) % 360},42%,20%)"/>'
        '</linearGradient></defs>'
        '<rect width="400" height="600" fill="url(#g)"/>'
        '<rect x="14" y="14" width="372" height="572" fill="none" '
        'stroke="rgba(255,255,255,0.14)" stroke-width="2" rx="6"/>'
        '<text fill="rgba(255,255,255,0.92)" font-family="Georgia,serif" '
        f'font-size="30" font-weight="700" text-anchor="middle">{tspans}</text>'
        '<text x="200" y="565" fill="rgba(255,255,255,0.5)" '
        'font-family="sans-serif" font-size="18" letter-spacing="3" '
        f'text-anchor="middle">{escape(fmt)}</text>'
        '</svg>'
    )


def _generate_cover_sync(file_hash: str, file_format: str) -> bytes | None:
    """Deckblatt aus der Quelldatei. CPU-lastig -> wird im Threadpool aufgerufen."""
    original = get_original_file(file_hash)
    return deckblatt.von_datei(original, file_format) if original else None


@router.get("/{book_id}/cover")
async def get_cover(book_id: Nr, _token: str = Depends(verify_token_inhalt)):
    """Liefert das Cover eines Buches und gibt NIE 404 zurück.

    Reihenfolge: vorhandenes cover.jpg -> sonst aus der Quelldatei erzeugen
    (erste PDF-Seite bzw. eingebettetes EPUB-Cover) und cachen -> sonst ein
    Platzhalter-SVG. So entstehen keine Konsolen-/API-Fehler.
    """
    book = await db.fetch_one(
        "SELECT hash, title, file_format FROM books WHERE id = ?", (book_id,)
    )
    if not book:
        return Response(
            content=_platzhalter_cover_svg("", ""),
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-store"},
        )

    cover_path = get_sidecar_path(book["hash"], "cover.jpg")
    if cover_path.exists():
        # die Adresse trägt den Stand des Umschlags (cover_stand), darum darf der Browser ihn behalten
        return FileResponse(cover_path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=604800"})

    # Cover fehlt -> aus der Quelldatei erzeugen (CPU-lastig, daher im Thread)
    try:
        data = await asyncio.to_thread(
            _generate_cover_sync, book["hash"], book["file_format"]
        )
    except Exception:
        data = None

    if data:
        try:
            save_cover(book["hash"], data)
            await db.execute("UPDATE books SET cover_path = 'cover.jpg' WHERE id = ? AND COALESCE(cover_path, '') = ''", (book_id,))
            await db.commit()
        except OSError as f:
            logging.getLogger("buecherfreunde.api.books").warning("Umschlag nicht gemerkt: %s", f)
        return Response(content=data, media_type="image/jpeg")

    # Letzter Ausweg: Platzhalter (kein 404)
    return Response(
        content=_platzhalter_cover_svg(book["title"], book["file_format"]),
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


async def _deckblatt_der_datei(book_id: int) -> tuple[dict, bytes]:
    """Das Deckblatt aus der Datei des Buchs, noch nicht gespeichert."""
    book = await db.fetch_one("SELECT id, hash, file_format FROM books WHERE id = ?", (book_id,))
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")
    original = await asyncio.to_thread(get_original_file, book["hash"])
    if not original or not original.exists():
        raise HTTPException(status_code=404, detail=FEHLT)
    cover_data = await asyncio.to_thread(deckblatt.von_datei, original, book["file_format"])
    if not cover_data:
        raise HTTPException(status_code=422, detail="In der Datei ist kein Deckblatt zu finden")
    return book, cover_data


@router.get("/{book_id}/cover/aus-datei")
async def cover_aus_datei(book_id: Nr, _p: Profil = Depends(braucht("bearbeiten"))):
    """Das Deckblatt aus der Datei als Bild, ohne es zu speichern: beim Bearbeiten kommt es ins Formular, gespeichert wird es erst
    mit Speichern über `cover/neu-extrahieren` (BF-112)."""
    _book, cover_data = await _deckblatt_der_datei(book_id)
    return Response(content=cover_data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/{book_id}/cover/neu-extrahieren")
async def re_extract_cover(book_id: Nr, _p: Profil = Depends(braucht("bearbeiten"))):
    """Extrahiert das Cover neu aus der Buchdatei und überschreibt das bestehende."""
    book, cover_data = await _deckblatt_der_datei(book_id)
    save_cover(book["hash"], cover_data)
    await db.execute(
        "UPDATE books SET cover_path = 'cover.jpg', updated_at = datetime('now') WHERE id = ?",
        (book_id,),
    )
    await db.commit()

    return {"gespeichert": True, "groesse": len(cover_data)}


@router.get("/{book_id}/file")
async def get_file(book_id: Nr, request: Request, herunterladen: bool = Query(False, description="Als Anhang (Herunterladen) statt zum Ansehen im Browser"),
                   format: str | None = Query(None, pattern=r"^[a-z0-9]{1,10}$", description="Ein weiteres Format des Buchs (BF-80); ohne: das Original"),
                   _token: str = Depends(verify_token_inhalt)):
    """Streamt die Buchdatei (mit Range-Request-Unterstützung); das Lesen wählt das Format, ohne Wahl das Original."""
    if not await db.fetch_one("SELECT 1 AS da FROM books WHERE id = ?", (book_id,)):
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")
    datei = await formate.zum_lesen(book_id, format)
    if datei is None:
        raise HTTPException(status_code=404, detail=f"Dieses Buch gibt es nicht als {format.upper() if format else 'Datei'}")
    book = {"hash": datei["hash"], "file_name": datei["name"], "file_format": datei["format"]}

    media_types = {
        "pdf": "application/pdf",
        "epub": "application/epub+zip",
        "mobi": "application/x-mobipocket-ebook",
        "txt": "text/plain; charset=utf-8",
        "md": "text/markdown; charset=utf-8",
    }
    media_type = media_types.get(book["file_format"], "application/octet-stream")

    return await original_antwort(request, book["hash"], media_type, book["file_name"], herunterladen)


@router.post("/rescan")
async def rescan_books(
    typen: str = Query("cover,isbn", description="Kommagetrennt: cover,isbn,metadaten,volltext"),
    kategorie: Index | None = Query(None, description="Nur Bücher dieser Kategorie (0=ohne Kategorie)"),
    manuell_einschliessen: bool = Query(False, description="Auch manuell bearbeitete Buecher scannen"),
    _p: Profil = Depends(braucht("einstellungen")),
):
    """Startet einen selektiven Rescan."""
    from backend.app.services import rescan_service
    typ_liste = [t.strip() for t in typen.split(",") if t.strip()]
    return await rescan_service.starte_rescan(typ_liste, kategorie, manuell_einschliessen)


@router.get("/rescan/status")
async def rescan_get_status(_p: Profil = Depends(braucht("einstellungen"))):
    """Gibt den aktuellen Rescan-Status zurück."""
    from backend.app.services import rescan_service
    return rescan_service.status


@router.post("/rescan/abbrechen")
async def rescan_cancel(_p: Profil = Depends(braucht("einstellungen"))):
    """Bricht den laufenden Rescan ab."""
    from backend.app.services import rescan_service
    return rescan_service.abbrechen()


@router.get("/rescan/vorschau")
async def rescan_vorschau(
    typen: str = Query("cover,isbn", description="Kommagetrennt: cover,isbn,metadaten,volltext"),
    kategorie: Index | None = Query(None, description="Nur Bücher dieser Kategorie (0=ohne Kategorie)"),
    manuell_einschliessen: bool = Query(False),
    _p: Profil = Depends(braucht("einstellungen")),
):
    """Vorschau: wie viele Buecher wuerden gescannt werden."""
    from backend.app.services import rescan_service
    typ_liste = [t.strip() for t in typen.split(",") if t.strip()]
    return await rescan_service.vorschau(typ_liste, kategorie, manuell_einschliessen)


@router.get("/rescan/kategorien")
async def rescan_kategorien(
    typen: str = Query("cover,isbn", description="Kommagetrennt: cover,isbn,metadaten,volltext"),
    manuell_einschliessen: bool = Query(False),
    _p: Profil = Depends(braucht("einstellungen")),
):
    """Zeigt betroffene Buecher pro Kategorie."""
    from backend.app.services import rescan_service
    typ_liste = [t.strip() for t in typen.split(",") if t.strip()]
    return await rescan_service.vorschau_kategorien(typ_liste, manuell_einschliessen)


def _baustein(b: Baustein) -> TextBaustein:
    if b.code is not None:
        c = b.code
        return TextBaustein(art="code", titel=b.titel, zeilen=c.zeilen, sprache=c.sprache, kennung=c.kennung, teil=c.teil, teile=c.teile)
    verhaeltnis = round(b.rechteck.width / b.rechteck.height, 4) if b.rechteck and b.rechteck.height else None
    return TextBaustein(art=b.art, text=b.text, titel=b.titel, inhalt=[_baustein(t) for t in b.inhalt],
                        bild=b.bild, verhaeltnis=verhaeltnis, breite_em=b.breite_em)


async def _codeteile(book_id: int) -> dict[int, list[Codeteil]]:
    """Je Dateiseite die Teile der erkannten Codestellen; leer, solange das Buch nicht erkannt ist (es kommt dann dran)."""
    try:
        _stand, begleiter = await codestellen.stellen(book_id)
    except KeyError:
        return {}
    je_seite: dict[int, list[Codeteil]] = {}
    for s in begleiter.stellen if begleiter and begleiter.format == "pdf" else []:
        for i, (t, zeilen) in enumerate(zip(s.teile, s.zeilen_der_teile())):
            if t.seite is not None and t.rechteck:
                je_seite.setdefault(t.seite, []).append(Codeteil(fitz.Rect(t.rechteck), s.kennung, s.sprache, s.titel, i, len(s.teile), zeilen))
    return je_seite


async def _pdf_zum_lesen(book_id: int) -> tuple[dict, Path]:
    book = await db.fetch_one("SELECT hash, page_count, file_format FROM books WHERE id = ?", (book_id,))
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")
    if (book["file_format"] or "").lower() != "pdf":
        raise HTTPException(status_code=422, detail="Die Textansicht gibt es nur für PDF")
    pfad = await asyncio.to_thread(get_original_file, book["hash"])
    if pfad is None:
        raise HTTPException(status_code=404, detail=FEHLT)
    return dict(book), pfad


@router.get("/{book_id}/textseiten", response_model=TextSeitenAntwort)
async def text_seiten(
    book_id: Nr,
    ab: int = Query(1, ge=1, le=SEITEN_HOECHSTENS, description="Erste Dateiseite"),
    anzahl: int = Query(6, ge=1, le=30),
    _p: Profil = Depends(profil),
):
    """Seiten eines PDF als Bausteine für die Textansicht: umfließende Absätze, Überschriften, Kästen und Abbildungen
    (über den Bild-Endpunkt), ohne Kopf- und Fußzeilen. Je Seite, woher ihr Text kommt; "wartet": die Texterkennung liest
    sie noch (BF-109)."""
    book, pfad = await _pdf_zum_lesen(book_id)
    erkennungen = await asyncio.to_thread(erkennungsablage.lesen, book["hash"])
    gesamt, seiten = await asyncio.to_thread(seiten_lesen, pfad, ab, anzahl, await _codeteile(book_id), erkennungen)
    _texte, gedruckt = await asyncio.to_thread(buch_seiten, book["hash"], book["file_format"], book["page_count"])
    wartend = await texterkennung.wartende(book_id, [s.nr for s in seiten if s.schicht == "ohne"])
    return TextSeitenAntwort(
        gesamt=gesamt,
        seiten=[TextSeite(nr=s.nr, gedruckt=gedruckt[s.nr - 1] if s.nr <= len(gedruckt) else "",
                          bausteine=[_baustein(b) for b in s.bausteine], schicht="wartet" if s.nr in wartend else s.schicht)
                for s in seiten],
    )


@router.get("/{book_id}/textseiten/{seite}/bild/{nr}")
async def text_seiten_bild(book_id: Nr, seite: Nr, nr: Index, _token: str = Depends(verify_token_inhalt)):
    """Abbildung `nr` einer Seite der Textansicht als PNG (Ausschnitt der Originalseite)."""
    book, pfad = await _pdf_zum_lesen(book_id)
    erkennungen = await asyncio.to_thread(erkennungsablage.lesen, book["hash"])
    png = await asyncio.to_thread(abbildung_png, pfad, seite, nr, codeteile=await _codeteile(book_id), erkennungen=erkennungen)
    if png is None:
        raise HTTPException(status_code=404, detail="Abbildung nicht gefunden")
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=604800"})


@router.get("/{book_id}/volltext-suche")
async def fulltext_search_book(
    book_id: Nr,
    q: str = Query(..., min_length=1, description="Suchbegriff"),
    limit: int = Query(500, ge=1, le=5000),
    ganzes_wort: bool = Query(False, description="Nur ganze Woerter"),
    gross_klein: bool = Query(False, description="Gross-/Kleinschreibung beachten"),
    regex: bool = Query(False, description="Regulaerer Ausdruck"),
    _p: Profil = Depends(braucht("suche")),
):
    """Durchsucht den Volltext eines Buchs: Treffer mit Seite, Ausschnitt und Lage. Gesucht wird nie in der
    Ereignisschleife; ein regulärer Ausdruck läuft in einem eigenen Prozess mit Zeitgrenze (`SUCHE_AUSDRUCK_S`). Geht es
    nicht (ungültiger Ausdruck, Zeit um), sagt `grund` warum."""
    book = await db.fetch_one("SELECT id, hash, page_count, file_format FROM books WHERE id = ?", (book_id,))
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")
    seiten, _gedruckt = await asyncio.to_thread(buch_seiten, book["hash"], book["file_format"], book["page_count"])
    if not seiten:
        return {"treffer": [], "gesamt": 0, "seiten_gesamt": 0, "suchbegriff": q, "grund": ""}
    return await buchsuche.suche(seiten, q, limit, ganzes_wort, gross_klein, regex, settings.suche_ausdruck_s)
