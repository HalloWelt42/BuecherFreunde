"""Der Auftrag "Originale prüfen" (BF-82): nach dem Wiederherstellen, dem Umzug oder auf Wunsch je Buch, ob sein Original
erreichbar ist. In der Kellerwolke zählt der Knoten mit derselben Prüfsumme (nichts wird geladen), auf dem Gerät die Datei, mit
`pruefsummen` auch ihr Inhalt. Fehlt es am alten Ort, sucht der Auftrag es über die Prüfsumme in der Kellerwolke
(`GET /api/v1/ablage/pruefsumme/{sha256}`) und trägt den neuen Ort ein. Fehlen Volltext, Umschlag oder Angaben auf dem Gerät,
kommen sie aus dem Auszug zurück. Gelöscht wird nichts: Fehlende bleiben im Bestand und stehen im Bericht."""

from __future__ import annotations

import asyncio

from backend.app.ablage import auszug
from backend.app.ablage.antwort import auf_dem_geraet
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core.database import db
from backend.app.core.suchindex import SUCHTEXT_ZEICHEN
from backend.app.einrichtung.auftrag import Auftrag
from backend.app.einrichtung.modelle import Befund, Pruefbericht, Teil
from backend.app.models.book import Originalhinweis
from backend.app.services.storage import compute_hash, get_sidecar_path

TEILE = (("erreichbar", "Erreichbar"), ("wiedergefunden", "Über die Prüfsumme wiedergefunden"), ("fehlt", "Fehlt"))
FEHLT = "Weder am alten Ort noch über die Prüfsumme in der Kellerwolke"


class Pruefung(Auftrag):
    art = "pruefung"
    was = "Originale prüfen"

    async def zaehlen(self) -> tuple[int, int, list[Teil]]:
        gesamt = (await db.fetch_one("SELECT COUNT(*) AS n FROM books"))["n"]
        je = {z["ergebnis"]: z["n"] for z in await db.fetch_all("SELECT ergebnis, COUNT(*) AS n FROM original_befund GROUP BY ergebnis")}
        texte = (await db.fetch_one("SELECT COALESCE(SUM(texte), 0) AS n FROM original_befund"))["n"]
        teile = [Teil(schluessel=k, name=n, gesamt=gesamt, fertig=je.get(k, 0)) for k, n in TEILE]
        teile.append(Teil(schluessel="texte", name="Volltext und Umschlag aus dem Auszug", gesamt=gesamt, fertig=texte))
        return gesamt, sum(je.values()), teile

    async def vorbereiten(self) -> None:
        await db.execute("DELETE FROM original_befund")      # der Bericht des letzten Laufs; die Bücher bleiben
        await db.commit()

    async def naechstes(self) -> bool:
        b = await db.fetch_one("SELECT id, hash FROM books WHERE id NOT IN (SELECT book_id FROM original_befund) ORDER BY id LIMIT 1")
        if b is None:
            return False
        ergebnis, ort, pfad, text = await self._original(b["hash"], bool((await self.angaben()).get("pruefsummen")))
        texte = await self._texte(b["id"], b["hash"]) if ergebnis != "fehlt" and ort == "kellerwolke" else False
        await db.execute("INSERT OR REPLACE INTO original_befund(book_id, ergebnis, ort, pfad, text, texte) VALUES (?, ?, ?, ?, ?, ?)",
                         (b["id"], ergebnis, ort, pfad, text, int(texte)))
        await db.commit()
        return True

    async def _original(self, file_hash: str, pruefsummen: bool) -> tuple[str, str, str, str]:
        ablage = await db.fetch_one("SELECT knoten, pfad FROM ablage_datei WHERE hash = ?", (file_hash,))
        text = ""
        if ablage and wolke.bereit:
            try:
                k = await wolke.knoten(ablage["knoten"])
                if k.get("sha256") in (None, file_hash):
                    return "erreichbar", "kellerwolke", str(k.get("pfad") or ablage["pfad"]), ""
                text = "Am alten Ort liegt eine andere Datei"
            except WolkeFehler as f:
                if f.status != 404:
                    raise
        lokal = await asyncio.to_thread(auf_dem_geraet, file_hash)
        if lokal is not None:
            if not pruefsummen or await asyncio.to_thread(compute_hash, lokal) == file_hash:
                return "erreichbar", "geraet", str(lokal), ""
            text = "Die Datei auf dem Gerät hat eine andere Prüfsumme"
        if wolke.bereit:
            for t in await wolke.gibt_es(file_hash):
                if t.get("geloescht") or t.get("haupt_id"):
                    continue
                await db.execute("INSERT INTO ablage_datei(hash, knoten, name, pfad, groesse) VALUES (?, ?, ?, ?, ?) ON CONFLICT(hash) DO UPDATE "
                                 "SET knoten = excluded.knoten, name = excluded.name, pfad = excluded.pfad",
                                 (file_hash, t["id"], t.get("name") or "", t.get("pfad") or "", t.get("groesse") or 0))
                return "wiedergefunden", "kellerwolke", str(t.get("pfad") or t.get("name") or ""), "Der neue Ort ist eingetragen"
        return "fehlt", "", "", text or FEHLT

    @staticmethod
    async def _texte(buch: int, file_hash: str) -> bool:
        """Fehlen Volltext, Umschlag oder Angaben auf dem Gerät, kommen sie aus dem Auszug; der Volltext auch in die Suche."""
        if all(get_sidecar_path(file_hash, n).exists() for n in ("fulltext.txt", "cover.jpg", "metadata.json")):
            return False
        ablage = await db.fetch_one("SELECT knoten FROM ablage_datei WHERE hash = ?", (file_hash,))
        gelesen = await auszug.holen(ablage["knoten"]) if ablage else None
        if gelesen is None:
            return False
        geschrieben = await asyncio.to_thread(auszug.dateien_ablegen, file_hash, gelesen)
        if "fulltext.txt" in geschrieben:
            text = gelesen.dateien["fulltext.txt"].decode("utf-8", "replace")
            await db.execute("UPDATE books SET fts_content = ? WHERE id = ?", (text[:SUCHTEXT_ZEICHEN], buch))
            await db.execute("UPDATE books SET fts_content = '' WHERE id = ?", (buch,))      # steht im Suchindex
        return bool(geschrieben)


pruefung = Pruefung()


async def bericht() -> Pruefbericht:
    s = await pruefung.stand()
    zahl = {t.schluessel: t.fertig for t in s.teile}
    zeilen = await db.fetch_all("SELECT f.*, b.title, b.author FROM original_befund f JOIN books b ON b.id = f.book_id "
                                "WHERE f.ergebnis != 'erreichbar' ORDER BY f.ergebnis, b.title")
    return Pruefbericht(auftrag=s, erreichbar=zahl.get("erreichbar", 0), wiedergefunden=zahl.get("wiedergefunden", 0), fehlt=zahl.get("fehlt", 0),
                        texte=zahl.get("texte", 0),
                        eintraege=[Befund(buch_id=z["book_id"], titel=z["title"], autor=z["author"], ergebnis=z["ergebnis"], ort=z["ort"],
                                          pfad=z["pfad"], text=z["text"]) for z in zeilen])


async def hinweis(buch: int) -> Originalhinweis | None:
    """Für die Buchseite: fehlt das Original laut der letzten Prüfung, der Grund und wann geprüft wurde."""
    z = await db.fetch_one("SELECT text, geprueft_am FROM original_befund WHERE book_id = ? AND ergebnis = 'fehlt'", (buch,))
    return Originalhinweis(text=z["text"] or FEHLT, geprueft_am=z["geprueft_am"]) if z else None
