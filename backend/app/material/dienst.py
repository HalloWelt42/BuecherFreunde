"""Begleitmaterial je Buch (BF-81): die eine Liste in `buch_material` und was man mit ihr tut. Buchseite, Suche,
Hochladen mit Vorschau, Abgleich und die Folgen beim Löschen lesen und schreiben nur hier; wo eine Datei liegt, weiß
material/ablage.py.

Entfernen geschieht nur nach der Folgenvorschau (`folgen`, dann `entfernen` mit deren `stand`). Das Material folgt dem Buch:
wer das Buch nicht sieht (privat, nicht freigegeben), sieht sein Material nicht (die Wege prüfen das Buch im Pfad); geht das
Buch, geht sein Material mit (in der Kellerwolke mit dem Original in den Papierkorb, auf dem Gerät mit dem Buchordner)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from pathlib import Path

from fastapi import Request
from fastapi.responses import Response

from backend.app.core.database import db
from backend.app.material import ablage, arten, zugehoerig
from backend.app.material.modelle import Fund, Herkunft, Material, Materialfolgen, Materialliste
from backend.app.material.textlauf import textlauf

SPALTEN = "id, buch_id, name, art, groesse, sha256, ort, knoten, rolle, pfad, herkunft, text_stand, text_seiten, angelegt_am"


class MaterialFehlt(LookupError):
    pass


class StandVeraltet(Exception):
    """Seit der Folgenvorschau hat sich etwas geändert."""


def _material(z: dict) -> Material:
    a = arten.nach_art(z["art"])
    return Material(id=z["id"], buch_id=z["buch_id"], name=z["name"], art=a.art, art_name=a.name, zeichen=a.zeichen, groesse=z["groesse"],
                    ort=z["ort"], pfad=z["pfad"], herkunft=z["herkunft"], oeffnen=a.oeffnen, lesbar=a.lesbar, text_stand=z["text_stand"],
                    text_seiten=z["text_seiten"], angelegt_am=z["angelegt_am"])


async def zeile(buch: int, nr: str) -> dict:
    z = await db.fetch_one(f"SELECT {SPALTEN} FROM buch_material WHERE id = ? AND buch_id = ?", (nr, buch))
    if z is None:
        raise MaterialFehlt("Dieses Begleitmaterial gibt es nicht")
    return z


async def zeilen(buch: int) -> list[dict]:
    return await db.fetch_all(f"SELECT {SPALTEN} FROM buch_material WHERE buch_id = ? ORDER BY name COLLATE NOCASE, angelegt_am", (buch,))


async def liste(buch: int) -> Materialliste:
    alle = [_material(z) for z in await zeilen(buch)]
    ort = await ablage.buchort(buch)
    return Materialliste(material=alle, funde=await funde(buch), ort=ablage.fuer_buch(ort).ort if ort else "geraet",
                         groesse=sum(m.groesse for m in alle))


async def anzahlen(buecher: list[int]) -> dict[int, int]:
    """Je Buch, wie viele Dateien Material es hat (nur Bücher mit Material)."""
    if not buecher:
        return {}
    zeilen_ = await db.fetch_all(f"SELECT buch_id, COUNT(*) AS n FROM buch_material WHERE buch_id IN ({','.join('?' * len(buecher))}) GROUP BY buch_id",
                                 tuple(buecher))
    return {z["buch_id"]: z["n"] for z in zeilen_}


def _pruefsumme(datei: Path) -> str:
    summe = hashlib.sha256()
    with datei.open("rb") as f:
        while stueck := f.read(1 << 20):
            summe.update(stueck)
    return summe.hexdigest()


async def aufnehmen(buch: int, name: str, herkunft: Herkunft, *, datei: Path | None = None, knoten: str | None = None,
                    behalten: bool = False, groesse: int = 0, sha256: str = "") -> Material:
    """Eine Datei wird Material des Buchs: vom Gerät (`datei`) oder aus der Kellerwolke (`knoten`), abgelegt, wo das
    Original liegt. Lesbares kommt danach in die Suche (material/textlauf.py)."""
    ort = await ablage.buchort(buch)
    if ort is None:
        raise MaterialFehlt("Das Buch gibt es nicht")
    if datei is not None:
        groesse, sha256 = datei.stat().st_size, sha256 or await asyncio.to_thread(_pruefsumme, datei)
    nr = str(uuid.uuid4())
    hin = ablage.fuer_buch(ort)
    abgelegt = await hin.ablegen(ort, nr, name, datei=datei, knoten=knoten, behalten=behalten)
    art = arten.von(name)
    await db.execute("""INSERT INTO buch_material (id, buch_id, name, art, groesse, sha256, ort, knoten, rolle, pfad, herkunft, text_stand)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (nr, buch, name, art.art, groesse, sha256, abgelegt.ort, abgelegt.knoten, abgelegt.rolle, abgelegt.pfad, herkunft,
                      "offen" if art.lesbar else "ohne"))
    await db.commit()
    textlauf.anstossen()
    return _material(await zeile(buch, nr))


def _mit_endung(neu: str, alt: str) -> str:
    """Die Endung bleibt: fehlt sie im neuen Namen, kommt sie dazu."""
    endung = Path(alt).suffix
    return neu if not endung or neu.lower().endswith(endung.lower()) else f"{neu}{endung}"


async def umbenennen(buch: int, nr: str, name: str) -> Material:
    z = await zeile(buch, nr)
    neu = _mit_endung(name, z["name"])
    if neu != z["name"]:
        ort = await ablage.buchort(buch)
        abgelegt = await ablage.von(z).umbenennen(ort, z, neu)
        await db.execute("UPDATE buch_material SET name = ?, pfad = ? WHERE id = ?", (neu, abgelegt.pfad, nr))
        await db.commit()
    return _material(await zeile(buch, nr))


def _stand(z: dict) -> str:
    return hashlib.sha256(json.dumps([z["id"], z["name"], z["groesse"], z["pfad"], z["text_seiten"]]).encode()).hexdigest()[:16]


async def folgen(buch: int, nr: str) -> Materialfolgen:
    z = await zeile(buch, nr)
    titel = (await db.fetch_one("SELECT title FROM books WHERE id = ?", (buch,)))["title"]
    return Materialfolgen(id=nr, name=z["name"], buch_id=buch, titel=titel, ort=z["ort"], pfad=z["pfad"], groesse=z["groesse"],
                          papierkorb=ablage.von(z).papierkorb, suche=z["text_stand"] == "fertig", seiten=z["text_seiten"], stand=_stand(z))


async def entfernen(buch: int, nr: str, stand: str) -> None:
    """Nur mit dem `stand` aus `folgen`: in der Kellerwolke in den Papierkorb, auf dem Gerät endgültig; die Suche verliert
    den Text (core/suchindex.py). Das Buch und das übrige Material bleiben."""
    z = await zeile(buch, nr)
    if _stand(z) != stand:
        raise StandVeraltet("Seit der Vorschau hat sich das Material geändert, bitte noch einmal ansehen")
    await ablage.von(z).entfernen(z)
    await db.execute("DELETE FROM buch_material WHERE id = ?", (nr,))
    await db.commit()


async def antwort(request: Request, buch: int, nr: str, herunterladen: bool) -> Response:
    z = await zeile(buch, nr)
    return await ablage.von(z).antwort(request, z, herunterladen or not arten.nach_art(z["art"]).oeffnen)


async def des_buchs(buch: int) -> list[Material]:
    """Das Material eines Buchs, für die Folgen beim Löschen des Buchs."""
    return [_material(z) for z in await zeilen(buch)]


# -- Funde aus dem Abgleich (material/erkennen.py) ------------------------------------------------------------------------------

async def funde(buch: int) -> list[Fund]:
    zeilen_ = await db.fetch_all("SELECT knoten, buch_id, name, groesse, pfad, gefunden_am FROM material_fund WHERE buch_id = ? AND stand = 'offen' "
                                 "ORDER BY name COLLATE NOCASE", (buch,))
    return [Fund(**z) for z in zeilen_]


async def _fund(buch: int, knoten: str) -> dict:
    z = await db.fetch_one("SELECT * FROM material_fund WHERE buch_id = ? AND knoten = ? AND stand = 'offen'", (buch, knoten))
    if z is None:
        raise MaterialFehlt("Diesen Fund gibt es nicht")
    return z


async def fund_annehmen(buch: int, knoten: str) -> Material:
    """Ja: die Datei wird Begleiter des Originals und Material des Buchs, in der App ohne den Namen des Buchs davor."""
    f = await _fund(buch, knoten)
    original = await db.fetch_one("SELECT a.name FROM books b JOIN ablage_datei a ON a.hash = b.hash WHERE b.id = ?", (buch,))
    name = zugehoerig.als_material(f["name"], original["name"]) if original else f["name"]
    m = await aufnehmen(buch, name, "erkannt", knoten=knoten, groesse=f["groesse"])
    await db.execute("UPDATE material_fund SET stand = 'angenommen' WHERE knoten = ?", (knoten,))
    await db.commit()
    return m


async def fund_ablehnen(buch: int, knoten: str) -> None:
    """Nein: die Datei bleibt, wo sie ist, und wird nie wieder angeboten."""
    await _fund(buch, knoten)
    await db.execute("UPDATE material_fund SET stand = 'abgelehnt' WHERE knoten = ?", (knoten,))
    await db.commit()
