"""Tabellen der Familie (BF-78, docs/neubau/FAMILIE.md, Daten): Profile, Sitzungen, Gerätebindung, private Bücher, Freigaben,
Lesezeit, und die Form der persönlichen Tabellen mit `profil_id`. Hier steht die einzige Wahrheit über diese Formen; der Umbau
(familie/umbau.py) legt sie an oder bringt alte Tabellen dahin."""

from __future__ import annotations

from dataclasses import dataclass

JETZT = "(strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"

FAMILIE_SQL = f"""
CREATE TABLE IF NOT EXISTS profil (
    id TEXT PRIMARY KEY,                             -- UUID
    name TEXT NOT NULL,
    zeichen TEXT NOT NULL DEFAULT '',
    farbe TEXT NOT NULL DEFAULT '',
    rolle TEXT NOT NULL,                             -- verwaltung, erwachsen, kind
    pin TEXT NOT NULL DEFAULT '',                    -- scrypt; leer: ohne
    bild_pin TEXT NOT NULL DEFAULT '',               -- scrypt der Bilder in ihrer Folge; leer: ohne
    geburtsjahr INTEGER DEFAULT NULL,
    stufe TEXT DEFAULT NULL,                         -- nur Kind, eine aus stufen.json
    einstellungen TEXT NOT NULL DEFAULT '{{}}',      -- JSON: lesehilfen, lesezeit, katze (familie/modelle.py)
    sortierung INTEGER NOT NULL DEFAULT 0,
    name_vom_konto INTEGER NOT NULL DEFAULT 0,       -- 1: beim nächsten Anmelden den Namen des Kontos übernehmen
    angelegt_am TEXT NOT NULL DEFAULT {JETZT}
);
CREATE TABLE IF NOT EXISTS profil_sitzung (          -- ein Schlüssel gilt, bis gewechselt oder abgemeldet wird
    pruefsumme TEXT PRIMARY KEY,                     -- sha256 des Schlüssels; der Schlüssel selbst steht nirgends
    profil_id TEXT NOT NULL REFERENCES profil(id) ON DELETE CASCADE,
    geraet TEXT NOT NULL DEFAULT '',
    ueber_bindung INTEGER NOT NULL DEFAULT 0,        -- 1: nach der Eltern-PIN auf einem fest gestellten Gerät gewählt
    angelegt_am TEXT NOT NULL DEFAULT {JETZT},
    zuletzt_am TEXT NOT NULL DEFAULT {JETZT}
);
CREATE INDEX IF NOT EXISTS idx_profil_sitzung_profil ON profil_sitzung(profil_id);
CREATE TABLE IF NOT EXISTS geraet_bindung (          -- ein gebundenes Gerät zeigt nur dieses Profil
    geraet TEXT PRIMARY KEY,                         -- zufällige Kennung des Browsers
    profil_id TEXT NOT NULL REFERENCES profil(id) ON DELETE CASCADE,
    offen_bis TEXT DEFAULT NULL,                     -- nach der Eltern-PIN darf bis dahin jemand anders wählen
    angelegt_am TEXT NOT NULL DEFAULT {JETZT}
);
CREATE TABLE IF NOT EXISTS buch_privat (             -- nur dieses Profil sieht das Buch
    profil_id TEXT NOT NULL REFERENCES profil(id) ON DELETE CASCADE,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    angelegt_am TEXT NOT NULL DEFAULT {JETZT},
    PRIMARY KEY (profil_id, book_id)
);
CREATE INDEX IF NOT EXISTS idx_buch_privat_buch ON buch_privat(book_id);
CREATE TABLE IF NOT EXISTS freigabe (                -- was ein Kind sieht: einzelne Bücher oder ganze Kategorien
    profil_id TEXT NOT NULL REFERENCES profil(id) ON DELETE CASCADE,
    art TEXT NOT NULL,                               -- buch, kategorie
    ziel_id INTEGER NOT NULL,                        -- books.id oder categories.id
    von_profil TEXT DEFAULT NULL REFERENCES profil(id) ON DELETE SET NULL,
    angelegt_am TEXT NOT NULL DEFAULT {JETZT},
    PRIMARY KEY (profil_id, art, ziel_id)
);
CREATE TRIGGER IF NOT EXISTS freigabe_buch_fort AFTER DELETE ON books
BEGIN DELETE FROM freigabe WHERE art = 'buch' AND ziel_id = OLD.id; END;
CREATE TRIGGER IF NOT EXISTS freigabe_kategorie_fort AFTER DELETE ON categories
BEGIN DELETE FROM freigabe WHERE art = 'kategorie' AND ziel_id = OLD.id; END;
CREATE TABLE IF NOT EXISTS ansage_auftrag (          -- der Auftrag "Ansagen erstellen" je Stimme (familie/ansagelauf.py)
    stimme TEXT PRIMARY KEY,                         -- katalog:<name>
    stand TEXT NOT NULL DEFAULT 'wartet',            -- wartet, laeuft, fertig, fehler
    gesamt INTEGER NOT NULL DEFAULT 0,
    fertig INTEGER NOT NULL DEFAULT 0,
    grund TEXT NOT NULL DEFAULT '',
    begonnen TEXT DEFAULT NULL,
    geaendert TEXT NOT NULL DEFAULT {JETZT},
    fertig_am TEXT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS lesezeit (                -- je Kind und Tag, gezählt im Takt des Lesers
    profil_id TEXT NOT NULL REFERENCES profil(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,                               -- JJJJ-MM-TT, Ortszeit
    sekunden INTEGER NOT NULL DEFAULT 0,
    vorlesen_sekunden INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (profil_id, tag)
);
"""

PROFIL = "profil_id TEXT NOT NULL REFERENCES profil(id) ON DELETE CASCADE"


@dataclass(frozen=True)
class Form:
    """Die Form einer persönlichen Tabelle: Spalten in ihrer Folge, Schlüssel und Indizes."""

    tabelle: str
    spalten: tuple[str, ...]                         # je Spalte ihre Erklärung; die erste Angabe ist der Name
    schluessel: str = ""                             # PRIMARY KEY (...), leer: der Schlüssel steht an einer Spalte
    indizes: tuple[str, ...] = ()

    @property
    def namen(self) -> list[str]:
        return [s.split()[0] for s in self.spalten]

    def anlegen(self, name: str | None = None, weitere: tuple[str, ...] = ()) -> str:
        teile = [*self.spalten, *weitere, *([f"PRIMARY KEY ({self.schluessel})"] if self.schluessel else [])]
        return f"CREATE TABLE {name or self.tabelle} (\n    " + ",\n    ".join(teile) + "\n)"


PERSOENLICH: tuple[Form, ...] = (
    Form("user_book_data", (
        PROFIL,
        "book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE",
        "is_favorite INTEGER DEFAULT 0",
        "is_to_read INTEGER DEFAULT 0",
        "rating INTEGER DEFAULT 0",
        "reading_position TEXT DEFAULT ''",
        "last_read_at TEXT DEFAULT NULL",
        "fassung_wahl TEXT NOT NULL DEFAULT ''",     # BF-71: welche Fassung "Lesen" öffnet; leer das Original
        "geteilt INTEGER NOT NULL DEFAULT 0",        # BF-78: das Kind teilt dieses Buch mit den Eltern (Einblick ab Jugend)
        "fertig_am TEXT DEFAULT NULL",               # BF-78: fertig gelesen (familie/lesestand.py); bleibt beim Zurückblättern
    ), "profil_id, book_id", ("CREATE INDEX IF NOT EXISTS idx_user_book_data_buch ON user_book_data(book_id)",)),
    Form("book_notes", (
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        PROFIL,
        "book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE",
        "content TEXT NOT NULL",
        "page_reference INTEGER DEFAULT NULL",
        "cfi_reference TEXT DEFAULT ''",
        "created_at TEXT NOT NULL DEFAULT (datetime('now'))",
        "updated_at TEXT NOT NULL DEFAULT (datetime('now'))",
    ), indizes=("CREATE INDEX IF NOT EXISTS idx_notes_book ON book_notes(book_id)",
                "CREATE INDEX IF NOT EXISTS idx_notes_profil ON book_notes(profil_id, book_id)")),
    Form("book_labels", (
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        PROFIL,
        "book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE",
        "color TEXT NOT NULL DEFAULT '#4FC3F7'",
        "name TEXT NOT NULL DEFAULT ''",
        "note TEXT NOT NULL DEFAULT ''",
        "page_reference TEXT DEFAULT ''",
        "position_percent REAL DEFAULT 0",
        "cfi_reference TEXT DEFAULT ''",
        "created_at TEXT NOT NULL DEFAULT (datetime('now'))",
    ), indizes=("CREATE INDEX IF NOT EXISTS idx_labels_book ON book_labels(book_id)",
                "CREATE INDEX IF NOT EXISTS idx_labels_profil ON book_labels(profil_id, book_id)")),
    Form("book_highlights", (
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        PROFIL,
        "book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE",
        "cfi_range TEXT NOT NULL",
        "color TEXT NOT NULL DEFAULT '#FFEE58'",
        "text_snippet TEXT NOT NULL DEFAULT ''",
        "label_name TEXT NOT NULL DEFAULT ''",
        "label_note TEXT NOT NULL DEFAULT ''",
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    ), indizes=("CREATE INDEX IF NOT EXISTS idx_highlights_book ON book_highlights(book_id)",
                "CREATE INDEX IF NOT EXISTS idx_highlights_profil ON book_highlights(profil_id, book_id)")),
    Form("vorlesestelle", (                          # wo das Vorlesen je Buch stehen blieb (api/user_data.py); auf jedem Gerät
        PROFIL,
        "buch_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE",
        "einheit INTEGER NOT NULL",                  # Seite, Abschnitt oder Stück der Lesequelle, ab 0
        "zeichen INTEGER NOT NULL",                  # Anfang des Satzes in der Einheit
        "bis_einheit INTEGER",                       # Ende des gewählten Umfangs (ausschließlich); leer: bis zum Ende
        "bis_zeichen INTEGER",
        "umfang TEXT NOT NULL DEFAULT ''",
        "ort TEXT NOT NULL DEFAULT ''",
        f"gemerkt_am TEXT NOT NULL DEFAULT {JETZT}",
    ), "profil_id, buch_id"),
    Form("fassung_lesestand", (                      # wo man in einer Übersetzung liest (services/fassung_lesen.py)
        PROFIL,
        "fassung_id INTEGER NOT NULL REFERENCES fassung(id) ON DELETE CASCADE",
        "position TEXT NOT NULL DEFAULT ''",
        f"gelesen_am TEXT NOT NULL DEFAULT {JETZT}",
    ), "profil_id, fassung_id"),
)
