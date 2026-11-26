"""Schnellfilter der Bücherlisten: jedes Wort muss in Titel, Autor, ISBN oder einem Etikett des Buchs vorkommen.

LIKE in SQLite übersieht Groß und Klein nur bei ASCII, "über" fände "Über" nicht. Deshalb GLOB mit beiden Schreibweisen
je Buchstabe ("*[üÜ]ber*"); Zeichen, die in GLOB etwas bedeuten, stehen einzeln in Klammern und gelten wörtlich."""

import re

HOECHSTENS_WOERTER = 8
HOECHSTENS_ZEICHEN = 100
# Ab vier Ziffern ein Stück ISBN; "3" in "Band 3" träfe sonst fast jede deutsche ISBN
_ISBN_TEIL = re.compile(r"[0-9xX]{4,}")


def muster(wort: str) -> str:
    """GLOB-Muster, das das Wort irgendwo im Text findet, Groß und Klein gleich."""
    teile: list[str] = []
    for zeichen in wort:
        klein, gross = zeichen.lower(), zeichen.upper()
        if klein != gross and len(klein) == 1 and len(gross) == 1:
            teile.append(f"[{klein}{gross}]")
        elif zeichen in "*?[]":
            teile.append(f"[{zeichen}]")
        else:
            teile.append(zeichen)
    return f"*{''.join(teile)}*"


def bedingung(suche: str | None) -> tuple[str, list[str]]:
    """Bedingung über `books b` samt Werten; leer, wenn es nichts zu filtern gibt."""
    teile: list[str] = []
    werte: list[str] = []
    for wort in (suche or "").split()[:HOECHSTENS_WOERTER]:
        wort = wort[:HOECHSTENS_ZEICHEN]
        m = muster(wort)
        oder = [
            "b.title GLOB ?",
            "b.author GLOB ?",
            "EXISTS (SELECT 1 FROM book_labels l WHERE l.book_id = b.id AND l.name GLOB ?)",
            "EXISTS (SELECT 1 FROM book_highlights h WHERE h.book_id = b.id AND h.label_name GLOB ?)",
        ]
        werte += [m, m, m, m]
        # ISBN mit oder ohne Bindestriche: verglichen wird nur, was nach einer ISBN aussieht
        ziffern = wort.replace("-", "")
        if _ISBN_TEIL.fullmatch(ziffern):
            oder.append("REPLACE(REPLACE(COALESCE(b.isbn, ''), '-', ''), ' ', '') GLOB ?")
            werte.append(muster(ziffern))
        teile.append("(" + " OR ".join(oder) + ")")
    return " AND ".join(teile), werte
