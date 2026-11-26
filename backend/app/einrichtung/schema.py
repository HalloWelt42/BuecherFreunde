"""Tabellen der Ersteinrichtung (BF-82) und die Trigger, die Änderungen am Persönlichen zum Nachführen seines Begleiters merken.
Angelegt beim Verbinden nach dem Umbau der Familie (core/database.py), weil die Trigger an deren Tabellen hängen."""

from __future__ import annotations

JETZT = "(strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"

# je persönlicher Tabelle die Spalte mit dem Buch
_BUCH = {"user_book_data": "book_id", "book_notes": "book_id", "book_labels": "book_id", "book_highlights": "book_id",
         "vorlesestelle": "buch_id", "buch_privat": "book_id"}


def _merken(art: str, ziel: str) -> str:
    """Neu gemerkt oder die Zeit erneuert: geschrieben wird erst, wenn eine Weile nichts mehr kam (gebündelt)."""
    return (f"INSERT INTO nachfuehren(art, ziel) VALUES ('{art}', {ziel}) "
            f"ON CONFLICT(art, ziel) DO UPDATE SET seit = excluded.seit;")


def _trigger() -> str:
    teile = []
    for tabelle, spalte in _BUCH.items():
        for ereignis, zeile in (("INSERT", "NEW"), ("UPDATE", "NEW"), ("DELETE", "OLD")):
            teile.append(f"CREATE TRIGGER IF NOT EXISTS nachfuehren_{tabelle}_{ereignis.lower()} AFTER {ereignis} ON {tabelle} "
                         f"BEGIN {_merken('buch', f'{zeile}.{spalte}')} END;")
    for ereignis, zeile in (("INSERT", "NEW"), ("DELETE", "OLD")):
        teile.append(f"CREATE TRIGGER IF NOT EXISTS nachfuehren_freigabe_{ereignis.lower()} AFTER {ereignis} ON freigabe BEGIN "
                     f"INSERT INTO nachfuehren(art, ziel) SELECT 'buch', {zeile}.ziel_id WHERE {zeile}.art = 'buch' "
                     f"ON CONFLICT(art, ziel) DO UPDATE SET seit = excluded.seit; {_merken('profile', '0')} END;")
    teile += [
        f"CREATE TRIGGER IF NOT EXISTS nachfuehren_profil_insert AFTER INSERT ON profil BEGIN {_merken('profile', '0')} END;",
        f"CREATE TRIGGER IF NOT EXISTS nachfuehren_profil_delete AFTER DELETE ON profil BEGIN {_merken('profile', '0')} END;",
        "CREATE TRIGGER IF NOT EXISTS nachfuehren_profil_update AFTER UPDATE OF name, zeichen, farbe, rolle, geburtsjahr, stufe, "
        f"einstellungen, sortierung ON profil BEGIN {_merken('profile', '0')} END;",
        "CREATE TRIGGER IF NOT EXISTS nachfuehren_stimme AFTER INSERT ON app_settings WHEN NEW.key = 'familie_stimme' "
        f"BEGIN {_merken('profile', '0')} END;",
        "CREATE TRIGGER IF NOT EXISTS nachfuehren_stimme_neu AFTER UPDATE ON app_settings WHEN NEW.key = 'familie_stimme' "
        f"BEGIN {_merken('profile', '0')} END;",
    ]
    return "\n".join(teile)


SQL = f"""
CREATE TABLE IF NOT EXISTS einrichtung (             -- eine Zeile: ob und wie die Ersteinrichtung läuft
    id INTEGER PRIMARY KEY CHECK (id = 1),
    neu INTEGER NOT NULL DEFAULT 0,                  -- 1: beim ersten Start leerer Bestand ohne Markerdatei
    modus TEXT NOT NULL DEFAULT 'aus',               -- neu (Ersteinrichtung offen), wartung (wieder geöffnet), aus
    ausgangslage TEXT DEFAULT NULL,                  -- neu, sicherung, kellerwolke, umzug
    begonnen_am TEXT DEFAULT NULL,
    abgeschlossen_am TEXT DEFAULT NULL,
    geaendert_am TEXT NOT NULL DEFAULT {JETZT}
);
CREATE TABLE IF NOT EXISTS einrichtung_schritt (     -- je Schritt, was gemerkt ist; Konto und Bedingungen bestimmt der Zustand selbst
    schritt TEXT PRIMARY KEY,
    stand TEXT NOT NULL,                             -- erledigt, uebersprungen
    text TEXT NOT NULL DEFAULT '',
    geaendert_am TEXT NOT NULL DEFAULT {JETZT}
);
CREATE TABLE IF NOT EXISTS einrichtung_aenderung (   -- Wartung: was der Assistent ändern würde, bis es bestätigt ist
    id TEXT PRIMARY KEY,                             -- UUID
    schritt TEXT NOT NULL,
    art TEXT NOT NULL,                               -- anschluss, katalog, profil, stimme
    ziel TEXT NOT NULL DEFAULT '',                   -- etwa die Art des Anschlusses; je Ziel gilt die neueste
    was TEXT NOT NULL,
    alt TEXT NOT NULL DEFAULT '',
    neu TEXT NOT NULL DEFAULT '',
    daten TEXT NOT NULL DEFAULT '{{}}',              -- JSON, nie ein Schlüssel (der liegt vorgemerkt in der Schlüsseldatei)
    angelegt_am TEXT NOT NULL DEFAULT {JETZT}
);
CREATE TABLE IF NOT EXISTS einrichtung_auftrag (     -- Prüfung, Neuaufbau, Originale kopieren: fortsetzbar über einen Neustart
    art TEXT PRIMARY KEY,                            -- pruefung, neuaufbau, kopieren
    stand TEXT NOT NULL DEFAULT 'wartet',            -- wartet, laeuft, pause, fertig, fehler
    gesamt INTEGER NOT NULL DEFAULT 0,
    fertig INTEGER NOT NULL DEFAULT 0,
    angaben TEXT NOT NULL DEFAULT '{{}}',            -- JSON: Zähler der Teile, Wahl beim Start
    grund TEXT NOT NULL DEFAULT '',
    begonnen TEXT DEFAULT NULL,
    geaendert TEXT NOT NULL DEFAULT {JETZT},
    fertig_am TEXT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS original_befund (         -- Bericht der Prüfung: je Buch, ob sein Original erreichbar ist
    book_id INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
    ergebnis TEXT NOT NULL,                          -- erreichbar, wiedergefunden, fehlt
    ort TEXT NOT NULL DEFAULT '',
    pfad TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    texte INTEGER NOT NULL DEFAULT 0,                -- 1: Volltext oder Umschlag kamen aus dem Auszug zurück
    geprueft_am TEXT NOT NULL DEFAULT {JETZT}
);
CREATE TABLE IF NOT EXISTS neuaufbau_datei (         -- Neuaufbau: die Originale im gewählten Ordner der Kellerwolke
    knoten TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    pfad TEXT NOT NULL DEFAULT '',
    groesse INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL DEFAULT '',
    auszug TEXT DEFAULT NULL,                        -- Knoten des Auszugs; leer: ohne
    stand TEXT NOT NULL DEFAULT 'offen',             -- offen, fertig, da (gab es schon), fehler
    persoenlich TEXT DEFAULT NULL,                   -- Knoten des Begleiters persoenlich; leer: ohne
    book_id INTEGER DEFAULT NULL,
    teile TEXT NOT NULL DEFAULT '',                  -- was zurückkam: volltext umschlag persoenliches (Leerzeichen dazwischen)
    text TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS umzug (                   -- altes Gerät: der vorbereitete Umzug, höchstens einer
    id INTEGER PRIMARY KEY CHECK (id = 1),
    code TEXT NOT NULL,                              -- sha256 des Einmalcodes; der Code selbst steht nirgends
    gilt_bis TEXT NOT NULL,
    versuche_frei INTEGER NOT NULL,
    sicherung TEXT NOT NULL,                         -- Name der Sicherung im Sicherungsordner
    eingeloest_am TEXT DEFAULT NULL,
    sitzung TEXT DEFAULT NULL,                       -- sha256 der Sitzung des neuen Geräts
    sitzung_bis TEXT DEFAULT NULL,
    angelegt_am TEXT NOT NULL DEFAULT {JETZT}
);
CREATE TABLE IF NOT EXISTS umzug_kopie (             -- neues Gerät: Originale kopieren, je Datei; der Auftrag setzt hier fort
    hash TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    groesse INTEGER NOT NULL DEFAULT 0,
    stand TEXT NOT NULL DEFAULT 'offen',             -- offen, fertig, fehler
    text TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS nachfuehren (             -- Persönliches nachführen: buch (Begleiter neu), leeren (in den Papierkorb), profile
    art TEXT NOT NULL,
    ziel INTEGER NOT NULL,
    seit TEXT NOT NULL DEFAULT {JETZT},              -- letzte Änderung; nachgeführt wird nach einer ruhigen Weile
    grund TEXT NOT NULL DEFAULT '',                  -- bei art fehler: warum das Buch übersprungen wurde
    PRIMARY KEY (art, ziel)
);
{_trigger()}
"""


# Spalten, die nach dem ersten Anlegen dazukamen; fehlen sie in einem vorhandenen Bestand, zieht die Datenbank sie nach dem
# Anlegen dieser Tabellen nach (core/database.py)
SPALTEN: tuple[tuple[str, str, str], ...] = (
    ("nachfuehren", "grund", "TEXT NOT NULL DEFAULT ''"),
)
