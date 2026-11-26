"""Der Auftrag "Originale kopieren" (BF-82): beim Umzug ohne Kellerwolke holt das neue Gerät jedes Original vom alten, über die
Sitzung aus dem Einmalcode (Schlüsselbund, Art `umzug`), Datei für Datei mit Prüfsumme. Eine angefangene Datei setzt nach einer
Unterbrechung an ihrem Ende fort (Bereich), ein fertiges Original wird nie zweimal geholt. Stimmt die Prüfsumme nicht, fällt nur
die angefangene Datei weg; das Original steht als Fehler im Auftrag und kommt beim Fortsetzen noch einmal dran. Am Ende prüft
der Auftrag "Originale prüfen", ob alles da ist."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import httpx

from backend.app.core import einstellungen, schluessel
from backend.app.core.database import db
from backend.app.einrichtung.auftrag import Auftrag, Ruhen
from backend.app.einrichtung.modelle import Teil
from backend.app.einrichtung.zustand import Einrichtungsfehler
from backend.app.services.storage import compute_hash, get_storage_path, sanitize_filename

STUECK = 1 << 20
QUELLE = "umzug_quelle"                                 # app_settings des neuen Geräts: die Adresse des alten


def _summe(datei: Path) -> str:
    summe = hashlib.sha256()
    with datei.open("rb") as f:
        while s := f.read(STUECK):
            summe.update(s)
    return summe.hexdigest()


class Kopieren(Auftrag):
    art = "kopieren"
    was = "Originale kopieren"

    async def zaehlen(self) -> tuple[int, int, list[Teil]]:
        z = await db.fetch_one("SELECT COUNT(*) AS gesamt, COALESCE(SUM(stand = 'fertig'), 0) AS fertig, COALESCE(SUM(stand = 'fehler'), 0) AS fehler, "
                               "COALESCE(SUM(groesse), 0) AS bytes, COALESCE(SUM(CASE WHEN stand = 'fertig' THEN groesse ELSE 0 END), 0) AS kopiert "
                               "FROM umzug_kopie")
        return z["gesamt"], z["fertig"] + z["fehler"], [
            Teil(schluessel="dateien", name="Dateien", gesamt=z["gesamt"], fertig=z["fertig"]),
            Teil(schluessel="groesse", name="Größe", gesamt=z["bytes"], fertig=z["kopiert"]),
            Teil(schluessel="fehler", name="Prüfsumme stimmt nicht", gesamt=z["gesamt"], fertig=z["fehler"])]

    async def _adresse(self) -> tuple[str, str]:
        adresse, sitzung = await einstellungen.lesen(QUELLE) or "", schluessel.lesen(schluessel.Art.UMZUG)
        if not (adresse and sitzung):
            raise Einrichtungsfehler("Erst mit dem alten Gerät verbinden")
        return adresse, sitzung

    async def vorbereiten(self) -> None:
        """Die Liste vom alten Gerät; schon fertige bleiben fertig, gescheiterte kommen noch einmal dran."""
        from backend.app.einrichtung import umzug

        adresse, sitzung = await self._adresse()
        try:
            async with umzug.client(adresse) as c:
                r = await c.get("/api/umzug/originale", headers={umzug.KOPF: sitzung})
        except httpx.HTTPError as f:
            raise Einrichtungsfehler(f"Das alte Gerät antwortet nicht ({type(f).__name__})", 502) from f
        if r.status_code >= 400:
            raise Einrichtungsfehler(f"Altes Gerät: {umzug._grund(r)}", 502)
        for e in r.json():
            await db.execute("INSERT OR IGNORE INTO umzug_kopie(hash, name, groesse) VALUES (?, ?, ?)", (e["hash"], e["name"], e["groesse"] or 0))
        await db.execute("UPDATE umzug_kopie SET stand = 'offen', text = '' WHERE stand = 'fehler'")
        await db.commit()

    async def naechstes(self) -> bool:
        from backend.app.einrichtung import umzug

        e = await db.fetch_one("SELECT * FROM umzug_kopie WHERE stand = 'offen' ORDER BY rowid LIMIT 1")
        if e is None:
            return False
        name = sanitize_filename(e["name"] or "original")
        ziel = get_storage_path(e["hash"]) / name
        teil = ziel.with_name(f".{name}.teil")
        if ziel.exists() and await asyncio.to_thread(compute_hash, ziel) == e["hash"]:
            await self._fertig(e["hash"], "schon da")
            return True
        ziel.parent.mkdir(parents=True, exist_ok=True)
        adresse, sitzung = await self._adresse()
        versatz = teil.stat().st_size if teil.exists() else 0
        try:
            async with umzug.client(adresse) as c:
                kopf = {umzug.KOPF: sitzung} | ({"Range": f"bytes={versatz}-"} if versatz else {})
                async with c.stream("GET", f"/api/umzug/originale/{e['hash']}", headers=kopf) as r:
                    if r.status_code == 416:
                        versatz = teil.stat().st_size
                    elif r.status_code >= 400:
                        await r.aread()
                        raise Ruhen(f"Altes Gerät: {umzug._grund(r)}")
                    else:
                        weiter = r.status_code == 206 and versatz > 0
                        with teil.open("ab" if weiter else "wb") as f:
                            async for stueck in r.aiter_bytes():          # wie es ankommt: nach einem Abbruch zählt jedes Byte
                                f.write(stueck)
        except httpx.HTTPError as f:
            raise Ruhen(f"Das alte Gerät antwortet nicht ({type(f).__name__}); fortgesetzt wird an derselben Stelle") from f
        if await asyncio.to_thread(_summe, teil) != e["hash"]:
            teil.unlink(missing_ok=True)
            await db.execute("UPDATE umzug_kopie SET stand = 'fehler', text = 'Prüfsumme stimmt nicht' WHERE hash = ?", (e["hash"],))
            await db.commit()
            return True
        teil.replace(ziel)
        await self._fertig(e["hash"], "")
        return True

    @staticmethod
    async def _fertig(file_hash: str, text: str) -> None:
        await db.execute("UPDATE umzug_kopie SET stand = 'fertig', text = ? WHERE hash = ?", (text, file_hash))
        await db.commit()

    async def danach(self) -> None:
        from backend.app.einrichtung.pruefung import pruefung

        await pruefung.beginnen(pruefsummen=False)


kopieren = Kopieren()
