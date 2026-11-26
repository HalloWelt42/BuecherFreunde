"""Wiederherstellen aus einer Sicherung (BF-82): aus einer hochgeladenen Datei (in Teilen, einrichtung/hochladen.py), aus dem
Sicherungsordner des Geräts oder aus der Kellerwolke (ablage/sicherungen.py), beim Umzug vom alten Gerät.

Immer erst die Folgen (`folgen`, mit `stand`), dann `beginnen` mit diesem Stand. In der Ersteinrichtung nur auf leerem Bestand; gibt
es dort schon ein eigenes Konto, nennen die Folgen, dass es durch das aus der Sicherung ersetzt wird. Unter Einstellungen
(`/api/backup/restore`, `ersetzen`) ersetzt die Sicherung einen Bestand; die Folgen nennen ihn, und vorher entsteht eine Sicherung des
jetzigen Stands. Gelöscht wird nichts.

Das Einspielen läuft als sichtbarer Auftrag "Sicherung einspielen" in Abschnitten, jeder fortsetzbar: holen, prüfen (ZIP,
Datenbank, Zustand, in die Form dieser Fassung gebracht in einem eigenen Ordner neben dem Bestand), vorher sichern (nur beim
Ersetzen), einspielen (über die Sicherung von SQLite in den laufenden Bestand; die offenen Verbindungen bleiben gültig und sehen
danach den neuen Inhalt; der Zustand der Einrichtung bleibt der dieses Geräts), Suchindex und Anschlüsse. Danach prüft der Auftrag
"Originale prüfen" (einrichtung/pruefung.py)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sqlite3
import zipfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from backend.app.ablage import sicherungen as wolke_sicherungen
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core import einstellungen
from backend.app.core.config import settings
from backend.app.core.database import Database, db
from backend.app.einrichtung import anschluesse, hochladen, zustand
from backend.app.einrichtung.auftrag import Auftrag
from backend.app.einrichtung.hochladen import ablage
from backend.app.einrichtung.modelle import Auftragsstand, Sicherung, Sicherungsliste, Teil, Wiederhergestellt, Wiederherstellfolgen
from backend.app.einrichtung.zustand import Einrichtungsfehler, Mitnahme
from backend.app.services import search, sicherung
from backend.app.services.ki import ki

STUECK = 1 << 20
ABSCHNITTE = (("holen", "Sicherung holen"), ("pruefen", "Sicherung prüfen"), ("vorher", "Jetzigen Stand sichern"),
              ("einspielen", "Einspielen"), ("danach", "Suchindex und Anschlüsse"))
# Tabellen, die den Stand der Einrichtung des Geräts halten, das die Sicherung schrieb; auf diesem Gerät gilt der eigene
FREMDER_STAND = ("einrichtung", "einrichtung_schritt", "einrichtung_aenderung", "einrichtung_auftrag", "original_befund", "neuaufbau_datei",
                 "umzug", "umzug_kopie", "nachfuehren")


# -- Quellen ------------------------------------------------------------------------------------------------------------

def _zeit(f: Path) -> str:
    return datetime.fromtimestamp(f.stat().st_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _aus_datei(quelle: str, kennung: str, f: Path, name: str) -> Sicherung:
    i = sicherung.inhalt(f)
    return Sicherung(quelle=quelle, kennung=kennung, name=name, groesse=f.stat().st_size, angelegt_am=_zeit(f), buecher=i.buecher,
                     profile=i.profile, version=i.version)


def _vom_geraet() -> list[Sicherung]:
    aus = []
    for f in sicherung.staende():
        try:
            aus.append(_aus_datei("geraet", f.name, f, f.name))
        except (zipfile.BadZipFile, OSError, ValueError, sqlite3.Error):
            continue
    return aus


async def liste(quelle: str) -> Sicherungsliste:
    if quelle == "geraet":
        return Sicherungsliste(quelle="geraet", bereit=True, sicherungen=await asyncio.to_thread(_vom_geraet))
    if not wolke.bereit:
        return Sicherungsliste(quelle="kellerwolke", bereit=False, grund="Erst die Kellerwolke mit Adresse und Schlüssel eintragen")
    try:
        abgelegt = await wolke_sicherungen.liste()
    except WolkeFehler as f:
        return Sicherungsliste(quelle="kellerwolke", bereit=False, grund=f.meldung)
    return Sicherungsliste(quelle="kellerwolke", bereit=True, sicherungen=[
        Sicherung(quelle="kellerwolke", kennung=a.knoten, name=a.name, groesse=a.groesse, angelegt_am=a.angelegt_am, buecher=a.buecher,
                  profile=a.profile) for a in abgelegt])


def _geraetedatei(kennung: str) -> Path:
    name = Path(kennung).name
    f = settings.backup_dir / name
    if not (name.startswith("buecherfreunde_backup_") and f.is_file()):
        raise Einrichtungsfehler("Diese Sicherung gibt es im Sicherungsordner nicht", 404)
    return f


async def beschreiben(quelle: str, kennung: str) -> Sicherung:
    """Was die Sicherung enthält, ohne sie zu laden (in der Kellerwolke aus den Feldern der Datei)."""
    if quelle == "geraet":
        f = _geraetedatei(kennung)
        return await asyncio.to_thread(_aus_datei, "geraet", f.name, f, f.name)
    if quelle == "datei":
        f, name = hochladen.datei(kennung)
        return await asyncio.to_thread(_aus_datei, "datei", kennung, f, name)
    s = next((s for s in (await liste("kellerwolke")).sicherungen if s.kennung == kennung), None)
    if s is None:
        raise Einrichtungsfehler("Diese Sicherung gibt es in der Kellerwolke nicht", 404)
    return s


# -- Folgen -------------------------------------------------------------------------------------------------------------

async def _ersetzt(ersetzen: bool) -> list[str]:
    """Was die Sicherung ersetzen würde, als Sätze; leer, wenn auf dem Gerät noch nichts ist."""
    saetze = []
    konten = [z["name"] for z in await db.fetch_all("SELECT name FROM nutzer ORDER BY id")]
    if konten:
        saetze.append(f"Das Konto {', '.join(konten)} wird durch das aus der Sicherung ersetzt")
    if ersetzen:
        z = await db.fetch_one("SELECT (SELECT COUNT(*) FROM books) AS buecher, (SELECT COUNT(*) FROM profil) AS profile, "
                               "(SELECT COUNT(*) FROM book_notes) AS notizen, (SELECT COUNT(*) FROM book_highlights) AS markierungen")
        saetze.append(f"Der Bestand mit {z['buecher']} Büchern, {z['profile']} Profilen, {z['notizen']} Notizen und {z['markierungen']} "
                      "Markierungen wird durch den der Sicherung ersetzt")
        saetze.append("Vorher entsteht eine Sicherung des jetzigen Stands im Sicherungsordner")
    else:
        profile = [z["name"] for z in await db.fetch_all("SELECT name FROM profil ORDER BY sortierung, angelegt_am")]
        if len(profile) > 1:
            saetze.append(f"Die Profile {', '.join(profile)} werden durch die aus der Sicherung ersetzt")
    return saetze


async def _darf(ersetzen: bool) -> None:
    if ersetzen:
        if await zustand.modus() == "neu":
            raise Einrichtungsfehler("Während der Ersteinrichtung stellt der Assistent wieder her")
        return
    z = await zustand.nur_neu()
    if z["ausgangslage"] not in ("sicherung", "umzug"):
        raise Einrichtungsfehler("Wiederherstellen gibt es nur in den Ausgangslagen Sicherung und Umzug")
    if not await zustand.bestand_leer():
        raise Einrichtungsfehler("Der Bestand ist nicht leer; die Ersteinrichtung überschreibt nie Bücher")


async def folgen(quelle: str, kennung: str, ersetzen: bool = False) -> Wiederherstellfolgen:
    await _darf(ersetzen)
    s = await beschreiben(quelle, kennung)
    ersetzt = await _ersetzt(ersetzen)
    stand = hashlib.sha256(json.dumps([quelle, kennung, s.name, ersetzt], ensure_ascii=False).encode()).hexdigest()[:16]
    return Wiederherstellfolgen(sicherung=s, ersetzt=ersetzt, vorher_sichern=ersetzen, stand=stand)


async def beginnen(quelle: str, kennung: str, stand: str, ersetzen: bool = False) -> Auftragsstand:
    """Nur mit dem `stand` der Folgen (422 ohne, 409, wenn sich seither etwas geändert hat); dann der Auftrag."""
    await _darf(ersetzen)
    if not stand:
        raise Einrichtungsfehler("Stand: erst die Folgen ansehen (.../wiederherstellen/folgen)", 422)
    f = await folgen(quelle, kennung, ersetzen)
    if stand != f.stand:
        raise Einrichtungsfehler("Seit der Vorschau hat sich etwas geändert, bitte die Folgen neu ansehen")
    return await einspielen.beginnen(quelle=quelle, kennung=kennung, name=f.sicherung.name, ersetzen=ersetzen)


# -- prüfen und einspielen ------------------------------------------------------------------------------------------------

def _pruefen(datei: Path) -> sicherung.Inhalt:
    if not zipfile.is_zipfile(datei):
        raise Einrichtungsfehler("Datei: keine Sicherung (keine ZIP)", 422)
    with zipfile.ZipFile(datei) as zf:
        if sicherung.DATENBANK not in zf.namelist():
            raise Einrichtungsfehler("Datei: keine Sicherung von BücherFreunde (die Datenbank fehlt)", 422)
        if sum(i.file_size for i in zf.infolist()) > settings.wiederherstellen_mb_hoechstens * 1024 * 1024:
            raise Einrichtungsfehler("Datei: ausgepackt zu groß", 413)
    return sicherung.inhalt(datei)


def _ausgepackt() -> Path:
    return ablage() / "bestand" / "buecherfreunde.db"


def _auspacken(datei: Path) -> Path:
    ziel = _ausgepackt()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(datei) as zf, zf.open(sicherung.DATENBANK) as quelle, ziel.open("wb") as z:
        shutil.copyfileobj(quelle, z, STUECK)
    with closing(sqlite3.connect(ziel)) as v:
        if v.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise Einrichtungsfehler("Datei: die Datenbank in der Sicherung ist beschädigt", 422)
        if v.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'books'").fetchone() is None:
            raise Einrichtungsfehler("Datei: die Datenbank kennt keine Bücher", 422)
    return ziel


def _zustand_schreiben(datei: Path, m: Mitnahme) -> None:
    """Der Stand der Einrichtung dieses Geräts, nicht der des Geräts, das die Sicherung schrieb."""
    with closing(sqlite3.connect(datei)) as v:
        for tabelle in FREMDER_STAND:
            v.execute(f"DELETE FROM {tabelle}")
        for tabelle, zeilen in (("einrichtung", [m.einrichtung] if m.einrichtung else []), ("einrichtung_schritt", m.schritte),
                                ("einrichtung_auftrag", m.auftraege)):
            for z in zeilen:
                v.execute(f"INSERT INTO {tabelle}({', '.join(z)}) VALUES ({', '.join('?' * len(z))})", tuple(z.values()))
        v.commit()


def _uebertragen(quelle: Path, ziel: Path) -> None:
    with closing(sqlite3.connect(quelle)) as q, closing(sqlite3.connect(ziel, timeout=30)) as z:
        z.execute("PRAGMA busy_timeout=30000")
        q.backup(z)


def _angaben_ablegen(datei: Path) -> int:
    """Die Angaben je Buch (metadata.json) in den Speicher; nur Pfade darunter, Vorhandenes bleibt."""
    wurzel, n = settings.storage_dir.resolve(), 0
    with zipfile.ZipFile(datei) as zf:
        for name in zf.namelist():
            rest = name[len("metadata/"):] if name.startswith("metadata/") else ""
            if not rest or not rest.endswith("metadata.json"):
                continue
            ziel = (settings.storage_dir / rest).resolve()
            if not ziel.is_relative_to(wurzel) or ziel.exists():
                continue
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(zf.read(name))
            n += 1
    return n


def aufraeumen() -> None:
    """Nur der eigene Ordner der Sicherungen auf dem Weg hinein; der Bestand und die Sicherungen bleiben."""
    shutil.rmtree(ablage(), ignore_errors=True)


class Einspielen(Auftrag):
    art = "einspielen"
    was = "Sicherung einspielen"

    async def _abschnitte(self) -> list[tuple[str, str]]:
        a = await self.angaben()
        return [(k, n) for k, n in ABSCHNITTE if k != "vorher" or a.get("ersetzen")]

    async def zaehlen(self) -> tuple[int, int, list[Teil]]:
        a, liste = await self.angaben(), await self._abschnitte()
        erledigt = set(a.get("erledigt") or [])
        return len(liste), len(erledigt), [Teil(schluessel=k, name=n, gesamt=1, fertig=int(k in erledigt)) for k, n in liste]

    async def _merken(self, **neu) -> None:
        a = await self.angaben() | neu
        await db.execute("UPDATE einrichtung_auftrag SET angaben = ? WHERE art = ?", (json.dumps(a), self.art))
        await db.commit()

    async def naechstes(self) -> bool:
        a = await self.angaben()
        erledigt = list(a.get("erledigt") or [])
        offen = [k for k, _ in await self._abschnitte() if k not in erledigt]
        if not offen:
            return False
        await getattr(self, f"_{offen[0]}")(a)
        await self._merken(erledigt=[*erledigt, offen[0]])
        return True

    @staticmethod
    def _datei(a: dict) -> Path:
        return Path(a["datei"]) if a.get("datei") else ablage() / "sicherung.zip"

    async def _holen(self, a: dict) -> None:
        if a["quelle"] == "datei":
            pfad, _name = hochladen.datei(a["kennung"])
            await self._merken(datei=str(pfad))
            return
        if a["quelle"] == "umzug":                            # schon vom alten Gerät geholt (einrichtung/umzug.py)
            return
        ziel = ablage() / "sicherung.zip"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        if a["quelle"] == "geraet":
            await asyncio.to_thread(shutil.copyfile, _geraetedatei(a["kennung"]), ziel)
        else:
            await asyncio.to_thread(wolke.holen, a["kennung"], ziel)

    async def _pruefen(self, a: dict) -> None:
        i = await asyncio.to_thread(_pruefen, self._datei(a))
        staging = await asyncio.to_thread(_auspacken, self._datei(a))
        probe = Database(db_path=staging)                     # in die Form dieser Fassung, ohne den Bestand anzufassen
        await probe.connect()
        await probe.disconnect()
        await self._merken(version=i.version)

    async def _vorher(self, a: dict) -> None:
        lauf = await asyncio.to_thread(sicherung.sichern, sicherung.Anlass.HAND)
        if lauf.neu:
            await wolke_sicherungen.ablegen(lauf.datei)
        await self._merken(vorher=lauf.datei.name)

    async def _einspielen(self, a: dict) -> None:
        await asyncio.to_thread(_zustand_schreiben, _ausgepackt(), await zustand.mitnehmen())
        await asyncio.to_thread(_uebertragen, _ausgepackt(), db.db_path)
        await asyncio.to_thread(_angaben_ablegen, self._datei(a))

    async def _danach(self, a: dict) -> None:
        for art, wert in (a.get("anschluesse") or {}).items():    # Umzug: Adressen, die das alte Gerät aus seiner .env kannte
            if art in anschluesse.ARTEN and await einstellungen.lesen(anschluesse.einstellung(art)) is None:
                await einstellungen.schreiben(anschluesse.einstellung(art), wert)
        for schluessel_, wert in (a.get("einstellungen") or {}).items():
            await einstellungen.schreiben(schluessel_, wert)
        await search.rebuild_index()
        await anschluesse.anwenden()
        await ki.wahl_laden()

    async def danach(self) -> None:
        a = await self.angaben()
        zahl = await db.fetch_one("SELECT (SELECT COUNT(*) FROM books) AS buecher, (SELECT COUNT(*) FROM profil) AS profile")
        await self._merken(ergebnis=Wiederhergestellt(name=a["name"], buecher=zahl["buecher"], profile=zahl["profile"], version=a.get("version", ""),
                                                      vorher=a.get("vorher", "")).model_dump())
        await asyncio.to_thread(aufraeumen)
        if await zustand.modus() == "neu":
            await zustand.vermerken("verbinden" if a["quelle"] == "umzug" else "sicherung",
                                    text=f"{a['name']}: {zahl['buecher']} Bücher, {zahl['profile']} Profile")
        if a["quelle"] != "umzug" or wolke.bereit:            # beim Umzug ohne Kellerwolke wählt man erst, wie die Originale kommen
            from backend.app.einrichtung.pruefung import pruefung

            await pruefung.beginnen(pruefsummen=False)

    async def ergebnis(self) -> Wiederhergestellt | None:
        e = (await self.angaben()).get("ergebnis")
        return Wiederhergestellt.model_validate(e) if e else None


einspielen = Einspielen()
