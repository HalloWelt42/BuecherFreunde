"""Die Aufnahmen: jede Datei auf ihrem Weg in sechs Stationen (Prüfen, Wolke, Lesen, Angaben, Regal, Wissen). Der Stand steht
in der Datenbank; nach einem Neustart geht jede Aufnahme dort weiter, wo sie war. Teile strömen vom Browser durch die App in die
Kellerwolke, ohne hier abgelegt zu werden."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from backend.app.ablage import originale
from backend.app.ablage.namen import sauber
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.annahme import auswertung
from backend.app.annahme.eintragen import ablegen, eintragen
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services.storage import SUPPORTED_FORMATS, get_storage_path

logger = logging.getLogger("buecherfreunde.annahme")
TEIL = 4 * 1024 * 1024
LAUFEND = ("wartet", "laedt", "angehalten", "liest", "angaben", "regal")
KLAEREN = ("format", "kaputt", "fehler", "ohne_text")
FORMATE = "PDF, EPUB, MOBI, TXT und MD"


class Versatz(Exception):
    """Der Browser schickt nicht ab dem Stand, den der Server hat."""

    def __init__(self, empfangen: int) -> None:
        super().__init__("Das Teil schließt nicht an")
        self.empfangen = empfangen


def mb(n: int) -> str:
    return f"{n / 1e6:.1f}".replace(".", ",") + " MB"


def _aussen(z: dict) -> dict:
    return {k: z[k] for k in ("id", "name", "groesse", "sha256", "empfangen", "stand", "schritt", "anteil", "text", "buch_id", "angelegt_am", "geaendert_am")} | {"teil_groesse": TEIL}


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
        self._schleife = asyncio.create_task(self._arbeiten())

    async def stoppen(self) -> None:
        if self._schleife:
            self._schleife.cancel()
        auswertung.schliessen()

    # -- Sicht ---------------------------------------------------------------------------------------------------------
    async def alle(self) -> dict:
        zeilen = [_aussen(z) for z in await db.fetch_all("SELECT * FROM aufnahme WHERE ausgeblendet = 0 ORDER BY id DESC LIMIT 300")]
        def zahl(*staende: str) -> int:
            return sum(z["stand"] in staende for z in zeilen)
        return {"eintraege": zeilen, "zaehler": {"alle": len(zeilen), "laeuft": zahl(*LAUFEND), "klaeren": zahl(*KLAEREN), "da": zahl("da"), "fertig": zahl("fertig", "wissen")}}

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
        stand, text, buch, schritt = "wartet", "Bereit zum Hochladen", None, 1
        endung = Path(name).suffix.lower()
        vorhanden = await db.fetch_one("SELECT id, title FROM books WHERE hash = ?", (sha256,)) if sha256 else None
        if endung not in SUPPORTED_FORMATS:
            stand, schritt, text = "format", 0, f"Dieses Format kann die Bibliothek nicht lesen. Nichts hochgeladen. Möglich sind {FORMATE}."
        elif groesse <= 0:
            stand, schritt, text = "kaputt", 0, "Die Datei ist leer. Nicht eingetragen."
        elif vorhanden:
            stand, schritt, buch, text = "da", 0, vorhanden["id"], f"Gibt es schon: \"{vorhanden['title']}\" hat denselben Inhalt"
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
            empfangen, knoten = await self._teil_hier(z, strom), None
        fertig = empfangen >= z["groesse"]
        await self._setze(nr, empfangen=empfangen, anteil=empfangen / z["groesse"], knoten=knoten or z["knoten"], stand="liest" if fertig else "laedt", schritt=2 if fertig else 1,
                          text="Wartet auf das Lesen" if fertig else f"Wird in der Kellerwolke abgelegt, {mb(empfangen)} von {mb(z['groesse'])}")
        if fertig:
            self._arbeit.set()
        return await self.einer(nr)

    async def _teil_hier(self, z: dict, strom: AsyncIterator[bytes]) -> int:
        """Ohne Kellerwolke (Entwicklung): das Teil landet im Zwischenspeicher."""
        ziel = settings.zwischen_dir / "eingang" / f"{z['id']}-{Path(z['name']).name}"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        with ziel.open("ab" if z["empfangen"] else "wb") as f:
            async for stueck in strom:
                f.write(stueck)
        return ziel.stat().st_size

    # -- Bedienung -----------------------------------------------------------------------------------------------------
    async def entfernen(self, nr: int) -> None:
        z = await db.fetch_one("SELECT upload, stand FROM aufnahme WHERE id = ?", (nr,))
        if z and z["upload"] and z["stand"] in ("wartet", "laedt", "angehalten"):
            try:
                await wolke.upload_abbrechen(z["upload"])
            except WolkeFehler as f:
                logger.info("Upload %s nicht abgebrochen: %s", z["upload"], f)
        await db.execute("DELETE FROM aufnahme WHERE id = ?", (nr,))
        await db.commit()
        for e in self._neu:
            e.set()

    async def erneut(self, nr: int) -> dict | None:
        z = await db.fetch_one("SELECT knoten, empfangen, groesse FROM aufnahme WHERE id = ?", (nr,))
        if z is None:
            return None
        if z["empfangen"] >= z["groesse"] > 0:
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
        hier = settings.zwischen_dir / "eingang" / f"{z['id']}-{Path(z['name']).name}"
        if hier.exists():
            return hier
        await db.execute("INSERT OR IGNORE INTO ablage_datei(hash, knoten, name, groesse) VALUES (?, ?, ?, ?)", (z["sha256"], z["knoten"], Path(z["name"]).name, z["groesse"]))
        await db.commit()
        pfad = await asyncio.to_thread(originale.holen, z["sha256"])
        if pfad is None:
            raise WolkeFehler("Das Original kommt gerade nicht aus der Kellerwolke")
        return pfad

    async def _verarbeiten(self, z: dict) -> None:
        nr, name = z["id"], Path(z["name"]).name
        await self._setze(nr, stand="liest", schritt=2, anteil=0, text="Text und Umschlag werden gelesen")
        pfad = await self._datei(z)
        summe = z["sha256"] or await asyncio.to_thread(lambda: hashlib.sha256(pfad.read_bytes()).hexdigest())
        e = await auswertung.auswerten(pfad)
        if not e.lesbar:
            await self._zu_klaeren(z)
            await self._setze(nr, stand="kaputt", schritt=0, text=e.grund + ". Nicht eingetragen.")
            return
        await self._setze(nr, stand="angaben", schritt=3, text="Angaben werden ergänzt")
        if z["anreichern"] and settings.openlibrary_enabled:
            try:
                from backend.app.services.import_service import _enrich_from_openlibrary
                await _enrich_from_openlibrary(e, pfad, None)
            except Exception as f:                         # noqa: BLE001 - ohne Ergänzung bleibt, was in der Datei steht
                logger.info("Angaben zu %s nicht ergänzt: %s", name, f)
        await self._setze(nr, stand="regal", schritt=4, text="Kommt ins Regal")
        buch = await eintragen(summe, name, z["groesse"], e)
        if z["knoten"]:
            await ablegen(buch, z["knoten"])
        else:
            ziel = get_storage_path(summe) / name
            ziel.parent.mkdir(parents=True, exist_ok=True)
            pfad.replace(ziel)
        ohne = not e.fulltext.strip()
        await self._setze(nr, buch_id=buch, schritt=5 if not ohne else 6, anteil=1, stand="ohne_text" if ohne else "wissen",
                          text="In der Bibliothek. Nur Bilder, kein Text: nicht im Volltext zu finden." if ohne else "In der Bibliothek. Die Bedeutung folgt mit dem nächsten Abgleich.")

    async def _zu_klaeren(self, z: dict) -> None:
        """Eine unlesbare Datei wird nie gelöscht, sie kommt in der Kellerwolke nach "Zu klären"."""
        await db.execute("DELETE FROM ablage_datei WHERE hash = ? AND hash NOT IN (SELECT hash FROM books)", (z["sha256"],))
        await db.commit()
        if z["knoten"]:
            ordner = await wolke.ordner(f"{settings.ablage_ordner}/Zu klären")
            await wolke.umziehen(z["knoten"], ordner["id"], f"{z['id']} {sauber(Path(z['name']).name, 180)}")


annahme = Annahme()
