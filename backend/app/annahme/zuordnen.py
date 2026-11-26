"""Die Vorschläge der Regeln für die Vorschau (BF-80), sofort nach dem Lesen der Datei; die KI ergänzt danach im Hintergrund,
was offen blieb (annahme/ki_vorschau.py). Je Feld mit Herkunft:

- Doppel: dasselbe Buch in einem anderen Format im Bestand (gleiche ISBN, sonst gleicher Titel und erster Autor, nur Bücher,
  die niemand privat hat) ist als weiteres Format vorgewählt (`bestand`); dann zeigen die Felder das vorhandene Buch. In
  derselben Vorschau: dieselbe Datei noch einmal (weglassen) oder derselbe Name in einem anderen Format (weiteres Format zu
  der ersten, `datei`).
- Art: die festen Regeln (services/artregeln.py, `regel`), mit dem Befund des Umschlags wie im Bestand.
- Kategorie: ein Ordner in der ZIP, der wie eine Kategorie heißt (`ordner`), sonst die beste Regel des Katalogs für die Art
  (`regel`).
- Sammlung und Band: aus einer Lücke (`luecke`), aus einem Ordner, der wie eine Sammlung heißt (`ordner`), aus Reihe und Band
  im Titel (`regel`) oder im Dateinamen (`datei`), wie beim Finden von Sammlungen (services/sammlungsfinder.py). Bei einem Stapel
  in eine Sammlung ohne erkannten Band der Band, den die Quelle unter diesem Titel kennt (`luecke`, BF-75).
- Etiketten: Ordner in der ZIP, die keine Kategorie und keine Sammlung sind (`ordner`).
- Sprache: aus der Datei (`datei`), sonst aus der Lücke (`luecke`); widersprechen sie sich, steht ein Hinweis dabei.
- Hinweise einer Lücke (Herkunft `luecke`, BF-75): andere Sprache, ein anderer Band im Titel oder Dateinamen, ein anderer Titel als
  der, den die Quelle für die Lücke kennt (luecken/dienst.py)."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from backend.app.annahme.modelle import BUCH, Doppel, Gelesen, Hinweis, Vorgabe, Wert, Ziel, Zuordnung
from backend.app.core.database import db
from backend.app.katalog import kategorien, merkmale
from backend.app.katalog.einordnen import regelfunde, teile
from backend.app.katalog.merkmale import Buchmerkmale
from backend.app.katalog.regeln import Pruefer, klein
from backend.app.katalog.vorschlaege import teil_vor_ganzem, zusammenfuehren
from backend.app.luecken.dienst import abweichungen, band_nach_titel
from backend.app.material import zugehoerig
from backend.app.quellen.sprache import kuerzel, name as sprachname
from backend.app.services import artregeln
from backend.app.services.sammlungsfinder import autor_schluessel, erkennen, erster_autor, normiert, ohne_autor

ISBN_ZEICHEN = re.compile(r"[^0-9X]")


class Lage(BaseModel):
    """Was die Regeln außer dem Gelesenen über die Datei wissen."""

    aufnahme: int
    name: str
    sha256: str
    ordner: list[str]                            # Ordner in der ZIP, nur Hinweise
    zip_name: str = ""
    vorschau: str
    vorgabe: Vorgabe


def isbn(text: str) -> str:
    t = ISBN_ZEICHEN.sub("", (text or "").upper())
    return t if len(t) in (10, 13) else ""


def typ_als_art(typ: str | None) -> str:
    return typ or BUCH


async def _bestandsbuch(g: Gelesen) -> dict | None:
    """Dasselbe Buch im Bestand, das niemand privat hat: gleiche ISBN, sonst gleicher Titel und erster Autor."""
    frei = "b.id NOT IN (SELECT book_id FROM buch_privat)"
    titel, autor, nummer = normiert(g.titel), autor_schluessel(erster_autor(g.autor)), isbn(g.isbn)
    if not nummer and not (titel and autor):
        return None
    for z in await db.fetch_all(f"SELECT b.id, b.title, b.author, b.isbn FROM books b WHERE {frei}"):
        if (nummer and isbn(z["isbn"]) == nummer) or (titel and autor and normiert(z["title"]) == titel
                                                       and autor_schluessel(erster_autor(z["author"])) == autor):
            return await db.fetch_one("SELECT * FROM books WHERE id = ?", (z["id"],))
    return None


async def _aus_dem_bestand(b: dict, format_: str) -> Zuordnung | None:
    """Ein weiteres Format zu einem Buch im Bestand: die Felder zeigen das vorhandene Buch. None, wenn das Buch dieses Format
    schon hat (dann ist es eine andere Datei und kommt als eigenes Buch, mit Hinweis)."""
    formate = [z["format"] for z in await db.fetch_all("SELECT format FROM buch_datei WHERE buch_id = ? ORDER BY haupt DESC", (b["id"],))]
    if format_ in formate:
        return None
    kats = [z["category_id"] for z in await db.fetch_all("""SELECT x.category_id FROM book_categories x JOIN categories c ON c.id = x.category_id
                                                            WHERE x.book_id = ? AND c.art = 'kategorie'""", (b["id"],))]
    zo = Zuordnung(art=Wert[str](wert=typ_als_art(b["typ"]), herkunft="bestand"), kategorien=Wert[list[int]](wert=kats, herkunft="bestand"),
                   sammlung=Wert[int | None](wert=b["sammlung_id"], herkunft="bestand"), band=Wert[str](wert=b["band_nummer"] or "", herkunft="bestand"),
                   sprache=Wert[str](wert=kuerzel(b["language"]), herkunft="bestand"),
                   doppel=Doppel(art="format", wahl="format", herkunft="bestand", grund=f"zu {b['title']}, {', '.join(f.upper() for f in formate)}"),
                   ziel=Ziel(buch_id=b["id"], titel=b["title"]))
    return zo


async def _in_der_vorschau(lage: Lage, g: Gelesen) -> tuple[Doppel, Ziel] | None:
    """Eine frühere Aufnahme derselben Vorschau: dieselbe Datei (weglassen) oder derselbe Name, dasselbe Buch in einem anderen
    Format (weiteres Format zu ihr)."""
    format_ = Path(lage.name).suffix.lower().lstrip(".")
    for z in await db.fetch_all("""SELECT id, name, sha256, zip_pfad, gelesen FROM aufnahme WHERE vorschau = ? AND id < ? AND material_fuer IS NULL
                                   AND stand NOT IN ('verworfen', 'format', 'kaputt', 'fehler') ORDER BY id""", (lage.vorschau, lage.aufnahme)):
        if z["sha256"] and z["sha256"] == lage.sha256:
            return Doppel(art="gleich", wahl="weglassen", herkunft="datei", grund=f"gleiche Datei wie {z['name']}"), Ziel(aufnahme=z["id"], titel=z["name"])
        anderes = Path(z["name"]).suffix.lower().lstrip(".")
        if anderes == format_ or anderes == "zip":
            continue
        gleicher_ort = (Path(z["zip_pfad"] or z["name"]).parent == Path(_zip_pfad(lage)).parent)
        gleicher_name = gleicher_ort and zugehoerig.stamm(z["name"]).casefold() == zugehoerig.stamm(lage.name).casefold()
        frueher = Gelesen.model_validate_json(z["gelesen"]) if z["gelesen"] else None
        gleiches_buch = frueher is not None and normiert(frueher.titel) == normiert(g.titel) != "" \
            and autor_schluessel(erster_autor(frueher.autor)) == autor_schluessel(erster_autor(g.autor)) != ""
        if gleicher_name or gleiches_buch:
            return (Doppel(art="format", wahl="format", herkunft="datei", grund=f"zu {z['name']}, {anderes.upper()}"),
                    Ziel(aufnahme=z["id"], titel=frueher.titel if frueher else z["name"]))
    return None


def _zip_pfad(lage: Lage) -> str:
    return "/".join([*lage.ordner, lage.name])


def _art(lage: Lage, g: Gelesen) -> Wert[str]:
    w = artregeln.Werk(id=0, hash=lage.sha256, title=g.titel, author=g.autor, publisher=g.verlag, year=g.jahr, isbn=g.isbn,
                       file_format=Path(lage.name).suffix.lower().lstrip("."), file_name=lage.name, page_count=g.seiten,
                       umschlag_schlicht=None if g.umschlag_schlicht is None else int(g.umschlag_schlicht))
    u = artregeln.urteil(w)
    return Wert[str](wert=typ_als_art(u.typ), herkunft="regel", grund=u.grund) if u else Wert[str](wert="")


async def kategorie_nach_regeln(g: Gelesen, typ: str) -> Wert[list[int]]:
    """Die beste Regel des Katalogs für ein Werk dieser Art (books.typ, leer: Buch); passt es zu einem Teil einer großen
    Kategorie, der Teil."""
    kats = [k for k in await kategorien.zum_einordnen() if typ in k.arten]
    if not kats:
        return Wert[list[int]](wert=[])
    b = Buchmerkmale(id=1, titel=g.titel, autor=g.autor, verlag=g.verlag, typ=typ, beschreibung=g.beschreibung[:merkmale.BESCHREIBUNG_ZEICHEN])
    funde = teil_vor_ganzem(zusammenfuehren(regelfunde([b], [(k, Pruefer(k.regeln)) for k in kats]), {}), teile(kats))
    if not funde:
        return Wert[list[int]](wert=[])
    bester = max(funde, key=lambda f: f.sicherheit)
    return Wert[list[int]](wert=[bester.kategorie_id], herkunft="regel", grund=" und ".join(bester.gruende))


async def _ordner_als(ordner: list[str], zip_name: str) -> tuple[list[int], int | None, list[str]]:
    """Ordnernamen der ZIP: Kategorien, die so heißen, eine Sammlung, die so heißt, und der Rest als Etiketten."""
    kats = {klein(z["name"]): z["id"] for z in await db.fetch_all("SELECT id, name FROM categories WHERE art = 'kategorie' AND verborgen = 0")}
    sammlungen = {normiert(z["name"]): z["id"] for z in await db.fetch_all("SELECT id, name FROM collections")}
    gefunden, sammlung, etiketten = [], None, []
    for teil in ordner:
        if klein(teil) in kats:
            gefunden.append(kats[klein(teil)])
        elif normiert(teil) in sammlungen and sammlung is None:
            sammlung = sammlungen[normiert(teil)]
        elif normiert(teil) and normiert(teil) != normiert(zugehoerig.stamm(zip_name)):
            etiketten.append(teil)
    return list(dict.fromkeys(gefunden)), sammlung, list(dict.fromkeys(etiketten))


async def _sammlung(lage: Lage, g: Gelesen, aus_ordner: int | None) -> tuple[Wert[int | None], Wert[str]]:
    sammlungen = {normiert(z["name"]): z["id"] for z in await db.fetch_all("SELECT id, name FROM collections")}
    funde = [("regel", erkennen(g.titel)), ("datei", erkennen(ohne_autor(lage.name, autor_schluessel(erster_autor(g.autor)))))]
    sammlung: Wert[int | None] = Wert[int | None](wert=None)
    if lage.vorgabe.sammlung_id:
        sammlung = Wert[int | None](wert=lage.vorgabe.sammlung_id, herkunft="luecke")
    elif aus_ordner:
        sammlung = Wert[int | None](wert=aus_ordner, herkunft="ordner")
    else:
        for herkunft, e in funde:
            if e and normiert(e.reihe) in sammlungen:
                sammlung = Wert[int | None](wert=sammlungen[normiert(e.reihe)], herkunft=herkunft, grund=f"Reihe {e.reihe}")
                break
    band: Wert[str] = Wert[str](wert="")
    if lage.vorgabe.band:
        band = Wert[str](wert=lage.vorgabe.band, herkunft="luecke")
    elif sammlung.wert is not None:
        band = next((Wert[str](wert=e.band, herkunft=h, grund=f"Band {e.band} im {'Titel' if h == 'regel' else 'Dateinamen'}")
                     for h, e in funde if e), band)
    if not band.wert and lage.vorgabe.sammlung_id and (n := await band_nach_titel(lage.vorgabe.sammlung_id, g.sprache or lage.vorgabe.sprache, g.titel)):
        band = Wert[str](wert=str(n), herkunft="luecke", grund=f"Band {n} heißt in den Quellen so")      # ein Stapel in die Sammlung
    return sammlung, band


def _sprache(g: Gelesen, vorgabe: Vorgabe) -> tuple[Wert[str], list[Hinweis]]:
    datei, luecke = kuerzel(g.sprache), kuerzel(vorgabe.sprache)
    hinweise = [Hinweis(text=f"Die Datei ist {sprachname(datei)}, die Lücke {sprachname(luecke)}", herkunft="luecke")] \
        if datei and luecke and datei != luecke else []
    if datei:
        return Wert[str](wert=datei, herkunft="datei"), hinweise
    return (Wert[str](wert=luecke, herkunft="luecke") if luecke else Wert[str](wert="")), hinweise


async def _zur_luecke(lage: Lage, g: Gelesen) -> list[Hinweis]:
    """Passt die Datei nicht zu der Lücke, in die sie geladen wird (anderer Band, anderer Titel), steht es dabei."""
    v = lage.vorgabe
    if not (v.sammlung_id and v.band):
        return []
    return [Hinweis(text=t, herkunft="luecke") for t in await abweichungen(v.sammlung_id, v.band, v.sprache, g.titel, lage.name, g.autor)]


async def vorschlagen(lage: Lage, g: Gelesen) -> Zuordnung:
    """Die Zuordnung nach den Regeln, sofort; was offen bleibt, hat keine Herkunft."""
    format_ = Path(lage.name).suffix.lower().lstrip(".")
    hinweise: list[Hinweis] = []
    if b := await _bestandsbuch(g):
        if zo := await _aus_dem_bestand(b, format_):
            return zo
        hinweise.append(Hinweis(text=f"Im Bestand gibt es {b['title']} schon als {format_.upper()}, aus einer anderen Datei", herkunft="bestand"))
    kats_ordner, sammlung_ordner, etiketten = await _ordner_als(lage.ordner, lage.zip_name)
    art = _art(lage, g)
    kats = Wert[list[int]](wert=kats_ordner, herkunft="ordner") if kats_ordner else \
        (await kategorie_nach_regeln(g, "" if art.wert == BUCH else art.wert) if art.wert else Wert[list[int]](wert=[]))
    sammlung, band = await _sammlung(lage, g, sammlung_ordner)
    sprache, sprachhinweise = _sprache(g, lage.vorgabe)
    zo = Zuordnung(art=art, kategorien=kats, etiketten=Wert[list[str]](wert=etiketten, herkunft="ordner" if etiketten else None),
                   sammlung=sammlung, band=band, sprache=sprache, hinweise=hinweise + sprachhinweise + await _zur_luecke(lage, g))
    if doppelt := await _in_der_vorschau(lage, g):
        zo.doppel, zo.ziel = doppelt
    return zo


def ki_noetig(zo: Zuordnung) -> bool:
    """Ob die KI noch etwas ergänzen kann: Art oder Kategorie ohne Vorschlag, bei einem neuen Werk."""
    if zo.doppel.wahl in ("format", "weglassen") or zo.art.wert == "material" or zo.nicht:
        return False
    return zo.art.herkunft is None or (zo.kategorien.herkunft is None and not zo.kategorien.wert)

