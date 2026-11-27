"""Die Aufnahmen: jede Datei auf ihrem Weg in sechs Stationen (Prüfen, Wolke, Lesen, Angaben, Regal, Wissen), eine Liste für
alle Quellen: hochgeladen im Browser, der Eingangsordner, Ordner auf dem Gerät und gemeinfreie Bücher. Der Stand steht in der
Datenbank; nach einem Neustart geht jede Aufnahme dort weiter, wo sie war, auch wartende. Teile strömen vom Browser durch die
App in die Kellerwolke, ohne hier abgelegt zu werden; Dateien aus Ordnern auf dem Gerät bleiben, wo sie sind (kopiert wird
in die Kellerwolke, ohne sie in den Speicher des Geräts).

Halt "Zum Bestätigen" (BF-80): vor der Station Regal wartet eine Aufnahme, die zu einer Vorschau gehört (annahme/vorschau.py),
bis sie übernommen oder verworfen wird; Hochladen im Browser immer, Eingangsordner und Ordner auf dem Gerät je Weg nach den
Einstellungen (annahme/einstellungen.py). Gelesen ist sie dann schon (Angaben in `gelesen`, Text und Umschlag bei der
Prüfsumme), im Regal, in der Suche und in den Zählern steht nichts. Eine ZIP wird hier ausgepackt (annahme/entpacken.py), Teil
für Teil, jeder Teil eine eigene Aufnahme. Nach dem Übernehmen geht es weiter: als Werk ins Regal, als weiteres Format zu einem
Buch (ablage/formate.py) oder als Begleitmaterial (BF-81, material/). Material von der Buchseite (`material_fuer`) geht ohne
Halt dorthin."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

from backend.app.ablage import formate, originale
from backend.app.ablage.namen import dateiname, sauber
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.annahme import angaben, auswertung, einstellungen, entpacken, gemeinfrei, uebernehmen, vorschau, zuordnen
from backend.app.annahme.eintragen import ablegen, eintragen
from backend.app.annahme.ki_vorschau import ki_vorschau
from backend.app.annahme.modelle import MATERIAL, Gelesen, Vorgabe, Wert, Ziel, Zuordnung
from backend.app.annahme.vorschau import behalten, gelesen_aus, zuordnung_aus
from backend.app.codestellen.dienst import codestellen
from backend.app.core.anschluesse import anschluesse
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.material import dienst as material, zugehoerig
from backend.app.quellen.fehler import QuelleFehler
from backend.app.services import deckblatt
from backend.app.services.ki import ki
from backend.app.services.storage import (
    SUPPORTED_FORMATS, compute_hash, get_sidecar_path, get_storage_path, load_fulltext, save_cover, save_fulltext, save_metadata,
)

logger = logging.getLogger("buecherfreunde.annahme")
TEIL = 4 * 1024 * 1024
LAUFEND = ("wartet", "laedt", "angehalten", "liest", "angaben", "regal", "entpacken")
IN_ARBEIT = ("liest", "angaben", "regal", "entpacken")
QUELLEN = ("hochladen", "eingangsordner", "ordner", "extern", "gemeinfrei")
BEHALTEN = uebernehmen.BEHALTEN                  # aus diesen Quellen bleibt die Datei, wo sie ist
KLAEREN = ("format", "kaputt", "fehler", "ohne_text")
# Zähler je Quelle: jeder Stand zählt genau einmal
IM_REGAL = ("fertig", "wissen", "ohne_text")
GESCHEITERT = ("format", "kaputt", "fehler")
WARTET = vorschau.WARTET                          # "bestaetigen": vor dem Regal, bis übernommen oder verworfen (BF-80)
STAENDE = (*LAUFEND, WARTET, *IM_REGAL, "da", *GESCHEITERT, "entpackt", "verworfen")
LISTE = 300                              # so viele Einträge zeigt die Liste, die Zähler zählen alle
FORMATE = "PDF, EPUB, MOBI, TXT und MD"
NAME_DER_QUELLE = {"eingangsordner": "Eingangsordner", "ordner": "Ordner auf dem Gerät", "extern": "Externe Sammlung"}
# Die nächste Aufnahme für die Arbeit; wer zu einer anderen gehört (Format, Material), wartet, bis die fertig ist, und ein
# angefangener Teil einer ZIP gehört der ZIP, die ihn beim Weiterauspacken fertig macht
NAECHSTE = f"""SELECT a.* FROM aufnahme a WHERE a.stand IN ({', '.join(repr(s) for s in IN_ARBEIT)})
               AND NOT (a.stand = 'entpacken' AND a.teil_von IS NOT NULL)
               AND NOT EXISTS (SELECT 1 FROM aufnahme w WHERE w.id = json_extract(a.zuordnung, '$.ziel.aufnahme')
                               AND w.stand IN ({', '.join(repr(s) for s in LAUFEND)}))
               ORDER BY a.id LIMIT 1"""


class AnnahmeFehler(Exception):
    """Diese eine Aufnahme geht nicht weiter; `meldung` für Menschen."""

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


class ZuViel(Exception):
    """Mehr Bytes als die Datei hat, die angesagt war."""

    def __init__(self) -> None:
        super().__init__("Mehr Daten als angesagt")


class Versatz(Exception):
    """Der Browser schickt nicht ab dem Stand, den der Server hat."""

    def __init__(self, empfangen: int) -> None:
        super().__init__("Das Teil schließt nicht an")
        self.empfangen = empfangen


def mb(n: int) -> str:
    return f"{n / 1e6:.1f}".replace(".", ",") + " MB"


def _aussen(z: dict) -> dict:
    return {k: z[k] for k in ("id", "name", "groesse", "sha256", "empfangen", "stand", "schritt", "anteil", "text", "buch_id", "quelle", "angelegt_am",
                              "geaendert_am", "vorschau", "teil_von", "material_fuer")} | {"teil_groesse": TEIL}


def ist_zip(z: dict) -> bool:
    return Path(z["name"]).suffix.lower() == ".zip" and z["teil_von"] is None and (z["material_fuer"] is None or bool(z["entpacken"]))


class Annahme:
    def __init__(self) -> None:
        self._arbeit = asyncio.Event()
        self._neu: set[asyncio.Event] = set()
        self._schleife: asyncio.Task | None = None
        self._eingang: str | None = None

    # -- Leben ---------------------------------------------------------------------------------------------------------
    def starten(self) -> None:
        self._arbeit, self._neu, self._eingang = asyncio.Event(), set(), None       # gehören zur laufenden Ereignisschleife
        self._arbeit.set()
        self._leere_ordner_raeumen()
        self._schleife = asyncio.create_task(self._arbeiten())

    async def stoppen(self) -> None:
        if self._schleife:
            self._schleife.cancel()
        auswertung.schliessen()

    # -- Sicht ---------------------------------------------------------------------------------------------------------
    async def alle(self) -> dict:
        """Die neuesten Einträge (höchstens `LISTE`, `weitere` sagt, wie viele darüber hinaus da sind) und Zähler über alle,
        auch je Quelle (gesamt, laeuft, bestaetigen, fertig, da, gescheitert)."""
        zeilen = [_aussen(z) for z in await db.fetch_all(f"SELECT * FROM aufnahme WHERE ausgeblendet = 0 ORDER BY id DESC LIMIT {LISTE}")]
        anzahl = {(z["quelle"], z["stand"]): z["n"] for z in await db.fetch_all(
            "SELECT quelle, stand, COUNT(*) AS n FROM aufnahme WHERE ausgeblendet = 0 GROUP BY quelle, stand")}

        def zahl(staende: tuple[str, ...], quelle: str | None = None) -> int:
            return sum(n for (q, s), n in anzahl.items() if s in staende and quelle in (None, q))

        je_quelle = {q: {"gesamt": zahl(STAENDE, q), "laeuft": zahl(LAUFEND, q), "bestaetigen": zahl((WARTET,), q), "fertig": zahl(IM_REGAL, q),
                         "da": zahl(("da",), q), "gescheitert": zahl(GESCHEITERT, q)} for q in QUELLEN}
        alle = sum(anzahl.values())
        return {"eintraege": zeilen, "weitere": max(0, alle - len(zeilen)),
                "zaehler": {"alle": alle, "laeuft": zahl(LAUFEND), "bestaetigen": zahl((WARTET,)), "klaeren": zahl(KLAEREN), "da": zahl(("da",)),
                            "fertig": zahl(("fertig", "wissen"))},
                "quellen": je_quelle}

    async def einer(self, nr: int) -> dict | None:
        z = await db.fetch_one("SELECT * FROM aufnahme WHERE id = ?", (nr,))
        return _aussen(z) if z else None

    async def ereignisse(self) -> AsyncIterator[dict]:
        neu = asyncio.Event()
        self._neu.add(neu)
        try:
            while True:
                yield await self.alle()
                neu.clear()
                try:
                    await asyncio.wait_for(neu.wait(), 20)
                    await asyncio.sleep(.4)                 # viele kleine Änderungen zusammenfassen
                except TimeoutError:
                    pass
        finally:
            self._neu.discard(neu)

    def melden(self) -> None:
        """Wer zusieht (Ereignisstrom), bekommt den neuen Stand; die Arbeit sieht nach, ob etwas dran ist."""
        self._weiter()

    async def _setze(self, nr: int, **felder) -> None:
        namen = ", ".join(f"{k} = ?" for k in felder)
        await db.execute(f"UPDATE aufnahme SET {namen}, geaendert_am = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?", (*felder.values(), nr))
        await db.commit()
        for e in self._neu:
            e.set()

    async def _zeile(self, nr: int) -> dict:
        return await db.fetch_one("SELECT * FROM aufnahme WHERE id = ?", (nr,))

    # -- Hochladen -----------------------------------------------------------------------------------------------------
    async def anlegen(self, name: str, groesse: int, sha256: str, anreichern: bool = False, vorschau_id: str | None = None,
                      material_fuer: int | None = None, auspacken: bool = False) -> dict:
        """Eine Datei aus dem Browser: ein Werk (mit Vorschau, BF-80; ohne genannte Vorschau bekommt sie eine eigene) oder
        Begleitmaterial zu einem Buch (`material_fuer`, ohne Vorschau; eine ZIP auf Wunsch ausgepackt)."""
        offen = await db.fetch_one("SELECT id FROM aufnahme WHERE sha256 = ? AND name = ? AND stand IN ('wartet', 'laedt', 'angehalten') "
                                   "AND COALESCE(material_fuer, 0) = ? ORDER BY id DESC", (sha256, name, material_fuer or 0)) if sha256 else None
        if offen:
            await self._stand_holen(offen["id"])
            return await self.einer(offen["id"])
        stand, schritt, text, buch = await self._vorab(name, groesse, sha256, material_fuer)
        if material_fuer is None:
            vorschau_id = vorschau_id or await vorschau.anlegen(name, "hochladen")
        c = await db.execute("INSERT INTO aufnahme(name, groesse, sha256, stand, schritt, text, buch_id, anreichern, vorschau, material_fuer, entpacken) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (name, groesse, sha256, stand, schritt, text, buch, int(anreichern), vorschau_id, material_fuer, int(auspacken)))
        nr = c.lastrowid
        await db.commit()
        if stand == "wartet" and wolke.bereit:
            try:
                u = await wolke.upload_anlegen(f"{nr} {sauber(name, 180)}", await self._eingang_ordner(), groesse, sha256)
                await self._setze(nr, upload=u["id"])
            except WolkeFehler as f:
                await self._setze(nr, stand="fehler", text=f.meldung)
        for e in self._neu:
            e.set()
        return await self.einer(nr)

    async def _vorab(self, name: str, groesse: int, sha256: str, material_fuer: int | None = None) -> tuple[str, int, str, int | None]:
        """Was sich ohne den Inhalt sagen lässt: Stand, Schritt, Text und die Nummer des Buchs, wenn es das schon gibt.
        Begleitmaterial darf jedes Format haben; eine ZIP aus dem Browser wird ausgepackt."""
        if groesse <= 0:
            return "kaputt", 0, "Die Datei ist leer. Nicht eingetragen.", None
        if material_fuer is not None:
            da = await db.fetch_one("SELECT buch_id FROM buch_material WHERE buch_id = ? AND sha256 = ?", (material_fuer, sha256)) if sha256 else None
            if da:
                return "da", 0, "Gibt es schon als Begleitmaterial zu diesem Buch", material_fuer
            return "wartet", 1, "Bereit zum Hochladen", None
        if Path(name).suffix.lower() not in SUPPORTED_FORMATS and Path(name).suffix.lower() != ".zip":
            return "format", 0, f"Dieses Format kann die Bibliothek nicht lesen. Möglich sind {FORMATE} und ZIP.", None
        if da := await self._schon_da(sha256):
            return "da", 0, da[1], da[0]
        return "wartet", 1, "Bereit zum Hochladen", None

    @staticmethod
    async def _schon_da(sha256: str) -> tuple[int, str] | None:
        """Das Buch, das diese Datei schon hat (als Original oder als weiteres Format), mit dem Satz dazu."""
        if not sha256:
            return None
        if da := await db.fetch_one("SELECT id, title FROM books WHERE hash = ?", (sha256,)):
            return da["id"], f"Gibt es schon: \"{da['title']}\" hat denselben Inhalt"
        if da := await db.fetch_one("SELECT b.id, b.title, d.format FROM buch_datei d JOIN books b ON b.id = d.buch_id WHERE d.hash = ?", (sha256,)):
            return da["id"], f"Gibt es schon: \"{da['title']}\" hat diese Datei als {da['format'].upper()}"
        return None

    async def aus_wolke(self, k: dict) -> None:
        """Eine Datei, die schon in der Kellerwolke liegt (Eingangsordner): gleich zum Lesen, ohne Hochladen."""
        stand, schritt, text, buch = await self._vorab(k["name"], k["groesse"], k["sha256"])
        if Path(k["name"]).suffix.lower() == ".zip" and stand == "wartet":    # ZIP nur aus dem Browser
            stand, schritt, text = "format", 0, f"Eine ZIP nimmt nur das Hochladen im Browser. Möglich sind hier {FORMATE}."
        if stand == "wartet":
            stand, schritt, text = "liest", 2, "Wartet auf das Lesen"
        await db.execute("INSERT INTO aufnahme(name, groesse, sha256, stand, schritt, text, buch_id, knoten, empfangen, anteil, quelle) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'eingangsordner')",
                         (k["name"], k["groesse"], k["sha256"], stand, schritt, text, buch, k["id"], k["groesse"]))
        await db.commit()
        self._weiter()

    async def aus_ordner(self, dateien: list[Path], quelle: str, anreichern: bool = False) -> int:
        """Dateien aus einem Ordner auf dem Gerät. Aus Einlese-Ordner und externer Sammlung bleiben sie, wo sie sind, und was
        schon in Arbeit, aufgenommen, wartend oder verworfen ist (gleicher Ort, gleiche Größe), kommt nicht noch einmal. Aus
        dem Eingangsordner ziehen sie beim Aufnehmen um; was dort liegen bleibt (gibt es schon, unlesbar, entfernt), kommt nie
        noch einmal."""
        staende = "" if quelle == "eingangsordner" else \
            "AND stand IN ('liest', 'angaben', 'regal', 'wissen', 'fertig', 'da', 'ohne_text', 'bestaetigen', 'verworfen')"
        bekannt = {(z["pfad"], z["groesse"]) for z in await db.fetch_all(
            f"SELECT pfad, groesse FROM aufnahme WHERE pfad IS NOT NULL {staende}")}
        neu = 0
        for datei in dateien:
            groesse = datei.stat().st_size
            if (str(datei), groesse) in bekannt:
                continue
            stand, schritt, text, buch = await self._vorab(datei.name, groesse, "")
            if datei.suffix.lower() == ".zip" and stand == "wartet":
                stand, schritt, text = "format", 0, f"Eine ZIP nimmt nur das Hochladen im Browser. Möglich sind hier {FORMATE}."
            if stand == "wartet":
                stand, schritt, text = "liest", 2, "Wartet auf das Lesen"
            await db.execute("INSERT INTO aufnahme(name, groesse, stand, schritt, text, buch_id, empfangen, anteil, anreichern, quelle, pfad) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)", (datei.name, groesse, stand, schritt, text, buch, groesse, int(anreichern), quelle, str(datei)))
            neu += 1
        await db.commit()
        self._weiter()
        return neu

    @staticmethod
    async def gemeinfrei_in_arbeit(nummer: int) -> bool:
        """Wird dieses gemeinfreie Buch gerade geholt oder gelesen?"""
        return await db.fetch_one("SELECT id FROM aufnahme WHERE quelle = ? AND json_extract(herkunft, '$.gutenberg_id') = ? AND stand IN ('liest', 'angaben', 'regal')",
                                  (gemeinfrei.QUELLE, nummer)) is not None

    async def aus_gemeinfrei(self, buecher: list[dict], vorschau: str | None = None) -> int:
        """Gemeinfreie Bücher aus der Suche: geholt wird beim Lesen. Was es schon gibt oder schon geholt wird, kommt nicht noch
        einmal; ohne Datei ist es gleich ein Fehler mit Grund. Mit `vorschau` (in die Lücke holen, BF-98) halten sie dort vor
        dem Regal; sonst halten gemeinfreie Bücher nie."""
        neu = 0
        for b in buecher:
            nummer = int(b.get("gutenberg_id") or 0)
            adresse = str(b.get("download_url") or "")
            titel = str(b.get("titel") or f"Gutenberg {nummer}")
            if await self.gemeinfrei_in_arbeit(nummer):
                continue
            da = await gemeinfrei.schon_da(nummer)
            if da:
                stand, schritt, text, buch = "da", 0, f"Gibt es schon: \"{da['title']}\"", da["id"]
            elif not adresse:
                stand, schritt, text, buch = "fehler", 0, "Zu diesem Buch gibt es keine Datei", None
            else:
                stand, schritt, text, buch = "liest", 2, "Wartet auf das Holen", None
            herkunft = {"gutenberg_id": nummer, "download_url": adresse, "cover_url": str(b.get("cover_url") or ""), "titel": titel}
            name = sauber(titel, 150) + (".txt" if ".txt" in adresse else ".epub")
            await db.execute("INSERT INTO aufnahme(name, groesse, stand, schritt, text, buch_id, anteil, quelle, herkunft, vorschau) VALUES (?, 0, ?, ?, ?, ?, 1, ?, ?, ?)",
                             (name, stand, schritt, text, buch, gemeinfrei.QUELLE, json.dumps(herkunft, ensure_ascii=False), vorschau))
            neu += 1
        await db.commit()
        self._weiter()
        return neu

    def _weiter(self) -> None:
        self._arbeit.set()
        for e in self._neu:
            e.set()

    async def _eingang_ordner(self) -> str:
        if self._eingang is None:
            self._eingang = (await wolke.ordner(f"{settings.ablage_ordner}/Eingang"))["id"]
        return self._eingang

    async def _stand_holen(self, nr: int) -> int:
        z = await db.fetch_one("SELECT upload, empfangen FROM aufnahme WHERE id = ?", (nr,))
        if z["upload"]:
            try:
                await self._setze(nr, empfangen=(await wolke.upload_stand(z["upload"]))["empfangen"])
            except WolkeFehler as f:
                logger.warning("Stand von Aufnahme %d nicht geholt: %s", nr, f)
        return (await db.fetch_one("SELECT empfangen FROM aufnahme WHERE id = ?", (nr,)))["empfangen"]

    async def teil(self, nr: int, versatz: int, strom: AsyncIterator[bytes], laenge: int) -> dict:
        z = await db.fetch_one("SELECT * FROM aufnahme WHERE id = ?", (nr,))
        if z["stand"] not in ("wartet", "laedt", "angehalten"):
            return _aussen(z)
        if versatz != z["empfangen"]:
            raise Versatz(await self._stand_holen(nr))
        if versatz + laenge > z["groesse"]:
            raise ZuViel()
        if z["upload"]:
            try:
                u = await wolke.upload_teil(z["upload"], versatz, strom, laenge)
            except WolkeFehler as f:
                if f.status in (0, 409, 423, 502, 503, 504):
                    raise Versatz(await self._stand_holen(nr)) from f
                await self._setze(nr, stand="fehler", text=f.meldung)
                raise
            empfangen, knoten = u["empfangen"], (u.get("knoten") or {}).get("id")
        else:
            empfangen, knoten = await self._teil_hier(z, strom, laenge), None
        fertig = empfangen >= z["groesse"]
        await self._setze(nr, empfangen=empfangen, anteil=empfangen / z["groesse"], knoten=knoten or z["knoten"], stand="liest" if fertig else "laedt", schritt=2 if fertig else 1,
                          text="Wartet auf das Lesen" if fertig else f"Wird abgelegt, {mb(empfangen)} von {mb(z['groesse'])}")
        if fertig:
            self._arbeit.set()
        return await self.einer(nr)

    @staticmethod
    def _zwischen() -> Path:
        return settings.eingang_dir

    @classmethod
    def _hier(cls, z: dict) -> Path:
        """Ablage ohne Kellerwolke: ein Ordner je Aufnahme im Eingang auf dem Gerät (dauerhaft, eine Vorschau wartet auch
        über einen Neustart), damit der Name der Datei (und so der Titel) bleibt, wie er ist; nur ein zu langer Name wird
        gekürzt."""
        return cls._zwischen() / str(z["id"]) / dateiname(Path(z["name"]).name)

    async def _teil_hier(self, z: dict, strom: AsyncIterator[bytes], laenge: int) -> int:
        """Ohne Kellerwolke (Entwicklung): das Teil landet im Eingang auf dem Gerät, nie mehr als angesagt. Bricht es ab, gilt
        nur, was vorher da war."""
        ziel = self._hier(z)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        if (da := ziel.stat().st_size if ziel.exists() else 0) < z["empfangen"]:        # verloren: dort weiter, wo es steht
            await self._setze(z["id"], empfangen=da, anteil=da / z["groesse"])
            raise Versatz(da)
        geschrieben = 0
        with ziel.open("r+b" if z["empfangen"] and ziel.exists() else "wb") as f:
            f.seek(z["empfangen"])
            try:
                async for stueck in strom:
                    geschrieben += len(stueck)
                    if geschrieben > laenge:
                        raise ZuViel()
                    f.write(stueck)
            except BaseException:
                f.truncate(z["empfangen"])
                raise
        return ziel.stat().st_size

    def _leere_ordner_raeumen(self, ordner: Path | None = None) -> None:
        """Leere Ordner im Eingang auf dem Gerät gehen: einer nach dem Ablegen, alle beim Start."""
        eingang = self._zwischen()
        for o in [ordner] if ordner else (list(eingang.iterdir()) if eingang.is_dir() else []):
            if o.parent == eingang and o.is_dir() and not any(o.iterdir()):
                o.rmdir()

    def _auf_dem_geraet(self, z: dict) -> Path | None:
        """Die Datei der Aufnahme auf dem Gerät, wenn sie dort liegt (Eingang oder Ordner)."""
        hier = self._hier(z)
        if hier.exists():
            return hier
        return Path(z["pfad"]) if z["pfad"] and Path(z["pfad"]).is_file() else None

    # -- Bedienung -----------------------------------------------------------------------------------------------------
    async def entfernen(self, nr: int) -> None:
        await self._entfernen(await db.fetch_all("SELECT * FROM aufnahme WHERE id = ?", (nr,)))

    async def aufraeumen(self, quelle: str | None, staende: list[str] | None) -> int:
        """Viele auf einmal entfernen, wie einzeln: nach Quelle, nach Stand oder beidem (sichtbare Einträge). Liefert, wie
        viele es waren."""
        bedingungen, werte = ["ausgeblendet = 0"], []
        if quelle:
            bedingungen.append("quelle = ?")
            werte.append(quelle)
        if staende:
            bedingungen.append(f"stand IN ({','.join('?' * len(staende))})")
            werte.extend(staende)
        zeilen = await db.fetch_all(f"SELECT * FROM aufnahme WHERE {' AND '.join(bedingungen)}", tuple(werte))
        await self._entfernen(zeilen)
        return len(zeilen)

    async def _entfernen(self, zeilen: list[dict]) -> None:
        """Laufende Uploads abbrechen (erst alles draußen, dann die Liste in einem Zug), angefangene Dateien im Eingang auf dem
        Gerät gehen mit. Ein eingetragenes Buch bleibt."""
        offen = [z for z in zeilen if z["stand"] in ("wartet", "laedt", "angehalten")]
        for z in offen:
            if z["upload"]:
                try:
                    await wolke.upload_abbrechen(z["upload"])
                except WolkeFehler as f:
                    logger.info("Upload %s nicht abgebrochen: %s", z["upload"], f)
            elif z["quelle"] == "hochladen":
                angefangen = self._hier(z)
                angefangen.unlink(missing_ok=True)
                self._leere_ordner_raeumen(angefangen.parent)
        # Aus dem Eingangsordner bleibt der Eintrag gemerkt, sonst nähme er dieselbe Datei gleich noch einmal auf
        merken = [z["id"] for z in zeilen if z["knoten"] or z["quelle"] == "eingangsordner"]
        weg = [z["id"] for z in zeilen if z["id"] not in merken]
        async with db.einheit():
            for sql, nummern in (("UPDATE aufnahme SET ausgeblendet = 1 WHERE id = ?", merken), ("DELETE FROM aufnahme WHERE id = ?", weg)):
                await db.execute_many(sql, [(n,) for n in nummern])
        for e in self._neu:
            e.set()

    async def erneut(self, nr: int) -> dict | None:
        z = await db.fetch_one("SELECT knoten, empfangen, groesse, pfad, quelle, stand FROM aufnahme WHERE id = ?", (nr,))
        if z is None:
            return None
        if z["stand"] in ("verworfen", WARTET):          # verworfen bleibt verworfen; wer wartet, wartet auf die Vorschau
            return await self.einer(nr)
        if z["pfad"] or z["quelle"] == gemeinfrei.QUELLE or z["empfangen"] >= z["groesse"] > 0:
            await self._setze(nr, stand="liest", schritt=2, text="Wartet auf das Lesen", versuche=0)
            self._arbeit.set()
        else:
            await self._setze(nr, stand="angehalten", schritt=1, text="Bitte die Datei noch einmal wählen")
        return await self.einer(nr)

    async def ausblenden(self) -> None:
        await db.execute("UPDATE aufnahme SET ausgeblendet = 1 WHERE stand IN ('fertig', 'wissen', 'da', 'ohne_text')")
        await db.commit()
        for e in self._neu:
            e.set()

    async def wissen_pruefen(self) -> None:
        """Aufnahmen, deren Bedeutung noch fehlt: sobald der Fundus das Buch durchsuchbar hat, sind sie fertig."""
        from backend.app.services import bedeutung

        for z in await db.fetch_all("SELECT id, buch_id FROM aufnahme WHERE stand = 'wissen' AND buch_id IS NOT NULL ORDER BY id LIMIT 20"):
            s = await bedeutung.buch_stand(z["buch_id"])
            if s and s["zustand"] == "durchsuchbar" and s["abschnitte"] > 1:
                await self._setze(z["id"], stand="fertig", schritt=6, text=f"Fertig, überall zu finden ({s['abschnitte']} Abschnitte)")

    # -- Auswertung ----------------------------------------------------------------------------------------------------
    async def _arbeiten(self) -> None:
        while True:
            try:
                z = await db.fetch_one(NAECHSTE)
            except Exception:                              # noqa: BLE001 - die Schleife darf nie still enden
                logger.exception("Aufnahmen nicht lesbar")
                await asyncio.sleep(10)
                continue
            if z is None:
                self._arbeit.clear()
                try:
                    await asyncio.wait_for(self._arbeit.wait(), 30)
                except TimeoutError:
                    pass
                continue
            try:
                await self._verarbeiten(z)
            except asyncio.CancelledError:
                raise
            except Exception as f:                         # noqa: BLE001 - eine Aufnahme darf die übrigen nie aufhalten
                logger.exception("Aufnahme %d", z["id"])
                warten = z["versuche"] < 3 and isinstance(f, WolkeFehler)
                await self._setze(z["id"], versuche=z["versuche"] + 1, **({} if warten else {"stand": "fehler", "text": getattr(f, "meldung", "") or f"{type(f).__name__}: {f}"}))
                await asyncio.sleep(10 if warten else 0)

    async def _datei(self, z: dict) -> Path:
        hier = self._hier(z)
        if hier.exists():
            return hier
        if z["pfad"]:
            if not Path(z["pfad"]).is_file():
                raise AnnahmeFehler("Die Datei liegt nicht mehr im Ordner")
            return Path(z["pfad"])
        if z["quelle"] == gemeinfrei.QUELLE:
            await self._setze(z["id"], text="Wird geholt")
            try:
                return await gemeinfrei.holen(z, hier)
            except QuelleFehler as f:
                raise AnnahmeFehler(f.grund) from f
        await db.execute("INSERT OR IGNORE INTO ablage_datei(hash, knoten, name, groesse) VALUES (?, ?, ?, ?)", (z["sha256"], z["knoten"], Path(z["name"]).name, z["groesse"]))
        await db.commit()
        pfad = await asyncio.to_thread(originale.holen, z["sha256"])
        if pfad is None:
            raise WolkeFehler("Das Original kommt gerade nicht aus der Kellerwolke")
        return pfad

    async def _anderswo(self, z: dict) -> dict | None:
        """Das Buch, dem derselbe Inhalt unter einem anderen Knoten schon gehört (zweimal abgelegt, bevor das erste fertig war)."""
        if not z["knoten"]:
            return None
        return await db.fetch_one("SELECT b.id, b.title FROM books b JOIN ablage_datei a ON a.hash = b.hash WHERE b.hash = ? AND a.knoten != ?", (z["sha256"], z["knoten"]))

    async def _verarbeiten(self, z: dict) -> None:
        if z["material_fuer"] and not ist_zip(z):
            return await self._als_material(z)
        if ist_zip(z):
            return await self._entpacken(z)
        zo = zuordnung_aus(z)
        if zo is not None and zo.bestaetigt and zo.art.wert == MATERIAL:
            return await self._material_aus_vorschau(z, zo)
        if zo is not None and zo.bestaetigt and zo.doppel.wahl == "format":
            return await self._weiteres_format(z, zo)
        gelesen = await self._lesen(z)
        if gelesen is None:
            return
        e, pfad, summe, neu_gelesen = gelesen
        z = await self._zeile(z["id"])                       # frisch: vielleicht ist sie inzwischen bestätigt
        zo = zuordnung_aus(z)
        if z["vorschau"] and not (zo and zo.bestaetigt):
            return await self._zur_bestaetigung(z, e, summe)
        if zo is not None and neu_gelesen:                  # bestätigt, bevor sie gelesen war: die Regeln nachholen
            zo = behalten(zo, await zuordnen.vorschlagen(await self._lage(z, summe), Gelesen.von(e, None)))
        await self._ins_regal(z, e, pfad, summe, zo)

    async def _vorschau_zuweisen(self, z: dict) -> dict:
        """Eingangsordner und Ordner auf dem Gerät halten nur, wenn es eingestellt ist; dann gehört die Aufnahme zur offenen
        Vorschau ihrer Quelle."""
        if z["vorschau"] or z["quelle"] == "hochladen" or not await einstellungen.halten(z["quelle"]):
            return z
        nr = await vorschau.der_quelle(z["quelle"], NAME_DER_QUELLE.get(z["quelle"], z["quelle"]))
        await self._setze(z["id"], vorschau=nr)
        return {**z, "vorschau": nr}

    async def _lesen(self, z: dict) -> tuple[auswertung.Ergebnis, Path | None, str, bool] | None:
        """Text, Umschlag und Angaben: schon gelesen (eine bestätigte Vorschau) aus dem Gemerkten, sonst aus der Datei.
        None, wenn die Aufnahme hier endet (gibt es schon, unlesbar)."""
        nr, name = z["id"], Path(z["name"]).name
        if g := gelesen_aus(z):
            volltext = await asyncio.to_thread(load_fulltext, z["sha256"]) or ""
            bild = get_sidecar_path(z["sha256"], "cover.jpg")
            return g.ergebnis(volltext, bild.read_bytes() if g.umschlag and bild.is_file() else None), self._auf_dem_geraet(z), z["sha256"], False
        z = await self._vorschau_zuweisen(z)
        await self._setze(nr, stand="liest", schritt=2, anteil=0, text="Text und Umschlag werden gelesen")
        if da := await self._anderswo(z):
            await self._setze(nr, stand="da", schritt=0, anteil=1, buch_id=da["id"], text=f"Gibt es schon: \"{da['title']}\" hat denselben Inhalt")
            return None
        pfad = await self._datei(z)
        summe = z["sha256"]
        if not summe:                                    # Ordner und gemeinfreie Bücher: erst jetzt bekannt
            summe = await asyncio.to_thread(compute_hash, pfad)
            await self._setze(nr, sha256=summe, groesse=z["groesse"] or pfad.stat().st_size)
            if da := await self._schon_da(summe):
                await self._setze(nr, stand="da", schritt=0, anteil=1, buch_id=da[0], text=da[1])
                return None
        e = await auswertung.auswerten(pfad)
        if not e.lesbar:
            await self._zu_klaeren(z)
            await self._setze(nr, stand="kaputt", schritt=0, text=e.grund + ". Nicht eingetragen.")
            return None
        await self._setze(nr, stand="angaben", schritt=3, text="Angaben werden ergänzt")
        if z["anreichern"]:
            await angaben.ergaenzen(e, pfad.stem)
        return e, pfad, summe, True

    async def _lage(self, z: dict, summe: str) -> zuordnen.Lage:
        teile = (z["zip_pfad"] or "").split("/")[:-1]
        v = await vorschau.offene(z["vorschau"]) if z["vorschau"] else None
        zip_name = (await self._zeile(z["teil_von"]))["name"] if z["teil_von"] else ""
        return zuordnen.Lage(aufnahme=z["id"], name=Path(z["name"]).name, sha256=summe, ordner=[t for t in teile if t], zip_name=zip_name,
                             vorschau=z["vorschau"] or "", vorgabe=vorschau.vorgabe_aus(v) if v else Vorgabe())

    async def _zur_bestaetigung(self, z: dict, e: auswertung.Ergebnis, summe: str) -> None:
        """Halt vor dem Regal: das Gelesene merken (Text und Umschlag bei der Prüfsumme), die Regeln schlagen vor, die KI
        ergänzt später. Ins Regal, in die Suche und in die Zähler kommt nichts."""
        schlicht = deckblatt.schlicht(e.cover_data) if e.cover_data else True
        await asyncio.to_thread(self._gelesenes_ablegen, summe, e)
        g = Gelesen.von(e, schlicht)
        zo = behalten(zuordnung_aus(z), await zuordnen.vorschlagen(await self._lage(z, summe), g))
        ki_stand = "offen" if ki.bereit and zuordnen.ki_noetig(zo) else ""
        await self._setze(z["id"], gelesen=g.model_dump_json(), zuordnung=zo.model_dump_json(), ki_stand=ki_stand, stand=WARTET, schritt=4, anteil=1,
                          text="Wartet auf die Bestätigung")
        if ki_stand:
            ki_vorschau.anstossen()

    @staticmethod
    def _gelesenes_ablegen(summe: str, e: auswertung.Ergebnis) -> None:
        save_metadata(summe, {"titel": e.title, "autor": e.author, "isbn": e.isbn, "verlag": e.publisher, "jahr": e.year, "sprache": e.language,
                              "beschreibung": e.description, "seiten": e.page_count})
        if e.fulltext:
            save_fulltext(summe, e.fulltext)
        if e.cover_data:
            save_cover(summe, e.cover_data)

    async def _ins_regal(self, z: dict, e: auswertung.Ergebnis, pfad: Path | None, summe: str, zo: Zuordnung | None) -> None:
        nr, name = z["id"], Path(z["name"]).name
        await self._setze(nr, stand="regal", schritt=4, text="Kommt ins Regal")
        buch = await eintragen(summe, name, z["groesse"] or (pfad.stat().st_size if pfad else 0), e)
        if zo is not None:
            await uebernehmen.felder_setzen(buch, zo)
        if pfad is None and not z["knoten"]:
            pfad = await self._datei(z)
        await self._ablegen(z, buch, summe, name, pfad)
        if z["quelle"] == gemeinfrei.QUELLE:
            await gemeinfrei.nachher(z, buch, summe)
        codestellen.vormerken(buch)                               # Codestellen im Hintergrund, sobald das Original liegt
        stand, schritt, text = self._am_ziel(e.fulltext)
        await self._setze(nr, buch_id=buch, schritt=schritt, anteil=1, stand=stand, text=text)

    async def _ziel_oder_fehler(self, z: dict, zo: Zuordnung) -> int | None:
        buch = await uebernehmen.ziel_buch(zo)
        if buch is None or await db.fetch_one("SELECT 1 AS da FROM books WHERE id = ?", (buch,)) is None:
            await self._setze(z["id"], stand="fehler", schritt=0, text=f"Das Buch dazu ({zo.ziel.titel if zo.ziel else '?'}) ist nicht im Regal")
            return None
        return buch

    async def _weiteres_format(self, z: dict, zo: Zuordnung) -> None:
        """Ein weiteres Format zum Buch: neben das Original, als eigene Datei des Buchs (ablage/formate.py)."""
        if (buch := await self._ziel_oder_fehler(z, zo)) is None:
            return
        nr, name = z["id"], Path(z["name"]).name
        await self._setze(nr, stand="regal", schritt=4, text="Kommt als weiteres Format zum Buch")
        if await formate.hat_format(buch, formate.endung(name)):
            await self._setze(nr, stand="fehler", schritt=0, text=f"Das Buch hat schon ein {formate.endung(name).upper()}")
            return
        pfad = None if z["knoten"] else (self._auf_dem_geraet(z) or await self._datei(z))
        summe = z["sha256"] or await asyncio.to_thread(compute_hash, pfad)
        await formate.ablegen(buch, summe, name, knoten=z["knoten"], pfad=pfad, behalten=z["quelle"] in BEHALTEN)
        try:
            await formate.eintragen(buch, summe, name, z["groesse"])
        except formate.FormatDa as f:
            await self._setze(nr, stand="fehler", schritt=0, text=f.meldung)
            return
        await db.commit()
        await asyncio.to_thread(self._gelesenes_weg, summe)
        if pfad is not None and z["quelle"] not in BEHALTEN:
            self._leere_ordner_raeumen(pfad.parent)
        titel = (await db.fetch_one("SELECT title FROM books WHERE id = ?", (buch,)))["title"]
        await self._setze(nr, stand="fertig", schritt=6, anteil=1, buch_id=buch, text=f"Als weiteres Format ({formate.endung(name).upper()}) bei \"{titel}\"")

    @staticmethod
    def _gelesenes_weg(summe: str) -> None:
        """Was die Vorschau zur Prüfsumme abgelegt hat, wenn die Datei kein eigenes Buch wird (die Datei selbst bleibt)."""
        for n in ("metadata.json", "fulltext.txt", "cover.jpg"):
            get_sidecar_path(summe, n).unlink(missing_ok=True)

    async def _material_aus_vorschau(self, z: dict, zo: Zuordnung) -> None:
        if (buch := await self._ziel_oder_fehler(z, zo)) is None:
            return
        original = await db.fetch_one("SELECT file_name FROM books WHERE id = ?", (buch,))
        bezug = (await self._zeile(zo.ziel.aufnahme))["name"] if zo.ziel and zo.ziel.aufnahme else original["file_name"]
        await self._in_material(z, buch, zugehoerig.als_material(Path(z["name"]).name, bezug), "hochladen")
        if z["sha256"]:
            await asyncio.to_thread(self._gelesenes_weg, z["sha256"])

    async def _als_material(self, z: dict) -> None:
        """Material von der Buchseite (BF-81): ohne Vorschau zum Buch."""
        if await db.fetch_one("SELECT 1 AS da FROM books WHERE id = ?", (z["material_fuer"],)) is None:
            await self._setze(z["id"], stand="fehler", schritt=0, text="Das Buch gibt es nicht mehr")
            return
        await self._in_material(z, z["material_fuer"], Path(z["name"]).name, "buchseite")

    async def _in_material(self, z: dict, buch: int, name: str, herkunft: str) -> None:
        await self._setze(z["id"], stand="regal", schritt=4, text="Kommt als Begleitmaterial zum Buch")
        pfad = None if z["knoten"] else (self._auf_dem_geraet(z) or await self._datei(z))
        m = await material.aufnehmen(buch, name, herkunft, datei=pfad, knoten=z["knoten"], behalten=z["quelle"] in BEHALTEN,
                                     groesse=z["groesse"], sha256=z["sha256"])
        if pfad is not None and z["quelle"] not in BEHALTEN:
            self._leere_ordner_raeumen(pfad.parent)
        titel = (await db.fetch_one("SELECT title FROM books WHERE id = ?", (buch,)))["title"]
        await self._setze(z["id"], stand="fertig", schritt=6, anteil=1, buch_id=buch, text=f"Begleitmaterial zu \"{titel}\": {m.name}")

    # -- ZIP -------------------------------------------------------------------------------------------------------------
    async def _zip_holen(self, z: dict) -> tuple[Path, bool]:
        """Die ZIP auf dem Gerät; True, wenn es eine Kopie aus der Kellerwolke ist (danach weg)."""
        if hier := self._auf_dem_geraet(z):
            return hier, False
        ziel = settings.zwischen_dir / "entpacken" / f"{z['id']}.zip"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(wolke.holen, z["knoten"], ziel)
        return ziel, True

    async def _entpacken(self, z: dict) -> None:
        """Eine ZIP Teil für Teil: je Eintrag eine Aufnahme derselben Vorschau (oder, als Material von der Buchseite, zum Buch).
        Was schon ausgepackt ist, bleibt (nach einem Neustart geht es beim nächsten weiter); die ZIP selbst bleibt im Eingang."""
        nr = z["id"]
        await self._setze(nr, stand="entpacken", schritt=2, anteil=0, text="Wird ausgepackt")
        zipdatei, kopie = await self._zip_holen(z)
        try:
            grenzen = (await einstellungen.lesen()).zip
            try:
                eintraege = await asyncio.to_thread(entpacken.verzeichnis, zipdatei, grenzen)
            except entpacken.ZipFehler as f:
                await self._setze(nr, stand="kaputt", schritt=0, text=f"{f.meldung}. Nicht ausgepackt.")
                return
            reihe = sorted(eintraege, key=lambda e: ("buch", "material", "rest", "nicht").index(e.einteilung))
            schon = {c["zip_pfad"]: c for c in await db.fetch_all("SELECT * FROM aufnahme WHERE teil_von = ?", (nr,))}
            zeilen: dict[int, int] = {}
            namen = {x.nr: x.name for x in eintraege}
            for i, e in enumerate(reihe, 1):
                c = schon.get(e.pfad)
                if c is None or c["stand"] == "entpacken":
                    c = await self._teil_auspacken(z, zipdatei, e, c, zeilen, namen, grenzen.datei_bytes)
                zeilen[e.nr] = c["id"]
                await self._setze(nr, anteil=i / len(reihe), text=f"Wird ausgepackt, {i} von {len(reihe)}")
            await self._setze(nr, stand="entpackt", schritt=4, anteil=1, text=f"{len(reihe)} {'Datei' if len(reihe) == 1 else 'Dateien'} ausgepackt, "
                                                                            f"die ZIP bleibt im Eingang")
        finally:
            if kopie:
                zipdatei.unlink(missing_ok=True)
        self._weiter()

    async def _teil_auspacken(self, z: dict, zipdatei: Path, e: entpacken.Eintrag, c: dict | None, zeilen: dict[int, int], namen: dict[int, str],
                              grenze: int) -> dict:
        if c is None:
            k = await db.execute("INSERT INTO aufnahme(name, groesse, stand, schritt, text, quelle, vorschau, teil_von, zip_pfad, material_fuer, anteil) "
                                 "VALUES (?, ?, 'entpacken', 2, 'Wird ausgepackt', ?, ?, ?, ?, ?, 0)",
                                 (e.name, e.groesse, z["quelle"], z["vorschau"], z["id"], e.pfad, z["material_fuer"]))
            await db.commit()
            c = await self._zeile(k.lastrowid)
        if e.einteilung == "nicht":
            await self._setze(c["id"], stand="format", schritt=0, text=f"Nicht ausgepackt: {e.grund}", zuordnung=Zuordnung(nicht=e.grund).model_dump_json())
            return await self._zeile(c["id"])
        ziel = self._hier(c) if not wolke.bereit else settings.zwischen_dir / "entpacken" / str(z["id"]) / str(c["id"])
        try:
            groesse, summe = await asyncio.to_thread(entpacken.auspacken, zipdatei, e, ziel, grenze)
        except (entpacken.ZuGross, zipfile.BadZipFile, zipfile.LargeZipFile, OSError, EOFError, NotImplementedError) as f:
            grund = "Größer als angegeben, nicht ausgepackt" if isinstance(f, entpacken.ZuGross) else f"Beschädigt, nicht ausgepackt ({type(f).__name__})"
            await self._setze(c["id"], stand="format", schritt=0, text=grund, zuordnung=Zuordnung(nicht=grund).model_dump_json())
            return await self._zeile(c["id"])
        knoten = None
        if wolke.bereit:
            ordner = f"{settings.ablage_ordner}/Eingang/{z['id']} {sauber(zugehoerig.stamm(z['name']), 100)}"
            await wolke.ordner(ordner)
            try:
                knoten = (await wolke.datei_schreiben(f"{ordner}/{c['id']} {sauber(e.name, 180)}", ziel))["id"]
            finally:
                ziel.unlink(missing_ok=True)
        felder = {"groesse": groesse, "sha256": summe, "knoten": knoten, "empfangen": groesse, "anteil": 1}
        if z["material_fuer"] or e.einteilung == "buch":
            felder |= {"stand": "liest", "schritt": 2, "text": "Wartet auf das Lesen"}
        elif e.einteilung == "material":
            buchzeile = zeilen.get(e.zu) if e.zu is not None else None
            zo = Zuordnung(art=Wert[str](wert=MATERIAL, herkunft="datei"),
                           ziel=Ziel(aufnahme=buchzeile, titel=zugehoerig.stamm(namen.get(e.zu, ""))) if buchzeile else None)
            felder |= {"stand": WARTET, "schritt": 4, "text": "Wartet auf die Bestätigung", "zuordnung": zo.model_dump_json()}
        else:
            felder |= {"stand": WARTET, "schritt": 4, "text": f"Nicht übernommen: {e.grund}", "zuordnung": Zuordnung(nicht=e.grund).model_dump_json()}
        await self._setze(c["id"], **felder)
        return await self._zeile(c["id"])

    async def _ablegen(self, z: dict, buch: int, summe: str, name: str, pfad: Path | None) -> None:
        """Das Original an seinen Ort: liegt es schon in der Kellerwolke, dort umziehen; sonst mit Kellerwolke dorthin
        schreiben, ohne sie in den Speicher des Geräts. Aus Einlese-Ordner und externer Sammlung bleibt die Datei, wo sie
        ist (Kopie); alles andere zieht um (Eingang auf dem Gerät, Eingangsordner auf dem Gerät)."""
        if z["knoten"]:
            await ablegen(buch, z["knoten"])
            return
        assert pfad is not None
        behalten_ = z["quelle"] in BEHALTEN
        if wolke.bereit:
            await wolke.ordner(f"{settings.ablage_ordner}/Eingang")
            k = await wolke.datei_schreiben(f"{settings.ablage_ordner}/Eingang/{summe[:12]} {sauber(name, 180)}", pfad)
            await ablegen(buch, k["id"])
            if not behalten_:
                pfad.unlink(missing_ok=True)
                self._leere_ordner_raeumen(pfad.parent)
            return
        ziel = get_storage_path(summe) / dateiname(name)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2 if behalten_ else shutil.move, pfad, ziel)      # auch über Datenträger hinweg
        if not behalten_:
            self._leere_ordner_raeumen(pfad.parent)

    @staticmethod
    def _am_ziel(volltext: str) -> tuple[str, int, str]:
        if not volltext.strip():
            return "ohne_text", 6, "In der Bibliothek. Nur Bilder, kein Text: nicht im Volltext zu finden."
        if not anschluesse().bedeutung:
            return "fertig", 6, "Fertig, in der Bibliothek zu finden"
        return "wissen", 5, "In der Bibliothek. Die Bedeutung folgt mit dem nächsten Abgleich."

    async def _zu_klaeren(self, z: dict) -> None:
        """Eine unlesbare Datei wird nie gelöscht, sie kommt in der Kellerwolke nach "Zu klären"."""
        await db.execute("DELETE FROM ablage_datei WHERE hash = ? AND hash NOT IN (SELECT hash FROM books)", (z["sha256"],))
        await db.commit()
        if z["knoten"]:
            ordner = await wolke.ordner(f"{settings.ablage_ordner}/Zu klären")
            await wolke.umziehen(z["knoten"], ordner["id"], f"{z['id']} {sauber(Path(z['name']).name, 180)}")


annahme = Annahme()
