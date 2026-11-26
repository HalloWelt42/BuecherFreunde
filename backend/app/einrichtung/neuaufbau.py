"""Neuaufbau aus der Kellerwolke ohne Sicherung (BF-82): aus den Originalen in einem Ordner und ihren Begleitern je Buch entstehen
Bücher, Angaben, Volltext und Umschläge (Auszug) und das Persönliche je Profil (Begleiter `persoenlich`, sonst was ein alter Auszug
davon trägt); die Profile kommen vorher aus ihrer Datei (ohne PIN).

`ordner_pruefen` sieht den Ordner einmal durch (Original ist jede Buchdatei ohne Rolle, ihr Auszug der Begleiter `auszug`) und
legt die Liste in `neuaufbau_datei` an; in der Kellerwolke ändert sich dabei nichts. Der Auftrag arbeitet sie Buch für Buch ab,
fortsetzbar. Ein Buch, das es schon gibt (gleiche Prüfsumme), bleibt, wie es ist. Ein Original ohne Auszug kommt mit den
Angaben aus seinem Namen in den Bestand ("Titel - Autor [Nummer]"); Volltext und Angaben entstehen dann neu aus der Datei
(Bibliothek ergänzen), Persönliches gibt es dafür keins. Die Nummer eines Buchs bleibt die aus dem Auszug oder dem Namen, wenn
sie frei ist. Gelöscht wird nichts."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from pathlib import PurePosixPath

from backend.app.ablage import auszug, persoenlich
from backend.app.ablage.auszug import Angaben
from backend.app.ablage.persoenlich import Persoenliches
from backend.app.ablage.wolke import wolke
from backend.app.annahme.eintragen import autoren_verknuepfen
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.core.suchindex import SUCHTEXT_ZEICHEN
from backend.app.einrichtung import katalog_schritt, profildatei, zustand
from backend.app.einrichtung.auftrag import Auftrag, Ruhen
from backend.app.einrichtung.modelle import Neuaufbaubericht, Ohneauszug, Ordnerpruefung, Teil
from backend.app.einrichtung.zustand import Einrichtungsfehler
from backend.app.services.storage import SUPPORTED_FORMATS, get_storage_path

NAME = re.compile(r"^(?P<titel>.*?)(?: - (?P<autor>.*?))? \[(?P<nr>\d+)\]$")
TEILE = (("buecher", "Bücher"), ("angaben", "Angaben"), ("volltext", "Volltext"), ("umschlaege", "Umschläge"), ("persoenliches", "Persönliches"))
# Spalten aus dem Auszug, die der Neuaufbau selbst setzt
EIGENE = {"id", "hash", "fts_content", "storage_path"}


async def _unterordner(knoten: str, name: str) -> dict | None:
    async for k in wolke.kinder(knoten):
        if k.get("typ") == "ordner" and k.get("name") == name:
            return k
    return None


async def ordner_finden(pfad: str) -> dict:
    """Ein Ordner unter dem der App, ohne etwas anzulegen; fehlt er: 404."""
    k = await wolke.ordner(settings.ablage_ordner)
    for teil in (t for t in pfad.split("/") if t.strip()):
        k = await _unterordner(k["id"], teil.strip())
        if k is None:
            raise Einrichtungsfehler(f"Den Ordner {pfad} gibt es in der Kellerwolke nicht", 404)
    return k


async def _durch(knoten: str, pfad: str) -> AsyncIterator[dict]:
    async for k in wolke.kinder(knoten):
        if k.get("typ") == "ordner":
            async for unten in _durch(k["id"], f"{pfad}/{k['name']}"):
                yield unten
        elif k.get("typ") == "datei":
            yield k | {"pfad": k.get("pfad") or f"{pfad}/{k['name']}"}


async def _sammeln(pfad: str) -> tuple[list[dict], dict[str, dict[str, str]]]:
    """Die Originale und je Rolle (`auszug`, `persoenlich`) ihre Begleiter, aus einem Durchgang durch die Liste."""
    ordner = await ordner_finden(pfad)
    originale, begleiter = [], {"auszug": {}, persoenlich.ROLLE: {}}
    async for k in _durch(ordner["id"], f"{settings.ablage_ordner}/{pfad}".rstrip("/")):
        if k.get("rolle") in begleiter and k.get("haupt_id"):
            begleiter[k["rolle"]][k["haupt_id"]] = k["id"]
        elif not k.get("haupt_id") and not k.get("rolle") and PurePosixPath(k["name"]).suffix.lower() in SUPPORTED_FORMATS:
            originale.append(k)
    return originale, begleiter


async def ordner_pruefen(pfad: str) -> Ordnerpruefung:
    """Zählt, was im Ordner liegt, und merkt die Liste für den Auftrag; Einträge eines früheren Laufs bleiben."""
    z = await zustand.nur_neu()
    if z["ausgangslage"] != "kellerwolke":
        raise Einrichtungsfehler("Den Neuaufbau gibt es nur in der Ausgangslage \"Ablage in der Kellerwolke übernehmen\"")
    if not wolke.bereit:
        raise Einrichtungsfehler("Erst die Kellerwolke mit Adresse und Schlüssel eintragen")
    originale, begleiter = await _sammeln(pfad)
    auszuege = begleiter["auszug"]
    for k in originale:
        await db.execute("INSERT INTO neuaufbau_datei(knoten, name, pfad, groesse, sha256, auszug, persoenlich) VALUES (?, ?, ?, ?, ?, ?, ?) "
                         "ON CONFLICT(knoten) DO UPDATE SET auszug = excluded.auszug, persoenlich = excluded.persoenlich WHERE stand = 'offen'",
                         (k["id"], k["name"], k["pfad"], k.get("groesse") or 0, k.get("sha256") or "", auszuege.get(k["id"]),
                          begleiter[persoenlich.ROLLE].get(k["id"])))
    await db.commit()
    pruefsummen = [k.get("sha256") for k in originale if k.get("sha256")]
    schon = 0
    for stueck in range(0, len(pruefsummen), 500):
        teil = pruefsummen[stueck:stueck + 500]
        schon += (await db.fetch_one(f"SELECT COUNT(*) AS n FROM books WHERE hash IN ({','.join('?' * len(teil))})", tuple(teil)))["n"]
    datei = await profildatei.lesen()
    mit = sum(1 for k in originale if k["id"] in auszuege)
    await zustand.vermerken("ordner", text=f"{pfad}: {len(originale)} Bücher, {mit} mit Auszug")
    return Ordnerpruefung(pfad=pfad, buecher=len(originale), mit_auszug=mit, ohne_auszug=len(originale) - mit, schon_da=schon,
                          mit_persoenlichem=sum(1 for k in originale if k["id"] in begleiter[persoenlich.ROLLE]),
                          groesse=sum(k.get("groesse") or 0 for k in originale), profile=[p.name for p in datei.profile] if datei else [],
                          profile_datei=datei is not None)


# -- Profile ------------------------------------------------------------------------------------------------------------

async def profile_einspielen() -> dict[str, str]:
    """Die Profile aus ihrer Datei, ohne PIN. Das Profil Verwaltung, das mit dem Konto entstand und noch nichts hat, übernimmt das
    erste Verwaltungsprofil der Datei (Name aus dem Konto bleibt). Antwortet, welche Kennung der Datei welchem Profil entspricht."""
    datei = await profildatei.lesen()
    if datei is None:
        return {}
    abbildung: dict[str, str] = {}
    eigene = await db.fetch_all("SELECT id FROM profil WHERE rolle = 'verwaltung' ORDER BY sortierung, angelegt_am")
    erste = next((p for p in datei.profile if p.rolle == "verwaltung"), None)
    if erste and len(eigene) == 1 and not await db.fetch_one("SELECT 1 FROM profil WHERE id = ?", (erste.id,)):
        abbildung[erste.id] = eigene[0]["id"]
        await db.execute("UPDATE profil SET zeichen = ?, farbe = ?, einstellungen = ?, sortierung = ? WHERE id = ?",
                         (erste.zeichen, erste.farbe, erste.einstellungen.model_dump_json(), erste.sortierung, eigene[0]["id"]))
    for p in datei.profile:
        if p.id in abbildung:
            continue
        await db.execute("INSERT OR IGNORE INTO profil(id, name, zeichen, farbe, rolle, geburtsjahr, stufe, einstellungen, sortierung) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (p.id, p.name, p.zeichen, p.farbe, p.rolle, p.geburtsjahr, p.stufe,
                                                               p.einstellungen.model_dump_json(), p.sortierung))
        abbildung[p.id] = p.id
    if datei.stimme:
        await db.execute("INSERT INTO app_settings(key, value) VALUES ('familie_stimme', ?) ON CONFLICT(key) DO NOTHING", (datei.stimme,))
    await db.commit()
    return abbildung


async def _kategorien_freigeben(abbildung: dict[str, str]) -> None:
    datei = await profildatei.lesen()
    for f in datei.freigaben if datei else []:
        k = await db.fetch_one("SELECT id FROM categories WHERE (schluessel = ? AND ? != '') OR name = ? ORDER BY schluessel = ? DESC LIMIT 1",
                               (f.schluessel, f.schluessel, f.name, f.schluessel))
        if k and f.profil in abbildung:
            await db.execute("INSERT OR IGNORE INTO freigabe(profil_id, art, ziel_id) VALUES (?, 'kategorie', ?)", (abbildung[f.profil], k["id"]))
    await db.commit()


# -- ein Buch -----------------------------------------------------------------------------------------------------------

async def _spalten() -> set[str]:
    return {z["name"] for z in await db.fetch_all("PRAGMA table_info(books)")}


def _aus_dem_namen(name: str) -> dict:
    stamm, endung = PurePosixPath(name).stem, PurePosixPath(name).suffix.lower().lstrip(".")
    m = NAME.match(stamm)
    return {"title": (m["titel"] if m else stamm) or stamm, "author": (m["autor"] or "") if m else "", "id": int(m["nr"]) if m else None,
            "file_format": endung, "file_name": name}


async def _buch_anlegen(sha: str, e: dict, angaben: Angaben | None, volltext: str) -> int:
    """Die Zeile aus dem Auszug (nur Spalten, die es gibt), sonst aus dem Namen; die Nummer bleibt, wenn sie frei ist."""
    if angaben:
        spalten = await _spalten()
        zeile = {k: v for k, v in angaben.buch.items() if k in spalten and k not in EIGENE}
        wunsch = angaben.buch.get("id")
    else:
        zeile = _aus_dem_namen(e["name"])
        wunsch = zeile.pop("id")
    zeile |= {"hash": sha, "storage_path": str(get_storage_path(sha)), "fts_content": volltext[:SUCHTEXT_ZEICHEN]}
    zeile.setdefault("file_size", e["groesse"])
    zeile.setdefault("file_format", PurePosixPath(e["name"]).suffix.lower().lstrip("."))
    zeile.setdefault("file_name", e["name"])
    if isinstance(wunsch, int) and not await db.fetch_one("SELECT 1 FROM books WHERE id = ?", (wunsch,)):
        zeile["id"] = wunsch
    namen = list(zeile)
    c = await db.execute(f"INSERT INTO books ({', '.join(namen)}) VALUES ({', '.join('?' * len(namen))})", tuple(zeile[n] for n in namen))
    buch = c.lastrowid
    await db.execute("UPDATE books SET fts_content = '' WHERE id = ?", (buch,))         # steht im Suchindex
    await autoren_verknuepfen(buch, zeile.get("author") or "")
    return buch


async def _kategorien(buch: int, namen: list[str]) -> None:
    for name in namen:
        k = await db.fetch_one("SELECT id FROM categories WHERE name = ? ORDER BY art = 'regal' DESC, id LIMIT 1", (name,))
        if k is None:
            slug = re.sub(r"[-\s]+", "-", re.sub(r"[^\w\s-]", "", name.lower())).strip("-") or "regal"
            while await db.fetch_one("SELECT 1 FROM categories WHERE slug = ?", (slug,)):
                slug += "-1"
            k = {"id": (await db.execute("INSERT INTO categories(name, slug) VALUES (?, ?)", (name, slug))).lastrowid}
        await db.execute("INSERT OR IGNORE INTO book_categories(book_id, category_id, quelle) VALUES (?, ?, 'manuell')", (buch, k["id"]))


async def _persoenliches(buch: int, je: dict[str, Persoenliches], abbildung: dict[str, str]) -> bool:
    """Nur für Profile, die es gibt; Daten ohne Profil (alte Auszüge) gehören dem ersten Profil Verwaltung."""
    erste = await db.fetch_one("SELECT id FROM profil WHERE rolle = 'verwaltung' ORDER BY sortierung, angelegt_am LIMIT 1")
    da = False
    for kennung, p in je.items():
        pid = abbildung.get(kennung) or (kennung if await db.fetch_one("SELECT 1 FROM profil WHERE id = ?", (kennung,)) else None)
        pid = pid or (erste["id"] if not kennung and erste else None)
        if pid is None:
            continue
        da = True
        if p.lesestand:
            l = p.lesestand.model_dump()
            await db.execute(f"INSERT OR REPLACE INTO user_book_data(profil_id, book_id, {', '.join(l)}) VALUES (?, ?, {', '.join('?' * len(l))})",
                             (pid, buch, *l.values()))
        if p.vorlesestelle:
            v = p.vorlesestelle.model_dump(exclude_none=True)
            await db.execute(f"INSERT OR REPLACE INTO vorlesestelle(profil_id, buch_id, {', '.join(v)}) VALUES (?, ?, {', '.join('?' * len(v))})",
                             (pid, buch, *v.values()))
        for tabelle, liste in (("book_notes", p.notizen), ("book_highlights", p.markierungen), ("book_labels", p.etiketten)):
            for eintrag in liste:
                w = eintrag.model_dump(exclude_none=True)
                await db.execute(f"INSERT INTO {tabelle}(profil_id, book_id, {', '.join(w)}) VALUES (?, ?, {', '.join('?' * len(w))})",
                                 (pid, buch, *w.values()))
        if p.privat:
            await db.execute("INSERT OR IGNORE INTO buch_privat(profil_id, book_id) VALUES (?, ?)", (pid, buch))
        if p.freigegeben:
            await db.execute("INSERT OR IGNORE INTO freigabe(profil_id, art, ziel_id) VALUES (?, 'buch', ?)", (pid, buch))
    return da


async def _persoenliches_lesen(e: dict, gelesen: auszug.Gelesen | None) -> dict[str, Persoenliches]:
    """Der Begleiter `persoenlich` gilt; ohne ihn, was ein alter Auszug an Persönlichem trägt."""
    if e["persoenlich"]:
        return persoenlich.lesen(await wolke.inhalt(e["persoenlich"])).profile
    return gelesen.angaben.persoenliches() if gelesen and gelesen.angaben else {}


class Neuaufbau(Auftrag):
    art = "neuaufbau"
    was = "Neuaufbau aus der Kellerwolke"

    async def zaehlen(self) -> tuple[int, int, list[Teil]]:
        z = await db.fetch_one(
            "SELECT COUNT(*) AS gesamt, COALESCE(SUM(stand != 'offen'), 0) AS fertig, COALESCE(SUM(book_id IS NOT NULL), 0) AS buecher, "
            "COALESCE(SUM(auszug IS NOT NULL), 0) AS mit, COALESCE(SUM(auszug IS NOT NULL AND stand = 'fertig'), 0) AS angaben, "
            "COALESCE(SUM(' ' || teile || ' ' LIKE '% volltext %'), 0) AS volltext, COALESCE(SUM(' ' || teile || ' ' LIKE '% umschlag %'), 0) AS umschlaege, "
            "COALESCE(SUM(' ' || teile || ' ' LIKE '% persoenliches %'), 0) AS persoenliches, "
            "COALESCE(SUM(auszug IS NOT NULL OR persoenlich IS NOT NULL), 0) AS mit_persoenlichem FROM neuaufbau_datei")
        gesamt = {"buecher": z["gesamt"], "angaben": z["mit"], "volltext": z["mit"], "umschlaege": z["mit"], "persoenliches": z["mit_persoenlichem"]}
        return z["gesamt"], z["fertig"], [Teil(schluessel=k, name=n, gesamt=gesamt[k], fertig=z[k]) for k, n in TEILE]

    async def vorbereiten(self) -> None:
        """Gescheiterte noch einmal; ohne Katalog zuerst der mitgelieferte, damit die Kategorien der Auszüge ihre Namen finden."""
        if not await db.fetch_one("SELECT 1 FROM neuaufbau_datei LIMIT 1"):
            raise Einrichtungsfehler("Erst den Ordner der Bücher prüfen")
        if not await db.fetch_one("SELECT 1 FROM categories WHERE art = 'kategorie' LIMIT 1"):
            await katalog_schritt.anwenden("standard")
        await db.execute("UPDATE neuaufbau_datei SET stand = 'offen', text = '', teile = '' WHERE stand = 'fehler'")
        await db.commit()

    async def _abbildung(self) -> dict[str, str]:
        angaben = await self.angaben()
        if "abbildung" not in angaben:
            angaben["abbildung"] = await profile_einspielen()
            await db.execute("UPDATE einrichtung_auftrag SET angaben = ? WHERE art = ?", (json.dumps(angaben), self.art))
            await db.commit()
        return angaben["abbildung"]

    async def naechstes(self) -> bool:
        if not wolke.bereit:
            raise Ruhen("Die Kellerwolke ist nicht eingetragen")
        abbildung = await self._abbildung()
        e = await db.fetch_one("SELECT * FROM neuaufbau_datei WHERE stand = 'offen' ORDER BY pfad, name LIMIT 1")
        if e is None:
            return False
        sha = e["sha256"] or str((await wolke.knoten(e["knoten"])).get("sha256") or "")
        da = await db.fetch_one("SELECT id FROM books WHERE hash = ?", (sha,)) if sha else None
        if not sha or da:
            await db.execute("UPDATE neuaufbau_datei SET stand = ?, book_id = ?, text = ? WHERE knoten = ?",
                             ("da" if da else "fehler", da["id"] if da else None, "gibt es schon" if da else "ohne Prüfsumme", e["knoten"]))
            await db.commit()
            return True
        gelesen = auszug.lesen(await wolke.inhalt(e["auszug"])) if e["auszug"] else None
        je = await _persoenliches_lesen(e, gelesen)
        volltext = gelesen.dateien.get("fulltext.txt", b"").decode("utf-8", "replace") if gelesen else ""
        if gelesen:
            await asyncio.to_thread(auszug.dateien_ablegen, sha, gelesen, False)
        teile = [n for n, ja in (("volltext", "fulltext.txt" in (gelesen.dateien if gelesen else {})),
                                 ("umschlag", "cover.jpg" in (gelesen.dateien if gelesen else {}))) if ja]
        async with db.einheit():                             # Buch, Ablage, Regale und Persönliches gelten zusammen oder gar nicht
            buch = await _buch_anlegen(sha, e, gelesen.angaben if gelesen else None, volltext)
            await db.execute("INSERT OR REPLACE INTO ablage_datei(hash, knoten, name, pfad, groesse, begleiter) VALUES (?, ?, ?, ?, ?, ?)",
                             (sha, e["knoten"], e["name"], e["pfad"], e["groesse"], e["auszug"]))
            if gelesen and gelesen.angaben:
                await _kategorien(buch, gelesen.angaben.kategorien)
            if await _persoenliches(buch, je, abbildung):
                teile.append("persoenliches")
            await db.execute("DELETE FROM nachfuehren WHERE art = 'buch' AND ziel = ?", (buch,))      # steht schon so in der Kellerwolke
            await db.execute("UPDATE neuaufbau_datei SET stand = 'fertig', book_id = ?, teile = ?, text = ? WHERE knoten = ?",
                             (buch, " ".join(teile), "" if gelesen else "ohne Auszug", e["knoten"]))
        return True

    async def danach(self) -> None:
        await _kategorien_freigeben(await self._abbildung())


neuaufbau = Neuaufbau()


async def bericht() -> Neuaufbaubericht:
    ohne = await db.fetch_all("SELECT book_id, name, pfad FROM neuaufbau_datei WHERE auszug IS NULL ORDER BY pfad, name")
    fehler = await db.fetch_all("SELECT book_id, name, pfad, text FROM neuaufbau_datei WHERE stand = 'fehler' ORDER BY pfad, name")
    z = await db.fetch_one("SELECT COUNT(*) AS n, COALESCE(SUM(auszug IS NOT NULL), 0) AS mit FROM neuaufbau_datei")
    return Neuaufbaubericht(auftrag=await neuaufbau.stand(), buecher=z["n"], mit_auszug=z["mit"],
                            ohne_auszug=[Ohneauszug(buch_id=r["book_id"], name=r["name"], pfad=r["pfad"]) for r in ohne],
                            fehler=[Ohneauszug(buch_id=r["book_id"], name=r["name"], pfad=r["pfad"]) for r in fehler],
                            profile=(await db.fetch_one("SELECT COUNT(*) AS n FROM profil"))["n"])
