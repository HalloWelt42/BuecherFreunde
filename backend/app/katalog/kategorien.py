"""Der gültige Katalog (BF-69): Bereiche und Kategorien in `categories` (`art` bereich, kategorie), neben den Regalen
(`art` regal). Eine Kategorie hängt an ihrem Bereich (`parent_id`), ihr Schlüssel ist fest (`schluessel`), ihre Regeln
stehen als JSON in `regeln`.

Einen Entwurf annehmen schreibt ihn hinein: gleicher Schlüssel ändert, ein neuer wird angelegt, gelöscht wird dabei nie.
Gelöscht wird nur einzeln, nach den Folgen (`loeschfolgen_*`), ein Bereich nur ohne Kategorien."""

from __future__ import annotations

import asyncio
import json
from collections import Counter

from pydantic import ValidationError

from backend.app.core.database import db
from backend.app.katalog import merkmale
from backend.app.katalog.datei import freier_schluessel, herkunft, schluesselteil
from backend.app.katalog.modelle import (
    BUCH, REGELARTEN, Bereich, BereichAenderung, BereichEingabe, Einordnungskategorie, Katalog, KatalogAntwort,
    Katalogbereich, Katalogkategorie, Kategorie, KategorieAenderung, KategorieEingabe, Loeschfolgen, Regal, Regelzahl,
    Regeln, Treffer, eigene_farbe,
)
from backend.app.katalog.regeln import Pruefer

SLUG = "katalog:"                              # Vorsilbe der Kürzel; Kürzel der Regale enthalten nie einen Doppelpunkt
TITEL_IN_DEN_FOLGEN = 10
BEREICH_FEHLT = "Bereich nicht gefunden"
KATEGORIE_FEHLT = "Kategorie nicht gefunden"
SPALTEN = """c.id, c.art, c.schluessel, c.name, c.icon, c.color, c.description, c.ki_beschreibung, c.regeln, c.verborgen,
             c.herkunft, c.arten, c.parent_id, c.spezial"""


class Fehlt(LookupError):
    pass


class Vergeben(Exception):
    """Den Namen gibt es an dieser Stelle schon."""


class HatKategorien(Exception):
    pass


def zeichen(icon: str | None) -> str:
    """Zeichen ohne "fa-": ältere Regale haben es mit."""
    return (icon or "").removeprefix("fa-")


def regeln_aus(text: str | None) -> Regeln:
    try:
        return Regeln.model_validate_json(text or "{}")
    except ValidationError:
        return Regeln()


def arten_aus(text: str | None) -> list[str]:
    try:
        arten = json.loads(text or "")
    except ValueError:
        return [BUCH]
    return [a for a in arten if isinstance(a, str)] if isinstance(arten, list) else [BUCH]


# -- lesen ------------------------------------------------------------------------------------------------------------------

async def _zeilen() -> list[dict]:
    return await db.fetch_all(f"""SELECT {SPALTEN}, (SELECT COUNT(*) FROM book_categories x WHERE x.category_id = c.id) AS anzahl
                                  FROM categories c ORDER BY c.sort_order, c.name COLLATE NOCASE, c.id""")


async def _bereichszahlen() -> dict[int, int]:
    zeilen = await db.fetch_all("""SELECT k.parent_id AS id, COUNT(DISTINCT x.book_id) AS n FROM categories k
                                   JOIN book_categories x ON x.category_id = k.id WHERE k.art = 'kategorie' GROUP BY k.parent_id""")
    return {z["id"]: z["n"] for z in zeilen}


def _kategorie(z: dict, bereichsfarbe: str) -> Kategorie:
    return Kategorie(id=z["id"], schluessel=z["schluessel"], name=z["name"], zeichen=zeichen(z["icon"]), farbe=z["color"] or bereichsfarbe,
                     ki_beschreibung=z["ki_beschreibung"], regeln=regeln_aus(z["regeln"]), verborgen=bool(z["verborgen"]),
                     herkunft=z["herkunft"], anzahl=z["anzahl"])


def _gliedern(zeilen: list[dict]) -> list[tuple[dict, list[dict]]]:
    """Je Bereich seine Kategorien, in der Reihenfolge des Katalogs."""
    bereiche = [z for z in zeilen if z["art"] == "bereich"]
    je: dict[int, list[dict]] = {b["id"]: [] for b in bereiche}
    for z in zeilen:
        if z["art"] == "kategorie" and z["parent_id"] in je:
            je[z["parent_id"]].append(z)
    return [(b, je[b["id"]]) for b in bereiche]


async def katalog() -> KatalogAntwort:
    zeilen = await _zeilen()
    zahlen = await _bereichszahlen()
    bereiche = [Bereich(id=b["id"], schluessel=b["schluessel"], name=b["name"], zeichen=zeichen(b["icon"]), farbe=b["color"] or "",
                        beschreibung=b["description"] or "", arten=arten_aus(b["arten"]), verborgen=bool(b["verborgen"]),
                        anzahl=zahlen.get(b["id"], 0), kategorien=[_kategorie(k, b["color"] or "") for k in ks])
                for b, ks in _gliedern(zeilen)]
    regale = [Regal(id=z["id"], name=z["name"], zeichen=zeichen(z["icon"]), farbe=z["color"] or "", anzahl=z["anzahl"],
                    spezial=bool(z["spezial"])) for z in zeilen if z["art"] == "regal"]
    ohne = await db.fetch_one(f"SELECT COUNT(*) AS n FROM books b WHERE NOT {merkmale.IN_KATEGORIE}")
    return KatalogAntwort(bereiche=bereiche, regale=regale, ohne_kategorie=ohne["n"] if ohne else 0,
                          hat_katalog=any(z["art"] != "regal" for z in zeilen))


async def bereich(nr: int) -> Bereich:
    for b in (await katalog()).bereiche:
        if b.id == nr:
            return b
    raise Fehlt(BEREICH_FEHLT)


async def kategorie(nr: int) -> Kategorie:
    for b in (await katalog()).bereiche:
        for k in b.kategorien:
            if k.id == nr:
                return k
    raise Fehlt(KATEGORIE_FEHLT)


async def als_datei() -> Katalog:
    """Der gültige Katalog im Format des Standards, zum Sichern und Teilen; Kategorien ohne eigene Farbe ohne Farbe."""
    bereiche = []
    for b, ks in _gliedern(await _zeilen()):
        kategorien = [Katalogkategorie(schluessel=k["schluessel"], name=k["name"], zeichen=zeichen(k["icon"]), farbe=k["color"] or "",
                                       ki_beschreibung=k["ki_beschreibung"], regeln=regeln_aus(k["regeln"]), verborgen=bool(k["verborgen"]),
                                       herkunft=k["herkunft"] or None) for k in ks]
        bereiche.append(Katalogbereich(schluessel=b["schluessel"], name=b["name"], zeichen=zeichen(b["icon"]), farbe=b["color"] or "#6b7280",
                                       beschreibung=b["description"] or "", arten=arten_aus(b["arten"]) or [BUCH],
                                       verborgen=bool(b["verborgen"]), herkunft=b["herkunft"] or None, kategorien=kategorien))
    return Katalog(bereiche=bereiche)


async def zum_einordnen() -> list[Einordnungskategorie]:
    """Die sichtbaren Kategorien sichtbarer Bereiche, mit den Arten ihres Bereichs."""
    zeilen = await db.fetch_all("""SELECT k.id, k.schluessel, k.name, k.ki_beschreibung, k.regeln, p.arten FROM categories k
                                   JOIN categories p ON p.id = k.parent_id AND p.art = 'bereich'
                                   WHERE k.art = 'kategorie' AND k.verborgen = 0 AND p.verborgen = 0
                                   ORDER BY p.sort_order, p.id, k.sort_order, k.id""")
    return [Einordnungskategorie(id=z["id"], schluessel=z["schluessel"], name=z["name"], ki_beschreibung=z["ki_beschreibung"],
                                 regeln=regeln_aus(z["regeln"]), arten=arten_aus(z["arten"])) for z in zeilen]


async def kategorien_eines_buchs(buch: int) -> list[dict]:
    """Kategorien und Regale eines Buchs mit Art, Zeichen, Farbe (bei Kategorien die geerbte) und dem Namen des Bereichs."""
    zeilen = await db.fetch_all("""SELECT c.id, c.name, c.slug, c.art, c.icon, COALESCE(NULLIF(c.color, ''), p.color, '') AS farbe,
                                          p.name AS bereich
                                   FROM book_categories x JOIN categories c ON c.id = x.category_id
                                   LEFT JOIN categories p ON p.id = c.parent_id AND c.art = 'kategorie' AND p.art = 'bereich'
                                   WHERE x.book_id = ? ORDER BY c.art != 'kategorie', c.name COLLATE NOCASE""", (buch,))
    return [{"id": z["id"], "name": z["name"], "slug": z["slug"], "art": z["art"], "zeichen": zeichen(z["icon"]), "farbe": z["farbe"],
             "bereich": z["bereich"]} for z in zeilen]


# -- einen Entwurf annehmen -------------------------------------------------------------------------------------------------

async def annehmen(k: Katalog) -> None:
    """Schreibt den Katalog: gleicher Schlüssel ändert, sonst anlegen; was nicht im Entwurf steht, bleibt unberührt."""
    async with db.einheit():
        for stelle, b in enumerate(k.bereiche):
            bereich_nr = await _bereich_schreiben(b, stelle)
            for stelle_k, kat in enumerate(b.kategorien):
                await _kategorie_schreiben(kat, bereich_nr, b.farbe, stelle_k)


async def _nummer(art: str, schluessel: str) -> int | None:
    z = await db.fetch_one("SELECT id FROM categories WHERE art = ? AND schluessel = ?", (art, schluessel))
    return z["id"] if z else None


async def _bereich_schreiben(b: Katalogbereich, stelle: int) -> int:
    werte = {"name": b.name, "icon": b.zeichen, "color": b.farbe, "description": b.beschreibung, "arten": json.dumps(b.arten),
             "verborgen": int(b.verborgen), "herkunft": b.herkunft or herkunft(b.schluessel), "sort_order": stelle}
    return await _schreiben("bereich", b.schluessel, werte)


async def _kategorie_schreiben(k: Katalogkategorie, bereich_nr: int, bereichsfarbe: str, stelle: int) -> int:
    werte = {"name": k.name, "icon": k.zeichen, "color": eigene_farbe(k.farbe, bereichsfarbe), "ki_beschreibung": k.ki_beschreibung,
             "regeln": k.regeln.model_dump_json(), "verborgen": int(k.verborgen), "herkunft": k.herkunft or herkunft(k.schluessel),
             "parent_id": bereich_nr, "sort_order": stelle}
    return await _schreiben("kategorie", k.schluessel, werte)


async def _schreiben(art: str, schluessel: str, werte: dict) -> int:
    """Ändern, wenn es den Schlüssel gibt, sonst anlegen; die Spalten kommen nur aus dem Code."""
    nr = await _nummer(art, schluessel)
    if nr is not None:
        await db.execute(f"UPDATE categories SET {', '.join(f'{s} = ?' for s in werte)} WHERE id = ?", (*werte.values(), nr))
        return nr
    alle = {**werte, "art": art, "schluessel": schluessel, "slug": SLUG + schluessel, "spezial": 0}
    c = await db.execute(f"INSERT INTO categories ({', '.join(alle)}) VALUES ({', '.join('?' * len(alle))})", tuple(alle.values()))
    return c.lastrowid


# -- einzeln anlegen und ändern ---------------------------------------------------------------------------------------------

async def _zeile(nr: int, art: str, meldung: str) -> dict:
    z = await db.fetch_one(f"SELECT {SPALTEN} FROM categories c WHERE c.id = ? AND c.art = ?", (nr, art))
    if z is None:
        raise Fehlt(meldung)
    return z


async def _vergebene_schluessel() -> set[str]:
    return {z["schluessel"] for z in await db.fetch_all("SELECT schluessel FROM categories WHERE art != 'regal'")}


async def _naechste_stelle(wo: str, werte: tuple) -> int:
    z = await db.fetch_one(f"SELECT MAX(sort_order) AS n FROM categories WHERE {wo}", werte)
    return (z["n"] if z and z["n"] is not None else -1) + 1


async def _name_frei(name: str, art: str, bereich_nr: int | None, ausser: int | None = None) -> None:
    oben = "parent_id IS ?" if art == "kategorie" else "1"
    werte = (name, art, bereich_nr, ausser) if art == "kategorie" else (name, art, ausser)
    if await db.fetch_one(f"SELECT id FROM categories WHERE name = ? COLLATE NOCASE AND art = ? AND {oben} AND id IS NOT ?", werte):
        raise Vergeben("Einen Bereich mit diesem Namen gibt es schon" if art == "bereich"
                       else "Eine Kategorie mit diesem Namen gibt es in diesem Bereich schon")


async def bereich_anlegen(e: BereichEingabe) -> Bereich:
    await _name_frei(e.name, "bereich", None)
    schluessel = freier_schluessel(schluesselteil(e.name), await _vergebene_schluessel())
    werte = {"name": e.name, "icon": e.zeichen, "color": e.farbe, "description": e.beschreibung, "arten": json.dumps(e.arten),
             "verborgen": int(e.verborgen), "herkunft": "eigen", "sort_order": await _naechste_stelle("art = 'bereich'", ())}
    return await bereich(await _schreiben("bereich", schluessel, werte))


async def bereich_aendern(nr: int, a: BereichAenderung) -> Bereich:
    await _zeile(nr, "bereich", BEREICH_FEHLT)
    felder = a.model_dump(exclude_none=True)
    if "name" in felder:
        await _name_frei(felder["name"], "bereich", None, nr)
    spalten = {"name": "name", "zeichen": "icon", "farbe": "color", "beschreibung": "description", "arten": "arten", "verborgen": "verborgen"}
    werte = {spalten[f]: json.dumps(w) if f == "arten" else int(w) if f == "verborgen" else w for f, w in felder.items()}
    if werte:
        await db.execute(f"UPDATE categories SET {', '.join(f'{s} = ?' for s in werte)} WHERE id = ?", (*werte.values(), nr))
    return await bereich(nr)


async def kategorie_anlegen(e: KategorieEingabe) -> Kategorie:
    b = await _zeile(e.bereich_id, "bereich", BEREICH_FEHLT)
    await _name_frei(e.name, "kategorie", b["id"])
    schluessel = freier_schluessel(f"{b['schluessel']}/{schluesselteil(e.name)}", await _vergebene_schluessel())
    werte = {"name": e.name, "icon": e.zeichen, "color": eigene_farbe(e.farbe, b["color"]), "ki_beschreibung": e.ki_beschreibung,
             "regeln": e.regeln.model_dump_json(), "verborgen": int(e.verborgen), "herkunft": "eigen", "parent_id": b["id"],
             "sort_order": await _naechste_stelle("art = 'kategorie' AND parent_id = ?", (b["id"],))}
    return await kategorie(await _schreiben("kategorie", schluessel, werte))


async def kategorie_aendern(nr: int, a: KategorieAenderung) -> Kategorie:
    k = await _zeile(nr, "kategorie", KATEGORIE_FEHLT)
    felder = a.model_dump(exclude_none=True)
    bereich_nr = felder.get("bereich_id", k["parent_id"])
    b = await _zeile(bereich_nr, "bereich", BEREICH_FEHLT)
    if "name" in felder or "bereich_id" in felder:
        await _name_frei(felder.get("name", k["name"]), "kategorie", bereich_nr, nr)
    werte: dict[str, object] = {}
    if "bereich_id" in felder:
        werte["parent_id"] = bereich_nr
    for feld, spalte in (("name", "name"), ("zeichen", "icon"), ("ki_beschreibung", "ki_beschreibung")):
        if feld in felder:
            werte[spalte] = felder[feld]
    if "farbe" in felder or "bereich_id" in felder:
        werte["color"] = eigene_farbe(felder.get("farbe", k["color"] or ""), b["color"])
    if a.regeln is not None:
        werte["regeln"] = a.regeln.model_dump_json()
    if a.verborgen is not None:
        werte["verborgen"] = int(a.verborgen)
    if werte:
        await db.execute(f"UPDATE categories SET {', '.join(f'{s} = ?' for s in werte)} WHERE id = ?", (*werte.values(), nr))
    return await kategorie(nr)


# -- löschen ----------------------------------------------------------------------------------------------------------------

async def _folgen(name: str, kategorien: list[int], anzahl_kategorien: int) -> Loeschfolgen:
    if not kategorien:
        return Loeschfolgen(name=name, buecher=0, vorschlaege=0, kategorien=anzahl_kategorien, titel=[])
    ph = ",".join("?" * len(kategorien))
    buecher = await db.fetch_one(f"SELECT COUNT(DISTINCT book_id) AS n FROM book_categories WHERE category_id IN ({ph})", tuple(kategorien))
    offen = await db.fetch_one(f"SELECT COUNT(*) AS n FROM katalog_vorschlag WHERE category_id IN ({ph}) AND stand = 'offen'", tuple(kategorien))
    titel = await db.fetch_all(f"""SELECT DISTINCT b.title FROM books b JOIN book_categories x ON x.book_id = b.id
                                   WHERE x.category_id IN ({ph}) ORDER BY b.title COLLATE NOCASE LIMIT ?""",
                               (*kategorien, TITEL_IN_DEN_FOLGEN))
    return Loeschfolgen(name=name, buecher=buecher["n"], vorschlaege=offen["n"], kategorien=anzahl_kategorien, titel=[t["title"] for t in titel])


async def loeschfolgen_kategorie(nr: int) -> Loeschfolgen:
    k = await _zeile(nr, "kategorie", KATEGORIE_FEHLT)
    return await _folgen(k["name"], [nr], 0)


async def loeschfolgen_bereich(nr: int) -> Loeschfolgen:
    b = await _zeile(nr, "bereich", BEREICH_FEHLT)
    kategorien = [z["id"] for z in await db.fetch_all("SELECT id FROM categories WHERE art = 'kategorie' AND parent_id = ?", (nr,))]
    return await _folgen(b["name"], kategorien, len(kategorien))


async def kategorie_loeschen(nr: int) -> None:
    """Die Kategorie mit ihren Zuordnungen und Vorschlägen; die Bücher bleiben."""
    await _zeile(nr, "kategorie", KATEGORIE_FEHLT)
    async with db.einheit():
        await db.execute("DELETE FROM book_categories WHERE category_id = ?", (nr,))
        await db.execute("DELETE FROM katalog_vorschlag WHERE category_id = ?", (nr,))
        await db.execute("DELETE FROM categories WHERE id = ?", (nr,))


async def bereich_loeschen(nr: int) -> None:
    await _zeile(nr, "bereich", BEREICH_FEHLT)
    if await db.fetch_one("SELECT id FROM categories WHERE art = 'kategorie' AND parent_id = ?", (nr,)):
        raise HatKategorien("Der Bereich hat noch Kategorien")
    await db.execute("DELETE FROM categories WHERE id = ?", (nr,))


# -- Treffer der Regeln -----------------------------------------------------------------------------------------------------

def zaehlen(pruefer: Pruefer, buecher: list[merkmale.Buchmerkmale]) -> tuple[Counter, int]:
    """Je Art der Regeln die Bücher, die sie trifft, und wie viele irgendeine trifft."""
    je_art: Counter = Counter()
    zusammen = 0
    for b in buecher:
        arten = {t.art for t in pruefer.treffer(b.suchtext())}
        je_art.update(arten)
        zusammen += bool(arten)
    return je_art, zusammen


async def treffer(nr: int) -> Treffer:
    """Was die Regeln der Kategorie im Bestand treffen, unter den Werken der Arten ihres Bereichs."""
    k = await _zeile(nr, "kategorie", KATEGORIE_FEHLT)
    b = await _zeile(k["parent_id"], "bereich", BEREICH_FEHLT)
    regeln = regeln_aus(k["regeln"])
    wo, werte = merkmale.nur_arten(arten_aus(b["arten"]))
    je_art, zusammen = await asyncio.to_thread(zaehlen, Pruefer(regeln), await merkmale.laden(wo, werte))
    ki = await db.fetch_one("SELECT COUNT(*) AS n FROM katalog_vorschlag WHERE category_id = ? AND stand = 'offen' AND quelle != 'regel'", (nr,))
    return Treffer(regeln=[Regelzahl(art=a, werte=regeln.werte(a), treffer=je_art[a]) for a in REGELARTEN], zusammen=zusammen,
                   ki_vorschlaege=ki["n"])
