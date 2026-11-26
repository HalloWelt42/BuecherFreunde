"""Die Vorschau vor dem Übernehmen (BF-80): eine Gruppe von Aufnahmen (ein Hochladen, eine ZIP, ein Weg wie der
Eingangsordner), die vor der Station Regal auf die Bestätigung wartet, auch über Tage und einen Neustart. Bis dahin ist nichts
im Regal, in der Suche oder in den Zählern.

Hier: anlegen, zeigen und ändern. Je Datei die Zuordnung mit Herkunft je Feld (annahme/modelle.py); was der Nutzer setzt,
heißt `nutzer` und überschreibt danach weder eine Regel noch die KI. Übernehmen steht in annahme/uebernehmen.py, Verwerfen in
annahme/verwerfen.py."""

from __future__ import annotations

import json
import posixpath
import uuid
from collections import Counter
from pathlib import Path

from backend.app.ablage.namen import fach, sauber
from backend.app.annahme.modelle import (
    BUCH, MATERIAL, NUTZER, Ablageziel, Aenderung, Doppel, Felder, Gelesen, Rolle, Vorgabe, Vorschauansicht, Vorschaukurz, Vorschauzaehler,
    Zeile, Ziel, Zuordnung,
)
from backend.app.ablage.wolke import wolke
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.familie import sichtbar
from backend.app.familie.sichtbar import Sicht
from backend.app.material import ablage as materialablage
from backend.app.models.book import BESONDERES
from backend.app.services.storage import SUPPORTED_FORMATS, get_sidecar_path, get_storage_path

IN_ARBEIT = ("wartet", "laedt", "angehalten", "liest", "angaben", "entpacken")
WARTET = "bestaetigen"
FELDER = ("art", "kategorien", "etiketten", "sammlung", "band", "sprache")


class VorschauFehlt(LookupError):
    pass


class Unpassend(ValueError):
    """Eine Änderung, die nicht geht; `meldung` nennt Feld und Grund."""

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


class Vorbei(Exception):
    """Die Aufnahme wartet nicht mehr (übernommen, verworfen, weggelassen)."""

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


def zuordnung_aus(z: dict) -> Zuordnung | None:
    return Zuordnung.model_validate_json(z["zuordnung"]) if z.get("zuordnung") else None


def gelesen_aus(z: dict) -> Gelesen | None:
    return Gelesen.model_validate_json(z["gelesen"]) if z.get("gelesen") else None


def behalten(alt: Zuordnung | None, neu: Zuordnung) -> Zuordnung:
    """Neue Vorschläge, aber was der Nutzer gesetzt hat, bleibt (auch sein Ziel und seine Wahl beim Doppel)."""
    if alt is None:
        return neu
    for feld in FELDER:
        if getattr(alt, feld).herkunft == NUTZER:
            setattr(neu, feld, getattr(alt, feld))
    if alt.doppel.herkunft == NUTZER or (alt.art.herkunft == NUTZER and alt.art.wert == MATERIAL):
        neu.doppel, neu.ziel = alt.doppel, alt.ziel
    if alt.art.herkunft == NUTZER:
        neu.nicht = alt.nicht
    neu.bestaetigt, neu.von_profil = alt.bestaetigt, alt.von_profil
    return neu


# -- anlegen ------------------------------------------------------------------------------------------------------------------

async def anlegen(name: str, quelle: str, vorgabe: Vorgabe | None = None) -> str:
    nr = str(uuid.uuid4())
    await db.execute("INSERT INTO vorschau (id, name, quelle, vorgabe) VALUES (?, ?, ?, ?)",
                     (nr, name or "Hochladen", quelle, (vorgabe or Vorgabe()).model_dump_json()))
    await db.commit()
    return nr


async def offene(nr: str) -> dict:
    z = await db.fetch_one("SELECT * FROM vorschau WHERE id = ?", (nr,))
    if z is None:
        raise VorschauFehlt("Diese Vorschau gibt es nicht")
    return z


async def der_quelle(quelle: str, name: str) -> str:
    """Für den Eingangsordner und Ordner auf dem Gerät: die offene Vorschau dieser Quelle, sonst eine neue."""
    z = await db.fetch_one("SELECT id FROM vorschau WHERE quelle = ? AND stand = 'offen' ORDER BY angelegt_am DESC", (quelle,))
    return z["id"] if z else await anlegen(name, quelle)


async def beruehrt(nr: str) -> None:
    await db.execute("UPDATE vorschau SET geaendert_am = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?", (nr,))


# -- zeigen -------------------------------------------------------------------------------------------------------------------

def rolle(z: dict, zo: Zuordnung | None) -> Rolle:
    if z["name"].lower().endswith(".zip") and z["teil_von"] is None and z["material_fuer"] is None:
        return "zip"
    if z["stand"] == "da" or (zo and zo.doppel.wahl == "weglassen"):
        return "doppel"
    if z["stand"] in ("format", "kaputt", "fehler", "verworfen") or (zo and zo.nicht and zo.art.wert != MATERIAL):
        return "rest"
    return MATERIAL if zo and zo.art.wert == MATERIAL else BUCH


async def _ablage(z: dict, zo: Zuordnung | None, g: Gelesen | None, r: Rolle) -> Ablageziel | None:
    """Wohin die Datei beim Übernehmen kommt, zum Anzeigen; was liegen bleibt: wo es liegt."""
    if r in ("zip", "doppel", "rest") or zo is None:
        return Ablageziel(ort="bleibt", ordner=_wo_es_liegt(z))
    if zo.ziel and zo.ziel.buch_id and (r == MATERIAL or zo.doppel.wahl == "format"):
        o = await materialablage.buchort(zo.ziel.buch_id)
        a = await db.fetch_one("SELECT name, pfad FROM ablage_datei WHERE hash = ?", (o.hash,)) if o else None
        if a and wolke.bereit:
            stamm = posixpath.splitext(a["name"])[0]
            name = f"{stamm}{materialablage.zusatz(z['name'])}" if r == MATERIAL else f"{stamm}.{Path(z['name']).suffix.lower().lstrip('.')}"
            return Ablageziel(ort="kellerwolke", ordner=posixpath.dirname(a["pfad"] or ""), name=name)
        ordner = str(get_storage_path(o.hash) / materialablage.ORDNER) if (o and r == MATERIAL) else _im_speicher(z["sha256"])
        return Ablageziel(ort="geraet", ordner=ordner, name=z["name"])
    if r == MATERIAL:                                 # zu einem Buch dieser Vorschau, das erst beim Übernehmen eins wird
        if wolke.bereit:
            return Ablageziel(ort="kellerwolke", ordner="neben dem Original", name=z["name"])
        return Ablageziel(ort="geraet", ordner=f"im Buchordner unter {materialablage.ORDNER}", name=z["name"])
    titel = sauber((g.titel if g else "") or Path(z["name"]).stem, 110) or "Ohne Titel"
    if wolke.bereit:
        return Ablageziel(ort="kellerwolke", ordner=f"{settings.ablage_ordner}/Bücher/{fach(titel)}", name=z["name"])
    return Ablageziel(ort="geraet", ordner=_im_speicher(z["sha256"]), name=z["name"])


def _im_speicher(summe: str) -> str:
    """Der Ordner der Datei im Speicher auf dem Gerät (je Prüfsumme); solange sie unbekannt ist, der Speicher selbst."""
    return str(get_storage_path(summe)) if summe else str(settings.storage_dir)


def _wo_es_liegt(z: dict) -> str:
    if z["pfad"]:
        return str(Path(z["pfad"]).parent)
    if z["knoten"]:
        return f"{settings.ablage_ordner}/Eingang"
    return str(settings.eingang_dir / str(z["id"]))


def _ordner_der_zip(z: dict) -> str:
    return posixpath.dirname(z["zip_pfad"] or "")


async def zeile(z: dict) -> Zeile:
    zo, g = zuordnung_aus(z), gelesen_aus(z)
    r = rolle(z, zo)
    return Zeile(id=z["id"], name=z["name"], groesse=z["groesse"], ordner=_ordner_der_zip(z), stand=z["stand"], text=z["text"], rolle=r,
                 buch_id=z["buch_id"], gelesen=g, umschlag=bool(g and g.umschlag and z["sha256"] and get_sidecar_path(z["sha256"], "cover.jpg").is_file()),
                 felder=zo, ablage=await _ablage(z, zo, g, r), ki=z["ki_stand"] if z["ki_stand"] in ("offen", "fertig") else "")


def _zaehler(zeilen: list[Zeile]) -> Vorschauzaehler:
    c = Vorschauzaehler(gesamt=sum(1 for z in zeilen if z.rolle != "zip"))
    for z in zeilen:
        offen = z.stand == WARTET or z.stand in IN_ARBEIT
        if z.stand in IN_ARBEIT:
            c.laeuft += 1
        if z.ki == "offen" and offen:
            c.ki += 1
        if z.rolle == "doppel":
            c.weglassen += 1
        elif z.rolle == "rest":
            c.nicht += 1
        elif z.rolle == MATERIAL and offen:
            c.material += 1
            c.uebernehmen += 1
        elif z.rolle == BUCH and offen and z.felder is not None:
            c.uebernehmen += 1
            if z.felder.doppel.wahl == "format":
                c.formate += 1
            elif z.felder.art.wert in BESONDERES:
                c.besonderes += 1
            elif z.felder.art.wert == BUCH:
                c.buecher += 1
            else:
                c.offen += 1
    return c


async def _zeilen_der(nr: str, sicht: Sicht | None) -> list[dict]:
    """Die Aufnahmen der Vorschau; mit Sicht ohne die zu Büchern, die das Profil nicht sieht (BF-78)."""
    zeilen = await db.fetch_all("SELECT * FROM aufnahme WHERE vorschau = ? ORDER BY id", (nr,))
    if sicht is None:
        return zeilen
    sieht = set(await sichtbar.nur_sichtbare(sicht, [z["buch_id"] for z in zeilen if z["buch_id"]]))
    return [z for z in zeilen if not z["buch_id"] or z["buch_id"] in sieht]


def _kurz(v: dict, zeilen: list[dict]) -> Vorschaukurz:
    return Vorschaukurz(id=v["id"], name=v["name"], quelle=v["quelle"], stand=v["stand"], dateien=sum(1 for z in zeilen if not _ist_zip(z)),
                        warten=sum(1 for z in zeilen if z["stand"] == WARTET), laeuft=sum(1 for z in zeilen if z["stand"] in IN_ARBEIT),
                        ki=sum(1 for z in zeilen if z["ki_stand"] == "offen" and z["stand"] == WARTET),
                        groesse=sum(z["groesse"] for z in zeilen if not _ist_zip(z)) or sum(z["groesse"] for z in zeilen),
                        hinweis=v["hinweis"], angelegt_am=v["angelegt_am"], geaendert_am=v["geaendert_am"])


def _ist_zip(z: dict) -> bool:
    return z["name"].lower().endswith(".zip") and z["teil_von"] is None and z["material_fuer"] is None


async def uebersicht(sicht: Sicht | None = None) -> list[Vorschaukurz]:
    """Die offenen Vorschauen ("Zum Bestätigen"), die neueste zuerst."""
    aus = []
    for v in await db.fetch_all("SELECT * FROM vorschau WHERE stand = 'offen' ORDER BY angelegt_am DESC, id"):
        zeilen = await _zeilen_der(v["id"], sicht)
        if zeilen:
            aus.append(_kurz(v, zeilen))
    return aus


async def ansicht(nr: str, sicht: Sicht | None) -> Vorschauansicht:
    v = await offene(nr)
    roh = await _zeilen_der(nr, sicht)
    zeilen = [await zeile(z) for z in roh]
    dazu = Counter(z.felder.ziel.aufnahme for z in zeilen if z.rolle == MATERIAL and z.felder and z.felder.ziel and z.felder.ziel.aufnahme)
    for z in zeilen:
        z.material = dazu.get(z.id, 0)
    return Vorschauansicht(**_kurz(v, roh).model_dump(), vorgabe=Vorgabe.model_validate_json(v["vorgabe"]), zaehler=_zaehler(zeilen), zeilen=zeilen)


# -- ändern -------------------------------------------------------------------------------------------------------------------

async def _pruefe_kategorien(ids: list[int]) -> None:
    if not ids:
        return
    da = {z["id"] for z in await db.fetch_all(f"SELECT id FROM categories WHERE art = 'kategorie' AND id IN ({','.join('?' * len(ids))})", tuple(ids))}
    if fehlt := [i for i in ids if i not in da]:
        raise Unpassend(f"Kategorien: {', '.join(map(str, fehlt))} gibt es nicht")


async def _ziel(nr: str, z: dict, felder: Felder, sicht: Sicht) -> Ziel | None:
    e = felder.ziel
    if e is None:
        return None
    if (e.buch_id is None) == (e.aufnahme is None):
        raise Unpassend("Ziel: genau eins von buch_id und aufnahme")
    if e.buch_id is not None:
        b = await db.fetch_one("SELECT id, title FROM books WHERE id = ?", (e.buch_id,))
        if b is None or not await sichtbar.sieht(sicht, e.buch_id):
            raise Unpassend("Ziel: dieses Buch gibt es nicht")
        return Ziel(buch_id=b["id"], titel=b["title"])
    andere = await db.fetch_one("SELECT * FROM aufnahme WHERE id = ? AND vorschau = ?", (e.aufnahme, nr))
    if andere is None or andere["id"] == z["id"] or rolle(andere, zuordnung_aus(andere)) != BUCH:
        raise Unpassend("Ziel: diese Aufnahme ist kein Buch dieser Vorschau")
    g = gelesen_aus(andere)
    return Ziel(aufnahme=andere["id"], titel=(g.titel if g else "") or andere["name"])


def _setzen(zo: Zuordnung, z: dict, felder: Felder, ziel: Ziel | None) -> None:
    gesetzt = felder.model_fields_set
    for feld in FELDER:
        wert = getattr(felder, feld)
        if feld not in gesetzt or (wert is None and feld != "sammlung"):     # null leert nur die Sammlung
            continue
        setattr(zo, feld, type(getattr(zo, feld))(wert=wert, herkunft=NUTZER))
    if "ziel" in gesetzt:
        zo.ziel = ziel
    if felder.art is not None:
        zo.nicht = "" if felder.art == MATERIAL else zo.nicht
        if felder.art not in (MATERIAL, "") and Path(z["name"]).suffix.lower() not in SUPPORTED_FORMATS:
            raise Unpassend("Art: diese Datei ist kein lesbares Buchformat, nur Material")
    if felder.doppel is not None:
        zo.doppel = Doppel(art=zo.doppel.art, wahl=felder.doppel, herkunft=NUTZER, grund=zo.doppel.grund)
    _stimmig(zo)


def _stimmig(zo: Zuordnung) -> None:
    """Was zusammen gelten muss; sonst Unpassend."""
    if zo.art.wert == MATERIAL and zo.ziel is None:
        raise Unpassend("Ziel: Material braucht das Buch, zu dem es gehört")
    if zo.doppel.wahl == "format" and zo.ziel is None:
        raise Unpassend("Ziel: ein weiteres Format braucht das Buch, zu dem es gehört")
    if zo.doppel.art == "gleich" and zo.doppel.wahl not in ("weglassen",):
        raise Unpassend("Doppel: dieselbe Datei gibt es nur einmal, sie wird weggelassen")


async def aendern(nr: str, a: Aenderung, sicht: Sicht) -> Vorschauansicht:
    """Felder einer oder mehrerer Aufnahmen setzen; geht eine nicht, ändert sich keine."""
    await offene(nr)
    zeilen = await db.fetch_all(f"SELECT * FROM aufnahme WHERE vorschau = ? AND id IN ({','.join('?' * len(a.ids))})", (nr, *a.ids))
    if len(zeilen) != len(set(a.ids)):
        raise VorschauFehlt("Diese Aufnahme gehört nicht zu der Vorschau")
    await _pruefe_kategorien(a.felder.kategorien or [])
    if a.felder.sammlung is not None and await db.fetch_one("SELECT 1 AS da FROM collections WHERE id = ?", (a.felder.sammlung,)) is None:
        raise Unpassend("Sammlung: diese Sammlung gibt es nicht")
    neu = []
    for z in zeilen:
        if z["stand"] not in (WARTET, *IN_ARBEIT) or (z["zuordnung"] and zuordnung_aus(z).bestaetigt):
            raise Vorbei(f"{z['name']} wartet nicht mehr auf die Bestätigung")
        zo = zuordnung_aus(z) or Zuordnung()
        _setzen(zo, z, a.felder, await _ziel(nr, z, a.felder, sicht))
        neu.append((zo.model_dump_json(), z["id"]))
    async with db.einheit():
        await db.execute_many("UPDATE aufnahme SET zuordnung = ?, geaendert_am = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?", neu)
        await beruehrt(nr)
        await db.commit()                            # Annahme und KI lesen über die gemeinsame Verbindung
    return await ansicht(nr, sicht)


def vorgabe_aus(v: dict) -> Vorgabe:
    return Vorgabe.model_validate(json.loads(v["vorgabe"] or "{}"))
