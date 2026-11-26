"""Freigaben für Kinder (BF-78): einzelne Bücher oder ganze Kategorien (mit allem darunter). Nichts geht von selbst frei; die
Altersangabe am Buch ist nur Hilfe. Freigeben kann nur, wer das Buch selbst sieht."""

from __future__ import annotations

from backend.app.core.database import db
from backend.app.familie.fehler import Fehlt, Unpassend
from backend.app.familie.modelle import FreigabeKategorie, Freigabeauftrag, Profil
from backend.app.familie.sichtbar import Sicht, nur_sichtbare

# die Bücher einer Kategorie und aller darunter
ANZAHL = """WITH RECURSIVE darunter(id) AS (SELECT ? UNION SELECT k.id FROM categories k JOIN darunter ON k.parent_id = darunter.id)
            SELECT COUNT(DISTINCT x.book_id) AS n FROM book_categories x WHERE x.category_id IN (SELECT id FROM darunter)"""


async def kategorien(kind: Profil) -> list[FreigabeKategorie]:
    zeilen = await db.fetch_all("""SELECT c.id, c.name, COALESCE(c.icon, '') AS zeichen FROM freigabe f
                                   JOIN categories c ON c.id = f.ziel_id WHERE f.profil_id = ? AND f.art = 'kategorie'
                                   ORDER BY c.sort_order, c.name COLLATE NOCASE""", (kind.id,))
    return [FreigabeKategorie(**z, anzahl=(await db.fetch_one(ANZAHL, (z["id"],)))["n"]) for z in zeilen]


async def buecher(kind: Profil) -> list[int]:
    """Die einzeln freigegebenen Bücher, nach Titel."""
    zeilen = await db.fetch_all("""SELECT b.id FROM freigabe f JOIN books b ON b.id = f.ziel_id
                                   WHERE f.profil_id = ? AND f.art = 'buch' ORDER BY b.title COLLATE NOCASE""", (kind.id,))
    return [z["id"] for z in zeilen]


async def _ziele(auftrag: Freigabeauftrag, von: Profil) -> list[int]:
    """Die genannten Ziele; fehlt eins (oder sieht es der Freigebende nicht), ändert sich nichts."""
    ids = list(dict.fromkeys(auftrag.ziel_ids))
    if auftrag.art == "buch":
        da = await nur_sichtbare(Sicht.von(von), ids)
    else:
        da = [z["id"] for z in await db.fetch_all(f"SELECT id FROM categories WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))]
    if fehlen := [i for i in ids if i not in set(da)]:
        raise Fehlt(f"{'Buch' if auftrag.art == 'buch' else 'Kategorie'} nicht gefunden: {', '.join(map(str, fehlen))}")
    return ids


async def hinzufuegen(kind: Profil, auftrag: Freigabeauftrag, von: Profil) -> None:
    if not kind.kind:
        raise Unpassend("Freigaben gibt es nur für Kinder")
    for ziel in await _ziele(auftrag, von):
        await db.execute("INSERT OR IGNORE INTO freigabe (profil_id, art, ziel_id, von_profil) VALUES (?, ?, ?, ?)",
                         (kind.id, auftrag.art, ziel, von.id))


async def entfernen(kind: Profil, auftrag: Freigabeauftrag) -> None:
    ids = list(dict.fromkeys(auftrag.ziel_ids))
    await db.execute(f"DELETE FROM freigabe WHERE profil_id = ? AND art = ? AND ziel_id IN ({','.join('?' * len(ids))})",
                     (kind.id, auftrag.art, *ids))
