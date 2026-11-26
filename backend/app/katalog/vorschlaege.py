"""Vorschläge des Katalogs (BF-69) in `katalog_vorschlag`: ein Buch in einer Kategorie, gefunden von Regel, KI oder
beiden. Entscheiden darf nur der Mensch: annehmen schreibt `book_categories` (Quelle `katalog-regel`, bei der KI allein
`katalog-ki`), ablehnen merkt es; ein abgelehnter oder angenommener Vorschlag kommt nie wieder."""

from __future__ import annotations

import json

from backend.app.core.database import db
from backend.app.katalog.modelle import Auch, Fund, OffeneJeKategorie, OffenerVorschlag
from backend.app.katalog.regeln import Regeltreffer, sicherheit
from backend.app.katalog.ki_fragen import KiFund

BEIDE_DAZU = 5                                 # stimmen Regel und KI überein, so viel sicherer
BEIDE_HOECHSTENS = 99
QUELLE_IM_REGAL = {"regel": "katalog-regel", "beide": "katalog-regel", "ki": "katalog-ki"}


def zusammenfuehren(regeln: dict[tuple[int, int], list[Regeltreffer]], ki: dict[tuple[int, int], KiFund]) -> list[Fund]:
    """Je Buch und Kategorie ein Fund; stimmen Regel und KI überein, heißt die Quelle `beide`."""
    aus = []
    for buch, kategorie in sorted(set(regeln) | set(ki)):
        r, k = regeln.get((buch, kategorie), []), ki.get((buch, kategorie))
        gruende = [t.satz for t in r] + ([k.satz] if k else [])
        if r and k:
            quelle, wert = "beide", min(BEIDE_HOECHSTENS, max(sicherheit(r), k.sicherheit) + BEIDE_DAZU)
        elif r:
            quelle, wert = "regel", sicherheit(r)
        else:
            assert k is not None
            quelle, wert = "ki", k.sicherheit
        aus.append(Fund(buch_id=buch, kategorie_id=kategorie, quelle=quelle, gruende=gruende, sicherheit=wert))
    return aus


def teil_vor_ganzem(funde: list[Fund], teil_von: dict[int, int]) -> list[Fund]:
    """Passt ein Buch zu einem Teil einer großen Kategorie (`teil_von`: Teil -> große), wird nur der Teil vorgeschlagen,
    sonst die große Kategorie."""
    ganz = {(f.buch_id, teil_von[f.kategorie_id]) for f in funde if f.kategorie_id in teil_von}
    return [f for f in funde if (f.buch_id, f.kategorie_id) not in ganz]


async def merken(funde: list[Fund], lauf_id: int | None) -> list[Fund]:
    """Neue Funde als offene Vorschläge, offene werden erneuert; gibt zurück, was gemerkt wurde. Steht das Buch schon in
    der Kategorie oder wurde der Vorschlag schon entschieden, bleibt es dabei."""
    gemerkt = []
    for f in funde:
        if await db.fetch_one("SELECT 1 FROM book_categories WHERE book_id = ? AND category_id = ?", (f.buch_id, f.kategorie_id)):
            continue
        c = await db.execute("""INSERT INTO katalog_vorschlag (book_id, category_id, quelle, gruende, sicherheit, lauf_id)
                                VALUES (?, ?, ?, ?, ?, ?)
                                ON CONFLICT (book_id, category_id) DO UPDATE SET quelle = excluded.quelle, gruende = excluded.gruende,
                                    sicherheit = excluded.sicherheit, lauf_id = excluded.lauf_id
                                WHERE katalog_vorschlag.stand = 'offen'""",
                             (f.buch_id, f.kategorie_id, f.quelle, json.dumps(f.gruende, ensure_ascii=False), f.sicherheit, lauf_id))
        if c.rowcount:
            gemerkt.append(f)
    return gemerkt


async def uebersicht() -> list[OffeneJeKategorie]:
    zeilen = await db.fetch_all("""SELECT category_id, COUNT(*) AS n FROM katalog_vorschlag WHERE stand = 'offen'
                                   GROUP BY category_id ORDER BY category_id""")
    return [OffeneJeKategorie(kategorie_id=z["category_id"], anzahl=z["n"]) for z in zeilen]


async def seite(kategorie: int | None, seite: int, pro_seite: int, sicher_ab: int) -> tuple[int, list[OffenerVorschlag]]:
    """Offene Vorschläge, die sichersten zuerst; je Vorschlag die übrigen offenen für dasselbe Buch."""
    wo, werte = ("v.stand = 'offen' AND v.category_id = ?", (kategorie,)) if kategorie else ("v.stand = 'offen'", ())
    gesamt = await db.fetch_one(f"SELECT COUNT(*) AS n FROM katalog_vorschlag v WHERE {wo}", werte)
    zeilen = await db.fetch_all(f"""SELECT v.id, v.book_id, v.category_id, v.quelle, v.gruende, v.sicherheit FROM katalog_vorschlag v
                                    JOIN books b ON b.id = v.book_id WHERE {wo}
                                    ORDER BY v.sicherheit DESC, b.title COLLATE NOCASE, v.id LIMIT ? OFFSET ?""",
                                (*werte, pro_seite, (seite - 1) * pro_seite))
    auch = await _auch([z["book_id"] for z in zeilen])
    return gesamt["n"], [OffenerVorschlag(id=z["id"], buch_id=z["book_id"], kategorie_id=z["category_id"], quelle=z["quelle"],
                                          gruende=json.loads(z["gruende"] or "[]"), sicherheit=z["sicherheit"],
                                          vorab=z["sicherheit"] >= sicher_ab,
                                          auch=[a for a in auch.get(z["book_id"], []) if a.kategorie_id != z["category_id"]])
                         for z in zeilen]


async def _auch(buecher: list[int]) -> dict[int, list[Auch]]:
    if not buecher:
        return {}
    zeilen = await db.fetch_all(f"""SELECT v.id, v.book_id, v.category_id, c.name, v.sicherheit FROM katalog_vorschlag v
                                    JOIN categories c ON c.id = v.category_id
                                    WHERE v.stand = 'offen' AND v.book_id IN ({','.join('?' * len(buecher))})
                                    ORDER BY v.sicherheit DESC, c.name COLLATE NOCASE""", tuple(buecher))
    aus: dict[int, list[Auch]] = {}
    for z in zeilen:
        aus.setdefault(z["book_id"], []).append(Auch(id=z["id"], kategorie_id=z["category_id"], name=z["name"], sicherheit=z["sicherheit"]))
    return aus


async def _offene(ids: list[int] | None, kategorie: int | None) -> list[dict]:
    if kategorie is not None:
        return await db.fetch_all("SELECT id, book_id, category_id, quelle FROM katalog_vorschlag WHERE stand = 'offen' AND category_id = ?",
                                  (kategorie,))
    ids = list(dict.fromkeys(ids or []))
    if not ids:
        return []
    return await db.fetch_all(f"""SELECT id, book_id, category_id, quelle FROM katalog_vorschlag
                                  WHERE stand = 'offen' AND id IN ({','.join('?' * len(ids))})""", tuple(ids))


async def annehmen(ids: list[int] | None = None, kategorie: int | None = None) -> int:
    """Die genannten offenen Vorschläge oder alle offenen einer Kategorie; gibt zurück, wie viele angenommen wurden."""
    offen = await _offene(ids, kategorie)
    async with db.einheit():
        for v in offen:
            await db.execute("INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, ?)",
                             (v["book_id"], v["category_id"], QUELLE_IM_REGAL[v["quelle"]]))
            await db.execute("UPDATE katalog_vorschlag SET stand = 'angenommen' WHERE id = ?", (v["id"],))
    return len(offen)


async def ablehnen(ids: list[int]) -> int:
    offen = await _offene(ids, None)
    async with db.einheit():
        for v in offen:
            await db.execute("UPDATE katalog_vorschlag SET stand = 'abgelehnt' WHERE id = ?", (v["id"],))
    return len(offen)
