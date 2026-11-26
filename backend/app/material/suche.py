"""Wortsuche im Begleitmaterial (BF-81): dieselbe Schreibweise wie die Suche in den Büchern (services/query_parser.py), nur in
Material von Büchern, die die Sicht sieht (BF-78). Ein Treffer nennt das Buch, die Datei und, bei einem PDF, die Seite."""

from __future__ import annotations

import logging
import sqlite3

from backend.app.core.database import db
from backend.app.familie.sichtbar import Sicht
from backend.app.material.modelle import Materialtreffer
from backend.app.services.query_parser import parse_query
from backend.app.services.search import _sanitize_html

logger = logging.getLogger("buecherfreunde.material.suche")


async def suchen(q: str, sicht: Sicht, anzahl: int = 20) -> list[Materialtreffer]:
    anfrage = parse_query(q).fts_query
    if not anfrage:
        return []
    bedingung, werte = sicht.bedingung("b.id")
    try:
        zeilen = await db.fetch_all(f"""SELECT t.material, t.buch_id, t.seite, m.name, b.title, b.author,
                                               snippet(material_fts, 0, '<mark>', '</mark>', '...', 30) AS auszug
                                        FROM material_fts JOIN material_text t ON t.id = material_fts.rowid
                                        JOIN buch_material m ON m.id = t.material JOIN books b ON b.id = t.buch_id
                                        WHERE material_fts MATCH ? AND {bedingung} ORDER BY rank LIMIT ?""", (anfrage, *werte, anzahl))
    except sqlite3.OperationalError as f:                 # eine Schreibweise, die der Index nicht versteht: keine Treffer
        logger.info("Suche im Material %r: %s", q, f)
        return []
    return [Materialtreffer(material_id=z["material"], buch_id=z["buch_id"], titel=z["title"], autor=z["author"], name=z["name"],
                            seite=z["seite"], auszug=_sanitize_html(z["auszug"] or "")) for z in zeilen]
