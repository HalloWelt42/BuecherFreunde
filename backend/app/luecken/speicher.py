"""Die Tabellen der Lücken (BF-75): `collections.luecken` (Platzhalter an oder aus), `reihe_sprache` (je Sammlung und Sprache die
Zahl der Bände, die Wahl des Nutzers und das Nachschlagen), `reihe_band` (was die Quelle je Band weiß) und `luecke_ausgeblendet`.
Lesen und Schreiben nur hier; was daraus folgt, rechnet luecken/rechnen.py."""

from __future__ import annotations

from collections import defaultdict

from backend.app.core.database import db
from backend.app.luecken.bandnummer import lesen
from backend.app.luecken.modelle import Ausblendgrund, Ausgeblendet, Buchband, GRUENDE, Quellband, Quellergebnis, Reihenstand, Wahl
from backend.app.luecken.sprachen import hauptsprache, sprache_von, sprachname

JETZT = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"


class SammlungFehlt(LookupError):
    pass


async def sammlung(sammlung_id: int) -> dict:
    z = await db.fetch_one("SELECT id, name, luecken FROM collections WHERE id = ?", (sammlung_id,))
    if z is None:
        raise SammlungFehlt("Sammlung nicht gefunden")
    return z


async def an_setzen(sammlung_id: int, an: bool) -> None:
    await db.execute("UPDATE collections SET luecken = ? WHERE id = ?", (int(an), sammlung_id))


# -- Bücher ----------------------------------------------------------------------------------------------------------------

async def buchbaende(sammlung_id: int) -> list[Buchband]:
    """Alle Bücher der Sammlung, gleich wer sie sieht (die Sicht wählt die Ansicht aus)."""
    zeilen = await db.fetch_all("""SELECT id, title AS titel, author AS autor, COALESCE(band_nummer, '') AS band, COALESCE(language, '') AS sprache,
                                          id IN (SELECT book_id FROM buch_privat) AS privat
                                   FROM books WHERE sammlung_id = ?""", (sammlung_id,))
    return [Buchband(**z) for z in zeilen]


async def hauptsprache_der_sammlung(sammlung_id: int) -> str:
    return hauptsprache(b.sprache for b in await buchbaende(sammlung_id))


def je_sprache(baende: list[Buchband], haupt: str) -> dict[str, list[Buchband]]:
    aus: dict[str, list[Buchband]] = defaultdict(list)
    for b in baende:
        aus[sprache_von(b.sprache, haupt)].append(b)
    return dict(aus)


# -- Zahl der Bände und Nachschlagen ------------------------------------------------------------------------------------------

async def reihenstaende(sammlung_id: int) -> dict[str, Reihenstand]:
    zeilen = await db.fetch_all("""SELECT sprache, wahl, eigene, quelle_gesamt, quelle, gefragt, stand, grund, nachgeschlagen_am
                                   FROM reihe_sprache WHERE sammlung_id = ?""", (sammlung_id,))
    return {z["sprache"]: Reihenstand(**z) for z in zeilen}


async def wahl_setzen(sammlung_id: int, sprache: str, wahl: Wahl, zahl: int | None) -> None:
    await db.execute("""INSERT INTO reihe_sprache (sammlung_id, sprache, wahl, eigene) VALUES (?, ?, ?, ?)
                        ON CONFLICT(sammlung_id, sprache) DO UPDATE SET wahl = excluded.wahl, eigene = excluded.eigene""",
                     (sammlung_id, sprache, wahl, zahl))


async def nachgeschlagen(sammlung_id: int, sprache: str, quelle: str, gefragt: str, ergebnis: Quellergebnis) -> None:
    """Die Antwort der Quelle; danach wird diese Sammlung in dieser Sprache nie wieder von selbst gefragt."""
    async with db.einheit():
        if await db.fetch_one("SELECT 1 AS da FROM collections WHERE id = ?", (sammlung_id,)) is None:
            return                                          # inzwischen gelöscht
        await _abgeschlossen(sammlung_id, sprache, quelle, gefragt, "fertig", "" if ergebnis.gesamt else "Die Quelle kennt die Reihe nicht",
                             ergebnis.gesamt, neue_zahl=True)
        await db.execute("DELETE FROM reihe_band WHERE sammlung_id = ? AND sprache = ?", (sammlung_id, sprache))
        await db.execute_many("""INSERT INTO reihe_band (sammlung_id, sprache, nummer, titel, autor, isbn, jahr, quelle)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                              [(sammlung_id, sprache, b.nummer, b.titel, b.autor, b.isbn, b.jahr, b.quelle) for b in ergebnis.baende])


async def gescheitert(sammlung_id: int, sprache: str, quelle: str, gefragt: str, grund: str) -> None:
    """Gefragt, aber keine Antwort: zählt als die eine Abfrage; nur "Neu nachschlagen" fragt wieder."""
    if await db.fetch_one("SELECT 1 AS da FROM collections WHERE id = ?", (sammlung_id,)) is not None:
        await _abgeschlossen(sammlung_id, sprache, quelle, gefragt, "fehler", grund, None, neue_zahl=False)


async def _abgeschlossen(sammlung_id: int, sprache: str, quelle: str, gefragt: str, stand: str, grund: str, gesamt: int | None, *,
                         neue_zahl: bool) -> None:
    """`neue_zahl`: die Antwort ersetzt die Zahl der Quelle (auch durch keine); ohne Antwort bleibt die frühere."""
    zahl = "excluded.quelle_gesamt" if neue_zahl else "reihe_sprache.quelle_gesamt"
    await db.execute(f"""INSERT INTO reihe_sprache (sammlung_id, sprache, quelle, gefragt, stand, grund, quelle_gesamt, nachgeschlagen_am)
                         VALUES (?, ?, ?, ?, ?, ?, ?, {JETZT})
                         ON CONFLICT(sammlung_id, sprache) DO UPDATE SET quelle = excluded.quelle, gefragt = excluded.gefragt,
                             stand = excluded.stand, grund = excluded.grund, quelle_gesamt = {zahl},
                             nachgeschlagen_am = excluded.nachgeschlagen_am""",
                     (sammlung_id, sprache, quelle, gefragt, stand, grund, gesamt))


ABKUERZUNG_NEU = "luecken_abkuerzung_neu_gefragt"     # Merker in app_settings: einmal und nie wieder


async def abkuerzungen_neu_fragen(ist_abkuerzung) -> int:
    """Einmal: Fragen, die unter einer Abkürzung aus Dateinamen ohne Ergebnis blieben (vor der Regel in dienst.reihenname),
    werden wieder offen, damit sie mit dem Namen der Sammlung genau ein weiteres Mal gestellt werden. Danach nie wieder."""
    if await db.fetch_one("SELECT 1 FROM app_settings WHERE key = ?", (ABKUERZUNG_NEU,)):
        return 0
    zeilen = await db.fetch_all("SELECT sammlung_id, sprache, gefragt FROM reihe_sprache WHERE stand = 'fertig' AND quelle_gesamt IS NULL")
    neu = [(z["sammlung_id"], z["sprache"]) for z in zeilen if ist_abkuerzung(z["gefragt"])]
    await db.execute_many("UPDATE reihe_sprache SET stand = 'offen', grund = '' WHERE sammlung_id = ? AND sprache = ?", neu)
    await db.execute("INSERT INTO app_settings(key, value) VALUES (?, '1')", (ABKUERZUNG_NEU,))
    await db.commit()
    return len(neu)


async def neu_nachschlagen(sammlung_id: int) -> None:
    """Alle Sprachen der Sammlung wieder offen, auf Wunsch des Nutzers (etwa nach einem Fehler oder einem neuen Namen)."""
    await db.execute("UPDATE reihe_sprache SET stand = 'offen', grund = '' WHERE sammlung_id = ?", (sammlung_id,))


async def offene_paare() -> list[tuple[int, str]]:
    """Was das Nachschlagen fragen darf: je Sammlung mit Platzhaltern jede Sprache, in der ein Band eine Nummer hat und die noch
    nie gefragt wurde (oder auf Wunsch wieder offen ist)."""
    zeilen = await db.fetch_all("""SELECT c.id AS sammlung_id, b.id, COALESCE(b.band_nummer, '') AS band, COALESCE(b.language, '') AS sprache
                                   FROM collections c JOIN books b ON b.sammlung_id = c.id
                                   WHERE c.luecken = 1 ORDER BY c.sort_order, c.name, c.id""")
    zu = {(z["sammlung_id"], z["sprache"]) for z in await db.fetch_all("SELECT sammlung_id, sprache FROM reihe_sprache WHERE stand != 'offen'")}
    je_sammlung: dict[int, list[Buchband]] = defaultdict(list)
    for z in zeilen:
        je_sammlung[z["sammlung_id"]].append(Buchband(id=z["id"], band=z["band"], sprache=z["sprache"]))
    aus = []
    for s, baende in je_sammlung.items():
        haupt = hauptsprache(b.sprache for b in baende)
        for sprache, liste in je_sprache(baende, haupt).items():
            if (s, sprache) not in zu and any(lesen(b.band).plaetze for b in liste):
                aus.append((s, sprache))
    return aus


# -- Was die Quelle je Band weiß ------------------------------------------------------------------------------------------------

async def quellbaende(sammlung_id: int) -> dict[tuple[str, int], Quellband]:
    zeilen = await db.fetch_all("SELECT sprache, nummer, titel, autor, isbn, jahr, quelle FROM reihe_band WHERE sammlung_id = ?", (sammlung_id,))
    return {(z["sprache"], z["nummer"]): Quellband(**{k: z[k] for k in Quellband.model_fields}) for z in zeilen}


async def quellband(sammlung_id: int, sprache: str, nummer: int) -> Quellband | None:
    z = await db.fetch_one("""SELECT nummer, titel, autor, isbn, jahr, quelle FROM reihe_band
                              WHERE sammlung_id = ? AND sprache = ? AND nummer = ?""", (sammlung_id, sprache, nummer))
    return Quellband(**z) if z else None


# -- Ausgeblendet -------------------------------------------------------------------------------------------------------------

async def ausgeblendete(sammlung_id: int) -> list[Ausgeblendet]:
    zeilen = await db.fetch_all("""SELECT a.sprache, a.nummer, a.grund, a.am, COALESCE(r.titel, '') AS titel FROM luecke_ausgeblendet a
                                   LEFT JOIN reihe_band r ON r.sammlung_id = a.sammlung_id AND r.sprache = a.sprache AND r.nummer = a.nummer
                                   WHERE a.sammlung_id = ? ORDER BY a.sprache, a.nummer""", (sammlung_id,))
    return [Ausgeblendet(**z, name=sprachname(z["sprache"]), grund_text=GRUENDE[z["grund"]]) for z in zeilen]


async def ausblenden(sammlung_id: int, sprache: str, nummer: int, grund: Ausblendgrund) -> None:
    await db.execute(f"""INSERT INTO luecke_ausgeblendet (sammlung_id, sprache, nummer, grund) VALUES (?, ?, ?, ?)
                         ON CONFLICT(sammlung_id, sprache, nummer) DO UPDATE SET grund = excluded.grund, am = {JETZT}""",
                     (sammlung_id, sprache, nummer, grund))


async def zurueckholen(sammlung_id: int, sprache: str, nummer: int) -> bool:
    c = await db.execute("DELETE FROM luecke_ausgeblendet WHERE sammlung_id = ? AND sprache = ? AND nummer = ?", (sammlung_id, sprache, nummer))
    return c.rowcount > 0
