"""Alte Kategorien (BF-69): Regale aus Importen (`art` regal, nicht in der Leiste, nicht "Ungeordnet") gehen im Katalog
auf. Je altem Regal schlagen Regeln eine Kategorie vor (gleicher Name, oder der Name trifft ihre Regeln als Schlagwort
oder Sachgruppe), sonst die KI aus dem Lauf des Einordnens (`katalog_alt_vorschlag`), sonst "Schlagwort am Buch".

Übernehmen setzt die Bücher in die Kategorie (Quelle manuell) oder vergibt den Namen als Etikett an jedes Buch. Das alte
Regal bleibt dabei stehen; entfernt wird es erst nach einer Folgenvorschau und ausdrücklich, nie von selbst."""

from __future__ import annotations

from collections.abc import Sequence

from backend.app.core.database import db
from backend.app.katalog import kategorien, merkmale
from backend.app.katalog.modelle import AltesRegal, AltLoeschfolgen, AltVorschlag, Einordnungskategorie, Uebernahmeziel
from backend.app.katalog.regeln import Pruefer, sicherheit, suchtext
from backend.app.models.grenzen import ETIKETT

ALT = "c.art = 'regal' AND COALESCE(c.spezial, 0) = 0 AND c.slug != 'ungeordnet'"
ETIKETT_FARBE = "#4FC3F7"
REGAL_FEHLT = "Altes Regal nicht gefunden"
TITEL_IN_DEN_FOLGEN = 10
NICHT_GEPRUEFT = "Keine Regel passt; die KI hat das Regal noch nicht gesehen (Einordnen starten)"


class Fehlt(LookupError):
    pass


def regelvorschlag(name: str, pruefer: Sequence[tuple[Einordnungskategorie, Pruefer]]) -> AltVorschlag | None:
    """Gleicher Name zuerst, sonst die Kategorie, deren Regeln den Namen am sichersten treffen."""
    for k, _ in pruefer:
        if k.name.casefold() == name.strip().casefold():
            return AltVorschlag(art="kategorie", kategorie_id=k.id, grund=f"Gleicher Name wie die Kategorie {k.name}")
    t = suchtext("", "", [name], merkmale.sachgruppen_aus([name]))
    besten = max(((sicherheit(tr), k, tr) for k, p in pruefer if (tr := p.treffer(t))), key=lambda x: x[0], default=None)
    if besten is None:
        return None
    _, k, tr = besten
    return AltVorschlag(art="kategorie", kategorie_id=k.id, grund=f"{tr[0].satz} der Kategorie {k.name}")


async def _alte() -> list[dict]:
    return await db.fetch_all(f"""SELECT c.id, c.name, c.color, (SELECT COUNT(*) FROM book_categories x WHERE x.category_id = c.id) AS anzahl
                                  FROM categories c WHERE {ALT} ORDER BY c.name COLLATE NOCASE""")


async def _ki_vorschlaege() -> dict[int, AltVorschlag]:
    zeilen = await db.fetch_all("SELECT regal_id, kategorie_id, grund FROM katalog_alt_vorschlag")
    return {z["regal_id"]: AltVorschlag(art="kategorie" if z["kategorie_id"] else "schlagwort", kategorie_id=z["kategorie_id"],
                                        grund=f"Die KI: {z['grund']}" if z["grund"] else "Die KI schlägt das vor") for z in zeilen}


async def pruefer() -> list[tuple[Einordnungskategorie, Pruefer]]:
    return [(k, Pruefer(k.regeln)) for k in await kategorien.zum_einordnen()]


async def liste() -> list[AltesRegal]:
    p, ki = await pruefer(), await _ki_vorschlaege()
    return [AltesRegal(id=z["id"], name=z["name"], anzahl=z["anzahl"],
                       vorschlag=regelvorschlag(z["name"], p) or ki.get(z["id"]) or AltVorschlag(art="schlagwort", grund=NICHT_GEPRUEFT))
            for z in await _alte()]


async def ohne_regelvorschlag(p: Sequence[tuple[Einordnungskategorie, Pruefer]]) -> list[tuple[int, str]]:
    """Die alten Regale, zu denen keine Regel passt: die fragt der Lauf die KI."""
    return [(z["id"], z["name"]) for z in await _alte() if regelvorschlag(z["name"], p) is None]


async def ki_merken(je_regal: dict[int, tuple[int | None, str]]) -> None:
    """Was die KI je Regal vorschlägt: eine Kategorie oder keine (Schlagwort am Buch), mit ihrem Satz."""
    async with db.einheit():
        for regal, (kategorie, grund) in je_regal.items():
            await db.execute("""INSERT INTO katalog_alt_vorschlag (regal_id, kategorie_id, grund) VALUES (?, ?, ?)
                                ON CONFLICT (regal_id) DO UPDATE SET kategorie_id = excluded.kategorie_id, grund = excluded.grund,
                                    geprueft_am = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')""", (regal, kategorie, grund))


async def _regale(ids: Sequence[int]) -> list[dict]:
    ids = list(dict.fromkeys(ids))
    zeilen = await db.fetch_all(f"SELECT c.id, c.name, c.color FROM categories c WHERE {ALT} AND c.id IN ({','.join('?' * len(ids))})",
                                tuple(ids))
    if fehlen := sorted(set(ids) - {z["id"] for z in zeilen}):
        raise Fehlt(f"{REGAL_FEHLT}: {', '.join(map(str, fehlen))}")
    return zeilen


async def uebernehmen(ids: Sequence[int], ziel: Uebernahmeziel, profil_id: str) -> int:
    """Die Bücher der Regale in die Kategorie, oder der Name jedes Regals als Etikett an seine Bücher (Etiketten sind
    persönlich: die des übernehmenden Profils, BF-78); gibt zurück, wie viele Bücher es betraf."""
    regale = await _regale(ids)
    if ziel.kategorie_id is not None:
        await kategorien.kategorie(ziel.kategorie_id)              # wirft kategorien.Fehlt
    ph = ",".join("?" * len(regale))
    buecher = await db.fetch_one(f"SELECT COUNT(DISTINCT book_id) AS n FROM book_categories WHERE category_id IN ({ph})",
                                 tuple(r["id"] for r in regale))
    async with db.einheit():
        for r in regale:
            if ziel.kategorie_id is not None:
                await db.execute("""INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle)
                                    SELECT book_id, ?, 'manuell' FROM book_categories WHERE category_id = ?""", (ziel.kategorie_id, r["id"]))
            else:
                await _etiketten(r, profil_id)
    return buecher["n"]


async def _etiketten(regal: dict, profil_id: str) -> None:
    """Der Name des Regals als Etikett des Profils an jedes seiner Bücher, das es noch nicht trägt."""
    name = regal["name"][:ETIKETT]
    await db.execute("""INSERT INTO book_labels (profil_id, book_id, color, name)
                        SELECT ?, x.book_id, ?, ? FROM book_categories x WHERE x.category_id = ?
                        AND NOT EXISTS (SELECT 1 FROM book_labels l WHERE l.book_id = x.book_id AND l.profil_id = ? AND l.name = ? COLLATE NOCASE)""",
                     (profil_id, regal["color"] if (regal["color"] or "").startswith("#") else ETIKETT_FARBE, name, regal["id"], profil_id, name))


async def loeschfolgen(nr: int) -> AltLoeschfolgen:
    [r] = await _regale([nr])
    zahlen = await db.fetch_one(f"""SELECT COUNT(*) AS buecher, SUM(NOT {merkmale.IN_KATEGORIE}) AS ohne
                                    FROM books b JOIN book_categories y ON y.book_id = b.id WHERE y.category_id = ?""", (nr,))
    titel = await db.fetch_all("""SELECT b.title FROM books b JOIN book_categories x ON x.book_id = b.id WHERE x.category_id = ?
                                  ORDER BY b.title COLLATE NOCASE LIMIT ?""", (nr, TITEL_IN_DEN_FOLGEN))
    return AltLoeschfolgen(id=nr, name=r["name"], buecher=zahlen["buecher"] or 0, ohne_kategorie=zahlen["ohne"] or 0,
                           titel=[t["title"] for t in titel])


async def entfernen(nr: int) -> int:
    """Das alte Regal fort, die Bücher bleiben; gibt zurück, wie viele darin standen."""
    folgen = await loeschfolgen(nr)
    async with db.einheit():
        await db.execute("DELETE FROM book_categories WHERE category_id = ?", (nr,))
        await db.execute("DELETE FROM categories WHERE id = ?", (nr,))
    return folgen.buecher
