"""Ein ausgewertetes Buch eintragen: Angaben in den Bestand, Volltext und Umschlag an ihre Orte, Begleiter neben das Original
in der Kellerwolke (Form des Auszugs in ablage/auszug.py). Ein Weg für alle Quellen (Hochladen, Ordner, gemeinfreie Bücher)."""

from __future__ import annotations

import logging
import re

from backend.app.ablage import auszug
from backend.app.ablage.namen import ablageort
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.annahme.auswertung import Ergebnis
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.core.suchindex import SUCHTEXT_ZEICHEN
from backend.app.services.autorennamen import zerlegen
from backend.app.services.storage import get_storage_path, save_cover, save_fulltext, save_metadata

logger = logging.getLogger("buecherfreunde.eintragen")


async def autoren_verknuepfen(buch: int, autor: str) -> None:
    """Autoren eines Buchs aus dem Autorenfeld: fehlende anlegen, Verknüpfung genau so wie das Feld."""
    async with db.einheit():
        await db.execute("DELETE FROM book_authors WHERE book_id = ?", (buch,))
        namen = [n for n in zerlegen(autor) if len(n) > 1]
        for stelle, name in enumerate(namen):
            slug = re.sub(r"[-\s]+", "-", re.sub(r"[^\w\s-]", "", name.lower())).strip("-")
            if not slug:
                continue
            await db.execute("INSERT OR IGNORE INTO authors (name, slug) VALUES (?, ?)", (name, slug))
            a = await db.fetch_one("SELECT id FROM authors WHERE slug = ?", (slug,))
            await db.execute("INSERT OR IGNORE INTO book_authors (book_id, author_id, sort_order) VALUES (?, ?, ?)", (buch, a["id"], stelle))


async def eintragen(file_hash: str, dateiname: str, groesse: int, e: Ergebnis) -> int:
    """Buch anlegen; liefert seine Nummer. Ist der Inhalt schon da, die vorhandene."""
    da = await db.fetch_one("SELECT id FROM books WHERE hash = ?", (file_hash,))
    if da:
        return da["id"]
    endung = dateiname.rsplit(".", 1)[-1].lower() if "." in dateiname else ""
    save_metadata(file_hash, {"titel": e.title, "autor": e.author, "isbn": e.isbn, "verlag": e.publisher, "jahr": e.year,
                              "sprache": e.language, "beschreibung": e.description, "seiten": e.page_count})
    if e.fulltext:
        save_fulltext(file_hash, e.fulltext)
    if e.cover_data:
        save_cover(file_hash, e.cover_data)
    async with db.einheit():                                # Buch, Autoren und Regal gelten zusammen oder gar nicht
        c = await db.execute(
            "INSERT INTO books (hash, title, author, isbn, publisher, year, language, description, file_format, file_size, file_name, "
            "storage_path, cover_path, page_count, fts_content, alter_von, alter_bis, alter_quelle) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (file_hash, e.title, e.author or "", e.isbn or "", e.publisher or "", e.year, e.language or "", e.description or "", endung, groesse,
             dateiname, str(get_storage_path(file_hash)), "cover.jpg" if e.cover_data else "", e.page_count, e.fulltext[:SUCHTEXT_ZEICHEN],
             e.alter_von, e.alter_bis, e.alter_quelle))
        buch = c.lastrowid
        await db.execute("UPDATE books SET fts_content = '' WHERE id = ?", (buch,))      # steht im Suchindex
        await autoren_verknuepfen(buch, e.author)
        if not e.isbn:
            await db.execute("INSERT OR IGNORE INTO categories (name, slug, description) VALUES ('Ungeordnet', 'ungeordnet', 'Bücher ohne ISBN oder Zuordnung')")
            k = await db.fetch_one("SELECT id FROM categories WHERE slug = 'ungeordnet'")
            await db.execute("INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'import')", (buch, k["id"]))
    return buch


async def ablegen(buch: int, knoten: str) -> None:
    """Das Original an seinen endgültigen Ort in der Kellerwolke, Felder und Begleiter dazu, Eintrag im Bestand."""
    z = await db.fetch_one("SELECT hash, title, author, file_name, file_format, file_size FROM books WHERE id = ?", (buch,))
    fach, name = ablageort(buch, z["title"], z["author"], z["file_name"], z["file_format"])
    ordner = await wolke.ordner(f"{settings.ablage_ordner}/Bücher/{fach}")
    try:
        k = await wolke.umziehen(knoten, ordner["id"], name)
    except WolkeFehler as f:
        if f.status != 409:
            raise
        k = await wolke.knoten(knoten)                      # liegt schon dort (Wiederholung nach Abbruch)
    await wolke.felder(knoten, {"buch": buch, "titel": z["title"], "autor": z["author"]})
    begleiter = await wolke.auszug_schreiben(knoten, await auszug.bauen(buch, z["hash"]))
    await db.execute("INSERT OR REPLACE INTO ablage_datei(hash, knoten, name, pfad, groesse, begleiter) VALUES (?, ?, ?, ?, ?, ?)",
                     (z["hash"], knoten, k["name"], k.get("pfad", ""), z["file_size"], begleiter))
    await db.commit()
