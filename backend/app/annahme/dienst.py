"""Die Aufnahmen: jede Datei auf ihrem Weg in sechs Stationen (Prüfen, Wolke, Lesen, Angaben, Regal, Wissen), eine Liste für
alle Quellen: hochgeladen im Browser, der Eingangsordner, Ordner auf dem Gerät und gemeinfreie Bücher. Der Stand steht in der
Datenbank; nach einem Neustart geht jede Aufnahme dort weiter, wo sie war, auch wartende. Teile strömen vom Browser durch die
App in die Kellerwolke, ohne hier abgelegt zu werden; Dateien aus Ordnern auf dem Gerät bleiben, wo sie sind (kopiert wird
in die Kellerwolke, ohne sie in den Speicher des Geräts)."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from collections.abc import AsyncIterator
from pathlib import Path

from backend.app.ablage import originale
from backend.app.ablage.namen import dateiname, sauber
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.annahme import angaben, auswertung, gemeinfrei
from backend.app.annahme.eintragen import ablegen, eintragen
from backend.app.codestellen.dienst import codestellen
from backend.app.core.anschluesse import anschluesse
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.quellen.fehler import QuelleFehler
from backend.app.services.storage import SUPPORTED_FORMATS, compute_hash, get_storage_path

logger = logging.getLogger("buecherfreunde.annahme")
TEIL = 4 * 1024 * 1024
LAUFEND = ("wartet", "laedt", "angehalten", "liest", "angaben", "regal")
IN_ARBEIT = ("liest", "angaben", "regal")
QUELLEN = ("hochladen", "eingangsordner", "ordner", "extern", "gemeinfrei")
BEHALTEN = ("ordner", "extern")          # aus diesen Quellen bleibt die Datei, wo sie ist
KLAEREN = ("format", "kaputt", "fehler", "ohne_text")
# Zähler je Quelle: jeder Stand zählt genau einmal
IM_REGAL = ("fertig", "wissen", "ohne_text")
GESCHEITERT = ("format", "kaputt", "fehler")
STAENDE = (*LAUFEND, *IM_REGAL, "da", *GESCHEITERT)
LISTE = 300                              # so viele Einträge zeigt die Liste, die Zähler zählen alle
FORMATE = "PDF, EPUB, MOBI, TXT und MD"


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
    return {k: z[k] for k in ("id", "name", "groesse", "sha256", "empfangen", "stand", "schritt", "anteil", "text", "buch_id", "quelle", "angelegt_am", "geaendert_am")} | {"teil_groesse": TEIL}


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
        auch je Quelle (gesamt, laeuft, fertig, da, gescheitert)."""
        zeilen = [_aussen(z) for z in await db.fetch_all(f"SELECT * FROM aufnahme WHERE ausgeblendet = 0 ORDER BY id DESC LIMIT {LISTE}")]
        anzahl = {(z["quelle"], z["stand"]): z["n"] for z in await db.fetch_all(
            "SELECT quelle, stand, COUNT(*) AS n FROM aufnahme WHERE ausgeblendet = 0 GROUP BY quelle, stand")}

        def zahl(staende: tuple[str, ...], quelle: str | None = None) -> int:
            return sum(n for (q, s), n in anzahl.items() if s in staende and quelle in (None, q))

        je_quelle = {q: {"gesamt": zahl(STAENDE, q), "laeuft": zahl(LAUFEND, q), "fertig": zahl(IM_REGAL, q), "da": zahl(("da",), q),
                         "gescheitert": zahl(GESCHEITERT, q)} for q in QUELLEN}
        alle = sum(anzahl.values())
        return {"eintraege": zeilen, "weitere": max(0, alle - len(zeilen)),
                "zaehler": {"alle": alle, "laeuft": zahl(LAUFEND), "klaeren": zahl(KLAEREN), "da": zahl(("da",)), "fertig": zahl(("fertig", "wissen"))},
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

    async def _setze(self, nr: int, **felder) -> None:
        namen = ", ".join(f"{k} = ?" for k in felder)
        await db.execute(f"UPDATE aufnahme SET {namen}, geaendert_am = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?", (*felder.values(), nr))
        await db.commit()
        for e in self._neu:
            e.set()

    # -- Hochladen -----------------------------------------------------------------------------------------------------
    async def anlegen(self, name: str, groesse: int, sha256: str, anreichern: bool = False) -> dict:
        offen = await db.fetch_one("SELECT id FROM aufnahme WHERE sha256 = ? AND name = ? AND stand IN ('wartet', 'laedt', 'angehalten') ORDER BY id DESC", (sha256, name)) if sha256 else None
        if offen:
            await self._stand_holen(offen["id"])
            return await self.einer(offen["id"])
        stand, schritt, text, buch = await self._vorab(name, groesse, sha256)
        c = await db.execute("INSERT INTO aufnahme(name, groesse, sha256, stand, schritt, text, buch_id, anreichern) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                             (name, groesse, sha256, stand, schritt, text, buch, int(anreichern)))
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

    async def _vorab(self, name: str, groesse: int, sha256: str) -> tuple[str, int, str, int | None]:
        """Was sich ohne den Inhalt sagen lässt: Stand, Schritt, Text und die Nummer des Buchs, wenn es das schon gibt."""
        if Path(name).suffix.lower() not in SUPPORTED_FORMATS:
            return "format", 0, f"Dieses Format kann die Bibliothek nicht lesen. Möglich sind {FORMATE}.", None
        if groesse <= 0:
            return "kaputt", 0, "Die Datei ist leer. Nicht eingetragen.", None
        da = await db.fetch_one("SELECT id, title FROM books WHERE hash = ?", (sha256,)) if sha256 else None
        if da:
            return "da", 0, f"Gibt es schon: \"{da['title']}\" hat denselben Inhalt", da["id"]
        return "wartet", 1, "Bereit zum Hochladen", None

    async def aus_wolke(self, k: dict) -> None:
        """Eine Datei, die schon in der Kellerwolke liegt (Eingangsordner): gleich zum Lesen, ohne Hochladen."""
        stand, schritt, text, buch = await self._vorab(k["name"], k["groesse"], k["sha256"])
        if stand == "wartet":
            stand, schritt, text = "liest", 2, "Wartet auf das Lesen"
        await db.execute("INSERT INTO aufnahme(name, groesse, sha256, stand, schritt, text, buch_id, knoten, empfangen, anteil, quelle) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'eingangsordner')",
                         (k["name"], k["groesse"], k["sha256"], stand, schritt, text, buch, k["id"], k["groesse"]))
        await db.commit()
        self._weiter()

    async def aus_ordner(self, dateien: list[Path], quelle: str, anreichern: bool = False) -> int:
        """Dateien aus einem Ordner auf dem Gerät. Aus Einlese-Ordner und externer Sammlung bleiben sie, wo sie sind, und was
        schon in Arbeit oder aufgenommen ist (gleicher Ort, gleiche Größe), kommt nicht noch einmal. Aus dem Eingangsordner
        ziehen sie beim Aufnehmen um; was dort liegen bleibt (gibt es schon, unlesbar, entfernt), kommt nie noch einmal."""
        staende = "" if quelle == "eingangsordner" else "AND stand IN ('liest', 'angaben', 'regal', 'wissen', 'fertig', 'da')"
        bekannt = {(z["pfad"], z["groesse"]) for z in await db.fetch_all(
            f"SELECT pfad, groesse FROM aufnahme WHERE pfad IS NOT NULL {staende}")}
        neu = 0
        for datei in dateien:
            groesse = datei.stat().st_size
            if (str(datei), groesse) in bekannt:
                continue
            stand, schritt, text, buch = await self._vorab(datei.name, groesse, "")
            if stand == "wartet":
                stand, schritt, text = "liest", 2, "Wartet auf das Lesen"
            await db.execute("INSERT INTO aufnahme(name, groesse, stand, schritt, text, buch_id, empfangen, anteil, anreichern, quelle, pfad) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)", (datei.name, groesse, stand, schritt, text, buch, groesse, int(anreichern), quelle, str(datei)))
            neu += 1
        await db.commit()
        self._weiter()
        return neu

    async def aus_gemeinfrei(self, buecher: list[dict]) -> int:
        """Gemeinfreie Bücher aus der Suche: geholt wird beim Lesen. Was es schon gibt oder schon geholt wird, kommt nicht noch
        einmal; ohne Datei ist es gleich ein Fehler mit Grund."""
        neu = 0
        for b in buecher:
            nummer = int(b.get("gutenberg_id") or 0)
            adresse = str(b.get("download_url") or "")
            titel = str(b.get("titel") or f"Gutenberg {nummer}")
            if await db.fetch_one("SELECT id FROM aufnahme WHERE quelle = ? AND json_extract(herkunft, '$.gutenberg_id') = ? AND stand IN ('liest', 'angaben', 'regal')",
                                  (gemeinfrei.QUELLE, nummer)):
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
            await db.execute("INSERT INTO aufnahme(name, groesse, stand, schritt, text, buch_id, anteil, quelle, herkunft) VALUES (?, 0, ?, ?, ?, ?, 1, ?, ?)",
                             (name, stand, schritt, text, buch, gemeinfrei.QUELLE, json.dumps(herkunft, ensure_ascii=False)))
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
        return settings.zwischen_dir / "eingang"

    @classmethod
    def _hier(cls, z: dict) -> Path:
        """Ablage ohne Kellerwolke: ein Ordner je Aufnahme, damit der Name der Datei (und so der Titel) bleibt, wie er ist;
        nur ein zu langer Name wird gekürzt."""
        return cls._zwischen() / str(z["id"]) / dateiname(Path(z["name"]).name)

    async def _teil_hier(self, z: dict, strom: AsyncIterator[bytes], laenge: int) -> int:
        """Ohne Kellerwolke (Entwicklung): das Teil landet im Zwischenspeicher, nie mehr als angesagt. Bricht es ab, gilt nur,
        was vorher da war."""
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
        """Leere Ordner im Zwischenspeicher des Eingangs gehen: einer nach dem Ablegen, alle beim Start."""
        eingang = self._zwischen()
        for o in [ordner] if ordner else (list(eingang.iterdir()) if eingang.is_dir() else []):
            if o.parent == eingang and o.is_dir() and not any(o.iterdir()):
                o.rmdir()

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
        """Laufende Uploads abbrechen (erst alles draußen, dann die Liste in einem Zug), angefangene Dateien im
        Zwischenspeicher gehen mit. Ein eingetragenes Buch bleibt."""
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
        z = await db.fetch_one("SELECT knoten, empfangen, groesse, pfad, quelle FROM aufnahme WHERE id = ?", (nr,))
        if z is None:
            return None
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
                z = await db.fetch_one("SELECT * FROM aufnahme WHERE stand IN ('liest', 'angaben', 'regal') ORDER BY id LIMIT 1")
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
        nr, name = z["id"], Path(z["name"]).name
        await self._setze(nr, stand="liest", schritt=2, anteil=0, text="Text und Umschlag werden gelesen")
        if da := await self._anderswo(z):
            await self._setze(nr, stand="da", schritt=0, anteil=1, buch_id=da["id"], text=f"Gibt es schon: \"{da['title']}\" hat denselben Inhalt")
            return
        pfad = await self._datei(z)
        summe = z["sha256"]
        if not summe:                                    # Ordner und gemeinfreie Bücher: erst jetzt bekannt
            summe = await asyncio.to_thread(compute_hash, pfad)
            await self._setze(nr, sha256=summe, groesse=z["groesse"] or pfad.stat().st_size)
            if da := await db.fetch_one("SELECT id, title FROM books WHERE hash = ?", (summe,)):
                await self._setze(nr, stand="da", schritt=0, anteil=1, buch_id=da["id"], text=f"Gibt es schon: \"{da['title']}\" hat denselben Inhalt")
                return
        e = await auswertung.auswerten(pfad)
        if not e.lesbar:
            await self._zu_klaeren(z)
            await self._setze(nr, stand="kaputt", schritt=0, text=e.grund + ". Nicht eingetragen.")
            return
        await self._setze(nr, stand="angaben", schritt=3, text="Angaben werden ergänzt")
        if z["anreichern"]:
            await angaben.ergaenzen(e, pfad.stem)
        await self._setze(nr, stand="regal", schritt=4, text="Kommt ins Regal")
        buch = await eintragen(summe, name, z["groesse"] or pfad.stat().st_size, e)
        await self._ablegen(z, buch, summe, name, pfad)
        if z["quelle"] == gemeinfrei.QUELLE:
            await gemeinfrei.nachher(z, buch, summe)
        codestellen.vormerken(buch)                               # Codestellen im Hintergrund, sobald das Original liegt
        stand, schritt, text = self._am_ziel(e.fulltext)
        await self._setze(nr, buch_id=buch, schritt=schritt, anteil=1, stand=stand, text=text)

    async def _ablegen(self, z: dict, buch: int, summe: str, name: str, pfad: Path) -> None:
        """Das Original an seinen Ort: liegt es schon in der Kellerwolke, dort umziehen; sonst mit Kellerwolke dorthin
        schreiben, ohne sie in den Speicher des Geräts. Aus Einlese-Ordner und externer Sammlung bleibt die Datei, wo sie
        ist (Kopie); alles andere zieht um (Zwischenspeicher, Eingangsordner auf dem Gerät)."""
        if z["knoten"]:
            await ablegen(buch, z["knoten"])
            return
        behalten = z["quelle"] in BEHALTEN
        if wolke.bereit:
            await wolke.ordner(f"{settings.ablage_ordner}/Eingang")
            k = await wolke.datei_schreiben(f"{settings.ablage_ordner}/Eingang/{summe[:12]} {sauber(name, 180)}", pfad)
            await ablegen(buch, k["id"])
            if not behalten:
                pfad.unlink(missing_ok=True)
                self._leere_ordner_raeumen(pfad.parent)
            return
        ziel = get_storage_path(summe) / dateiname(name)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2 if behalten else shutil.move, pfad, ziel)      # auch über Datenträger hinweg
        if not behalten:
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
