"""Hilfen für die Tests des Katalogs (BF-69): erfundene Werke mit Regalen und ein kleiner eigener Katalog."""

import itertools

from tests.api.conftest import buch_erstellen

_nummern = itertools.count(1)

# Ein kleiner Katalog: zwei Bereiche für Bücher, einer für Dokumente; alles erfunden
KLEIN = {"fassung": 1, "bereiche": [
    {"schluessel": "romane", "name": "Romane", "zeichen": "feather", "farbe": "#8e44ad", "arten": [""], "kategorien": [
        {"schluessel": "romane/krimi", "name": "Krimi", "zeichen": "magnifying-glass", "ki_beschreibung": "Kriminalromane",
         "regeln": {"schlagworte": ["Kriminalroman", "Crime fiction"], "titelwoerter": ["Kommissar"]}},
        {"schluessel": "romane/fantasy", "name": "Fantasy", "zeichen": "dragon", "ki_beschreibung": "Drachen und Magie",
         "regeln": {"schlagworte": ["Fantasy"]}}]},
    {"schluessel": "technik", "name": "Technik", "zeichen": "microchip", "farbe": "#2f6fb3", "kategorien": [
        {"schluessel": "technik/informatik", "name": "Informatik", "zeichen": "code", "ki_beschreibung": "Programmieren",
         "regeln": {"sachgruppen": ["004"], "titelwoerter": ["Python"], "verlage": ["Bitverlag"]}}]},
    {"schluessel": "besonderes", "name": "Besonderes", "zeichen": "file-lines", "farbe": "#5f6673", "arten": ["dokument", "heft"],
     "kategorien": [{"schluessel": "besonderes/belege", "name": "Belege", "zeichen": "receipt", "ki_beschreibung": "Rechnungen",
                     "regeln": {"titelwoerter": ["Rechnung", "Kommissar"]}}]},
]}


async def regal(test_db, name: str, spezial: bool = False) -> int:
    slug = name.lower().replace(" ", "-")
    await test_db.execute("INSERT OR IGNORE INTO categories (name, slug, spezial) VALUES (?, ?, ?)", (name, slug, int(spezial)))
    z = await test_db.fetch_one("SELECT id FROM categories WHERE slug = ?", (slug,))
    await test_db.commit()
    return z["id"]


async def werk(test_db, titel: str, *, regale: tuple[str, ...] = (), typ: str = "", verlag: str = "", autor: str = "Erna Beispiel",
               beschreibung: str = "") -> int:
    """Ein erfundenes Werk; `regale` sind Namen alter Regale (sie zählen als Schlagworte)."""
    b = await buch_erstellen(test_db, hash=f"katalog-{next(_nummern)}", title=titel, author=autor, publisher=verlag, description=beschreibung)
    await test_db.execute("UPDATE books SET typ = ? WHERE id = ?", (typ, b))
    for name in regale:
        await test_db.execute("INSERT INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'metadaten')", (b, await regal(test_db, name)))
    await test_db.commit()
    return b


async def katalog_annehmen(client, katalog: dict | None = None) -> dict:
    """Einen Katalog als Entwurf laden und annehmen; gibt GET /api/katalog."""
    r = await client.post("/api/katalog/datei", json=katalog or KLEIN)
    assert r.status_code == 200, r.text
    r = await client.post("/api/katalog/entwurf/annehmen")
    assert r.status_code == 200, r.text
    return r.json()


def nummern(katalog: dict) -> dict[str, int]:
    """Je Schlüssel die Nummer im gültigen Katalog."""
    aus = {}
    for b in katalog["bereiche"]:
        aus[b["schluessel"]] = b["id"]
        aus |= {k["schluessel"]: k["id"] for k in b["kategorien"]}
    return aus
