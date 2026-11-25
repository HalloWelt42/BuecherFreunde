"""Trägt die Ablageorte aus dem Stand des Kopierwerkzeugs in die Datenbank des Neubaus ein (BF-7). Wiederholbar.

    python3 uebernehmen.py <stand.sqlite> <buecherfreunde.db>"""
import sqlite3
import sys
from pathlib import PurePosixPath

stand, db = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True), sqlite3.connect(sys.argv[2], timeout=30)
db.execute("CREATE TABLE IF NOT EXISTS ablage_datei (hash TEXT PRIMARY KEY, knoten TEXT NOT NULL, name TEXT NOT NULL, pfad TEXT NOT NULL DEFAULT '', groesse INTEGER NOT NULL DEFAULT 0, begleiter TEXT DEFAULT NULL, abgelegt_am TEXT NOT NULL DEFAULT (datetime('now')))")
zeilen = stand.execute("SELECT hash, knoten, pfad, groesse, begleiter FROM datei WHERE fehler IS NULL AND knoten IS NOT NULL").fetchall()
db.executemany("INSERT OR REPLACE INTO ablage_datei(hash, knoten, name, pfad, groesse, begleiter) VALUES (?, ?, ?, ?, ?, ?)",
               [(h, k, PurePosixPath(p).name, p, g, b) for h, k, p, g, b in zeilen])
db.commit()
ohne = db.execute("SELECT COUNT(*) FROM books WHERE hash NOT IN (SELECT hash FROM ablage_datei)").fetchone()[0]
print(f"{len(zeilen)} Ablageorte eingetragen, {ohne} Bücher noch ohne")
