"""Der eigene Katalog der gemeinfreien Bücher (BF-98): die Katalogdatei des Project Gutenberg von den Spiegeln
(`GUTENBERG_KATALOG_PFAD`, geholt über den Abruf der Dateien mit Takt, Pausen und Zeitgrenzen der Quelle), als SQLite mit
Volltextindex im Ort Suchindex (`gutenberg_katalog.db`, jederzeit neu zu bauen), nur Einträge der Art Text.

Holen ist ein sichtbarer Auftrag mit Fortschritt in Byte. Bricht er ab, setzt der nächste am Stand fort (Range mit If-Range auf
die Kennung der Datei); hat sie sich inzwischen geändert, beginnt er sauber von vorn. Gebaut wird neben dem alten Katalog und erst
ganz fertig in einem Schritt an seinen Platz gerückt; bis dahin gilt der alte. Beim Erneuern fragt er, ob sich die Datei geändert
hat (If-None-Match); unverändert gilt der Katalog als frisch geholt. Das erste Holen stößt die Oberfläche an, wenn jemand die
gemeinfreien Bücher öffnet und es noch keinen gibt; erneuert wird er in der nächtlichen Pflege (services/pflege.py).

Gesucht wird nur hier, ohne Anfrage ins Netz: Vorschläge beim Tippen, der Rückfall von "Bei Gutendex suchen" (api/gutenberg.py)
und der Abgleich fehlender Bände einer Sammlung nach Titel und Autor (quellen/abgleich.py, luecken/dienst.py)."""

from __future__ import annotations

import asyncio
import csv
import email.utils
import json
import logging
import os
import re
import sqlite3
from collections.abc import Callable, Iterable, Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.quellen import regeln
from backend.app.quellen.abgleich import autor_passt, gleicher_band, nachname, punkte, umschrift
from backend.app.quellen.abruf import abruf
from backend.app.quellen.fehler import AnfrageFalsch, Ausgefallen, QuelleFehler, ruhig
from backend.app.quellen.gutenberg import SPIEGEL, Fundbuch, Fundliste, datei_adresse, umschlag_adresse
from backend.app.quellen.klartext import klartext
from backend.app.quellen.modelle import Angaben, Buchfrage
from backend.app.quellen.versand import Dateiziel, gesamt_aus

logger = logging.getLogger("buecherfreunde.quellen.gutenberg_katalog")
DATEI = "gutenberg_katalog.db"
TEIL = "gutenberg_katalog.csv.teil"           # die Katalogdatei, solange sie geholt wird
MERKZETTEL = "gutenberg_katalog.csv.teil.json"  # Kennung, Stand und Größe der Datei, die gerade geholt wird
SEITE = 32                                     # Treffer je Seite, wie bei Gutendex
HOECHSTENS = 200_000_000                       # so groß darf die Katalogdatei werden
WORTE_HOECHSTENS = 12                          # so viele Wörter einer Eingabe zählen
KANDIDATEN = 40                                # so viele Funde des Index prüft der Abgleich eines fehlenden Bands genau
STAPEL = 2000                                  # so viele Einträge schreibt der Bau auf einmal
ART = "Text"
SPALTEN = ("Text#", "Type", "Title", "Language", "Authors", "Subjects", "Bookshelves")
SPIEGEL_NAME = "Der Spiegel des Project Gutenberg"

SCHEMA = """
CREATE TABLE kopf(schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL);
CREATE TABLE buch(id INTEGER PRIMARY KEY, titel TEXT NOT NULL, autor TEXT NOT NULL, sprachen TEXT NOT NULL, themen TEXT NOT NULL,
                  regale TEXT NOT NULL, such_titel TEXT NOT NULL, such_autor TEXT NOT NULL);
CREATE VIRTUAL TABLE buch_fts USING fts5(such_titel, such_autor, themen, regale, content='buch', content_rowid='id',
                                         tokenize='unicode61 remove_diacritics 2');
"""
NEU = "INSERT OR REPLACE INTO buch VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
GEWICHTE = "bm25(buch_fts, 10.0, 4.0, 1.0, 1.0)"   # ein Wort im Titel zählt mehr als eines beim Autor, beide mehr als Themen
_WORT = re.compile(r"\w+")
_ROLLE = re.compile(r"\[[^\]]*\]\s*$")
_KLAMMER = re.compile(r"\s*\([^)]*\)")
_LEBENSDATEN = re.compile(r",\s*(?:ca\.\s*|active\s+|fl\.\s*)?(?:\d|-\s*\d|\?|BCE)[^,]*$", re.IGNORECASE)


class Katalogfehler(Exception):
    """Die geholte Datei taugt nicht als Katalog; `grund` ist ein Satz für die Oberfläche."""

    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund


class Katalogstand(BaseModel):
    """Wie es um den eigenen Katalog steht, auch während er geholt oder gebaut wird."""

    da: bool = False
    anzahl: int = 0                                # Bücher der Art Text
    stand: str | None = None                       # Datum der Datei auf dem Spiegel (JJJJ-MM-TT)
    geholt_am: str | None = None                   # zuletzt geholt oder als unverändert bestätigt (Weltzeit)
    alter_tage: float | None = None
    faellig: bool = False                          # älter als GUTENBERG_KATALOG_TAGE: die nächtliche Pflege erneuert ihn
    erneuern_tage: int
    laeuft: bool = False
    schritt: Literal["", "holen", "bauen"] = ""
    erledigt: int = 0                              # Byte: geholt, beim Bauen gelesen
    gesamt: int | None = None                      # Byte der Datei, wenn bekannt
    grund: str = ""                                # warum der letzte Lauf scheiterte, als Satz
    suche_geduld_s: float                          # so lange wartet "Bei Gutendex suchen" (für den Hinweis beim Warten)


def _jetzt() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ort() -> Path:
    """Der Katalog liegt im Ort Suchindex, neben `suche.db` (in Tests neben der Probedatenbank)."""
    return db.suche_dir / DATEI


def _teil() -> Path:
    return db.suche_dir / TEIL


def _merkzettel() -> Path:
    return db.suche_dir / MERKZETTEL


# -- Einträge der Katalogdatei ---------------------------------------------------------------------------------------------

def titel_aus(feld: str) -> str:
    """Ein Titel über mehrere Zeilen (Titel und Untertitel) als eine Zeile: "Titel: Untertitel"."""
    zeilen = [" ".join(z.split()) for z in (feld or "").splitlines() if z.strip()]
    if not zeilen:
        return ""
    kopf, rest = zeilen[0], " ".join(zeilen[1:])
    return f"{kopf}{' ' if kopf.endswith((':', ';', ',')) else ': '}{rest}" if rest else kopf


def autor_aus(feld: str) -> str:
    """Die Verfasser wie bei Gutendex ("Nachname, Vorname", mehrere mit Semikolon), ohne Lebensdaten; wer mit einer Rolle in
    eckigen Klammern dasteht (Übersetzer, Herausgeber, Illustrator), ist kein Verfasser."""
    namen = []
    for teil in (feld or "").split(";"):
        name = teil.strip()
        if not name or _ROLLE.search(name):
            continue
        name = _LEBENSDATEN.sub("", _KLAMMER.sub("", name)).strip(" ,")
        if name:
            namen.append(name)
    return "; ".join(namen)


def _sprachen_aus(feld: str) -> str:
    """"de; en" als ";de;en;", damit eine Sprache mit instr() genau gefunden wird."""
    kuerzel = [s.strip().lower() for s in (feld or "").split(";") if s.strip()]
    return f";{';'.join(kuerzel)};" if kuerzel else ""


def _eintrag(z: dict[str, str]) -> tuple[int, str, str, str, str, str, str, str] | None:
    """Eine Zeile der Katalogdatei als Zeile der Tabelle `buch`; None für alles, was kein Text ist. Gesucht wird in der Umschrift
    von Titel und Autor, gezeigt wird, wie es im Katalog steht."""
    if (z.get("Type") or "").strip() != ART:
        return None
    try:
        nummer = int((z.get("Text#") or "").strip())
    except ValueError:
        return None
    titel, autor = titel_aus(z.get("Title") or ""), autor_aus(z.get("Authors") or "")
    if nummer <= 0 or not titel:
        return None
    return (nummer, titel, autor, _sprachen_aus(z.get("Language") or ""), " ".join((z.get("Subjects") or "").split()),
            " ".join((z.get("Bookshelves") or "").split()), umschrift(titel), umschrift(autor))


def _zeilen(roh, gelesen: list[int]) -> Iterator[str]:
    """Die Zeilen der Datei als Text; `gelesen` zählt die Byte mit. Ein Zeichen über mehrere Byte endet nie an einem
    Zeilenende, und Zeilenumbrüche in Feldern löst der CSV-Leser selbst."""
    for i, zeile in enumerate(roh):
        gelesen[0] += len(zeile)
        yield (zeile.removeprefix(b"\xef\xbb\xbf") if i == 0 else zeile).decode("utf-8", errors="replace")


def bauen(quelle: Path, ziel: Path, kopf: dict[str, str], stand: Callable[[int, int], None] | None = None) -> int:
    """Die Katalogdatei (CSV) als SQLite mit Volltextindex nach `ziel`, nur Einträge der Art Text. Gebaut wird neben dem Ziel,
    erst ganz fertig rückt die neue Datei in einem Schritt an seinen Platz. Liefert die Zahl der Bücher; wirft Katalogfehler,
    wenn die Datei kein Katalog ist."""
    neu = ziel.with_name(ziel.name + ".neu")
    neu.unlink(missing_ok=True)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    gesamt, gelesen = quelle.stat().st_size, [0]
    v = sqlite3.connect(neu)
    try:
        v.execute("PRAGMA journal_mode=OFF")
        v.execute("PRAGMA synchronous=OFF")
        v.executescript(SCHEMA)
        with quelle.open("rb") as roh:
            leser = csv.DictReader(_zeilen(roh, gelesen))
            if not leser.fieldnames or not set(SPALTEN) <= set(leser.fieldnames):
                raise Katalogfehler("Die Datei vom Spiegel ist kein Katalog des Project Gutenberg")
            stapel: list[tuple] = []
            for zeile in leser:
                if (e := _eintrag(zeile)) is not None:
                    stapel.append(e)
                if len(stapel) >= STAPEL:
                    v.executemany(NEU, stapel)
                    stapel.clear()
                    if stand:
                        stand(gelesen[0], gesamt)
            v.executemany(NEU, stapel)
        anzahl = v.execute("SELECT count(*) FROM buch").fetchone()[0]
        if not anzahl:
            raise Katalogfehler("Im Katalog vom Spiegel steht kein Buch")
        v.execute("INSERT INTO buch_fts(buch_fts) VALUES('rebuild')")
        v.execute("INSERT INTO buch_fts(buch_fts) VALUES('optimize')")
        v.executemany("INSERT OR REPLACE INTO kopf VALUES (?, ?)", [*kopf.items(), ("anzahl", str(anzahl))])
        v.commit()
    except BaseException:
        v.close()
        neu.unlink(missing_ok=True)
        raise
    v.close()
    os.replace(neu, ziel)
    if stand:
        stand(gesamt, gesamt)
    return anzahl


# -- Lesen -------------------------------------------------------------------------------------------------------------------

@contextmanager
def _lesend(pfad: Path) -> Iterator[sqlite3.Connection]:
    """Nur lesend, je Abfrage eine eigene Verbindung: ein neu gebauter Katalog gilt ab der nächsten."""
    with closing(sqlite3.connect(f"{pfad.resolve().as_uri()}?mode=ro", uri=True)) as v:
        v.row_factory = sqlite3.Row
        yield v


def kopf_lesen(pfad: Path) -> dict[str, str]:
    """Die Angaben zum Katalog (Anzahl, Stand, Kennung, wann geholt); leer, wenn es keinen brauchbaren gibt."""
    if not pfad.is_file():
        return {}
    try:
        with _lesend(pfad) as v:
            return {z["schluessel"]: z["wert"] for z in v.execute("SELECT schluessel, wert FROM kopf")}
    except sqlite3.Error as f:
        logger.warning("Eigener Katalog nicht lesbar: %s", f)
        return {}


def _bestaetigen(pfad: Path) -> None:
    """Die Datei auf dem Spiegel ist unverändert: der Katalog gilt als frisch geholt."""
    with closing(sqlite3.connect(pfad)) as v:
        v.execute("INSERT OR REPLACE INTO kopf VALUES ('geholt_am', ?)", (_jetzt(),))
        v.commit()


def _worte(text: str) -> list[str]:
    """Die Wörter einer Eingabe in der Umschrift, wie der Index sie kennt; Groß und klein und übrige Akzente gleicht der Index
    selbst aus, Satzzeichen trennen."""
    return list(dict.fromkeys(_WORT.findall(umschrift(text).lower())))[:WORTE_HOECHSTENS]


def _zitiert(worte: Iterable[str], anfang: bool = False) -> list[str]:
    return [f'"{w}"{"*" if anfang else ""}' for w in worte]


def _ausdruck(text: str) -> str:
    """Jedes Wort als Anfang eines Worts im Index ("mühl" findet "Mühlenkai"), alle müssen vorkommen."""
    return " ".join(_zitiert(_worte(text), anfang=True))


def _sprachfilter(sprache: str) -> list[str]:
    return [f";{s};" for s in dict.fromkeys(t.strip().lower() for t in (sprache or "").split(",")) if s]


def _liste(feld: str) -> list[str]:
    return [t.strip() for t in (feld or "").split(";") if t.strip()]


def _fund(z: sqlite3.Row) -> Fundbuch:
    nummer = z["id"]
    return Fundbuch(gutenberg_id=nummer, titel=z["titel"], autor=z["autor"], sprachen=[s for s in z["sprachen"].split(";") if s],
                    download_url=datei_adresse(nummer), download_format="epub", cover_url=umschlag_adresse(nummer),
                    regale=_liste(z["regale"]), themen=_liste(z["themen"]))


def _suchen(pfad: Path, wort: str, thema: str, sprache: str, seite: int, je_seite: int) -> Fundliste:
    teile = [f"{{{spalten}}} : ({ausdruck})" for spalten, ausdruck in (("such_titel such_autor", _ausdruck(wort)), ("themen regale", _ausdruck(thema))) if ausdruck]
    sprachen = _sprachfilter(sprache)
    bedingungen, werte = [], []
    if teile:
        bedingungen.append("buch_fts MATCH ?")
        werte.append(" AND ".join(teile))
    if sprachen:
        bedingungen.append(f"({' OR '.join('instr(b.sprachen, ?) > 0' for _ in sprachen)})")
        werte += sprachen
    von = "buch_fts f JOIN buch b ON b.id = f.rowid" if teile else "buch b"
    ordnung = f"{GEWICHTE}, b.id" if teile else "b.id DESC"
    wo = " AND ".join(bedingungen) or "1"
    with _lesend(pfad) as v:
        gesamt = v.execute(f"SELECT count(*) FROM {von} WHERE {wo}", werte).fetchone()[0]
        zeilen = v.execute(f"SELECT b.* FROM {von} WHERE {wo} ORDER BY {ordnung} LIMIT ? OFFSET ?", [*werte, je_seite, (seite - 1) * je_seite]).fetchall()
    return Fundliste(gesamt=gesamt, seite=seite, buecher=[_fund(z) for z in zeilen], herkunft="katalog")


def _angaben(z: sqlite3.Row, sprache: str) -> Angaben:
    """Ein Eintrag zum Vergleich mit einer Frage, in der Umschrift wie die Frage; die Sprache der Frage, wenn er sie hat."""
    sprachen = [s for s in z["sprachen"].split(";") if s]
    return Angaben(titel=z["such_titel"], autoren=_liste(z["such_autor"]), sprache=sprache if sprache in sprachen else (sprachen[0] if sprachen else ""))


def _abgleichen(pfad: Path, fragen: list[Buchfrage]) -> list[Fundbuch | None]:
    """Je Frage das Buch des Katalogs, das sicher derselbe Band ist: der ganze Titel gleich (nicht nur der Haupttitel, sonst
    wären alle Teile einer Reihe gleich), der Autor widerspricht nicht, in der Sprache der Frage, wenn sie eine nennt; ohne
    Rücksicht auf Groß und klein, Satzzeichen und Umlautschreibweise. Unter mehreren gewinnt, wer nach den Punkten der Quellen
    am besten passt; sonst None. Der Index liefert die Kandidaten: ein Wort des Titels und, wenn bekannt, der Nachname."""
    aus: list[Fundbuch | None] = []
    with _lesend(pfad) as v:
        for roh in fragen:
            frage = Buchfrage(titel=umschrift(roh.titel), autoren=[umschrift(a) for a in roh.autoren], sprache=roh.sprache)
            worte = [w for w in _worte(frage.titel) if len(w) > 2]
            if not worte:
                aus.append(None)
                continue
            ausdruck = f"{{such_titel}} : ({' OR '.join(_zitiert(worte))})"
            if namen := [" ".join(_zitiert(n)) for a in frage.autoren if (n := _worte(nachname(a)))]:
                ausdruck += f" AND {{such_autor}} : ({' OR '.join(namen)})"
            sprachen = _sprachfilter(frage.sprache)
            filter_ = f" AND ({' OR '.join('instr(b.sprachen, ?) > 0' for _ in sprachen)})" if sprachen else ""
            zeilen = v.execute(f"SELECT b.* FROM buch_fts f JOIN buch b ON b.id = f.rowid WHERE buch_fts MATCH ?{filter_} ORDER BY {GEWICHTE} LIMIT ?",
                               [ausdruck, *sprachen, KANDIDATEN]).fetchall()
            passend = [(punkte(frage, a), -i, z) for i, z in enumerate(zeilen) if (a := _angaben(z, frage.sprache))
                       and gleicher_band(frage.titel, a.titel) and autor_passt(frage.autoren, a.autoren) is not False]
            bestes = max(passend, key=lambda b: b[:2], default=None)
            aus.append(_fund(bestes[2]) if bestes and bestes[0] > 0 else None)
    return aus


# -- Der Auftrag "Katalog holen" ----------------------------------------------------------------------------------------------

class Katalog:
    def __init__(self) -> None:
        self._aufgabe: asyncio.Task | None = None
        self.schritt: Literal["", "holen", "bauen"] = ""
        self.erledigt = 0
        self.gesamt: int | None = None
        self.grund = ""

    @property
    def laeuft(self) -> bool:
        return self._aufgabe is not None and not self._aufgabe.done()

    async def da(self) -> bool:
        return bool(await asyncio.to_thread(kopf_lesen, ort()))

    async def stand(self) -> Katalogstand:
        kopf = await asyncio.to_thread(kopf_lesen, ort())
        geholt = kopf.get("geholt_am")
        alter = (datetime.now(UTC) - datetime.fromisoformat(geholt.replace("Z", "+00:00"))).total_seconds() / 86400 if geholt else None
        laeuft = self.laeuft
        return Katalogstand(da=bool(kopf), anzahl=int(kopf.get("anzahl") or 0), stand=kopf.get("stand") or None, geholt_am=geholt,
                            alter_tage=round(alter, 2) if alter is not None else None,
                            faellig=bool(kopf) and alter is not None and alter > settings.gutenberg_katalog_tage,
                            erneuern_tage=settings.gutenberg_katalog_tage, laeuft=laeuft, schritt=self.schritt if laeuft else "",
                            erledigt=self.erledigt if laeuft else 0, gesamt=self.gesamt if laeuft else None, grund=self.grund,
                            suche_geduld_s=settings.gutenberg_suche_geduld_s)

    def starten(self) -> bool:
        """Holen oder erneuern; läuft es schon, bleibt es bei diesem Lauf. Mit dem Vorrang dessen, der startet."""
        if self.laeuft:
            return False
        self.schritt, self.erledigt, self.gesamt, self.grund = "holen", 0, None, ""
        self._aufgabe = asyncio.create_task(self._laufen())
        return True

    async def warten(self) -> None:
        if self._aufgabe is not None:
            await asyncio.gather(self._aufgabe, return_exceptions=True)

    async def stoppen(self) -> None:
        if self._aufgabe is not None:
            self._aufgabe.cancel()
            await asyncio.gather(self._aufgabe, return_exceptions=True)
            self._aufgabe = None

    async def _laufen(self) -> None:
        try:
            await self._erneuern()
        except QuelleFehler as f:
            self.grund = klartext(f, SPIEGEL_NAME)
        except Katalogfehler as f:
            self.grund = f.grund
            await asyncio.to_thread(self._teil_weg)              # was da kam, taugt nicht: das nächste Mal von vorn
        except OSError:
            logger.exception("Eigener Katalog")
            self.grund = "Der Katalog ließ sich im Ort Suchindex nicht ablegen"
        except Exception:                                      # noqa: BLE001 - der Auftrag endet immer mit Grund
            logger.exception("Eigener Katalog")
            self.grund = "Der Katalog ließ sich nicht bauen"
        finally:
            self.schritt = ""
        if self.grund:
            logger.warning("Eigener Katalog: %s", self.grund)

    async def _erneuern(self) -> None:
        alt = await asyncio.to_thread(kopf_lesen, ort())
        datei = await self._holen(alt.get("etag", ""))
        if datei is None:
            await asyncio.to_thread(_bestaetigen, ort())
            logger.info("Eigener Katalog unverändert")
            return
        merk = self._merkzettel_lesen()
        kopf = {"geholt_am": _jetzt(), "stand": _datum(merk.get("stand", "")) or _jetzt()[:10], "etag": merk.get("etag", ""), "adresse": merk.get("adresse", "")}
        self.schritt, self.erledigt, self.gesamt = "bauen", 0, datei.stat().st_size
        anzahl = await asyncio.to_thread(bauen, datei, ort(), kopf, self._gebaut)
        await asyncio.to_thread(self._teil_weg)
        logger.info("Eigener Katalog gebaut: %d Bücher", anzahl)

    async def _holen(self, etag_alt: str) -> Path | None:
        """Die Katalogdatei ganz in TEIL, vom ersten Spiegel, der sie liefert; None, wenn sie unverändert ist."""
        teil, letzter = _teil(), None
        for spiegel in SPIEGEL:
            adresse = f"https://{spiegel}{settings.gutenberg_katalog_pfad}"
            merk = self._merkzettel_lesen()
            versatz = teil.stat().st_size if teil.is_file() and merk.get("etag") else 0
            if versatz:
                kopf = {"If-Range": merk["etag"]}                     # dieselbe Datei: weiter, sonst kommt sie ganz
            else:
                kopf = {"If-None-Match": etag_alt} if etag_alt else {}  # unverändert: 304
            ziel = Dateiziel(teil, versatz, self._beginn(adresse, versatz, merk), self._geholt)
            try:
                antwort = await abruf().lade_in_datei(regeln.GUTENBERG_DATEIEN, adresse, ziel, HOECHSTENS, kopf)
            except AnfrageFalsch as f:                          # 404 hier, oder der Stand passt nicht (416): von vorn
                letzter = f
                await asyncio.to_thread(self._teil_weg)
                continue
            except QuelleFehler as f:
                letzter = f
                if ruhig(f):
                    break
                continue
            if antwort.status == 304:
                return None
            if antwort.status not in (200, 206):
                letzter = AnfrageFalsch("die Datei kam nicht")
                continue
            gesamt = self._merkzettel_lesen().get("gesamt")
            if gesamt and teil.stat().st_size != gesamt:
                raise Ausgefallen("die Datei kam nicht ganz, das nächste Mal geht es am Stand weiter")
            return teil
        raise letzter or AnfrageFalsch("die Datei kam nicht")

    # -- Rückmeldungen aus dem Abruf (laufen im Thread des Versands) ---------------------------------------------------------
    def _beginn(self, adresse: str, versatz: int, merk: dict) -> Callable[[int, dict[str, str]], None]:
        def beginn(status: int, kopf: dict[str, str]) -> None:
            fortgesetzt = status == 206 and versatz > 0
            zettel = {"adresse": adresse, "etag": kopf.get("etag") or (merk.get("etag", "") if fortgesetzt else ""),
                      "stand": kopf.get("last-modified") or (merk.get("stand", "") if fortgesetzt else ""), "gesamt": gesamt_aus(kopf, versatz if fortgesetzt else 0)}
            _merkzettel().write_text(json.dumps(zettel), encoding="utf-8")
        return beginn

    def _geholt(self, erledigt: int, gesamt: int | None) -> None:
        self.erledigt, self.gesamt = erledigt, gesamt

    def _gebaut(self, gelesen: int, gesamt: int) -> None:
        self.erledigt, self.gesamt = gelesen, gesamt

    @staticmethod
    def _merkzettel_lesen() -> dict:
        try:
            return json.loads(_merkzettel().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _teil_weg() -> None:
        _teil().unlink(missing_ok=True)
        _merkzettel().unlink(missing_ok=True)

    # -- Suchen ---------------------------------------------------------------------------------------------------------------
    async def vorschlaege(self, wort: str, sprache: str = "", seite: int = 1) -> Fundliste:
        """Beim Tippen: nur mit einem Wort, nur aus dem Katalog; ohne Katalog eine leere Liste."""
        if not _ausdruck(wort) or not await self.da():
            return Fundliste(seite=seite, herkunft="katalog")
        return await asyncio.to_thread(_suchen, ort(), wort, "", sprache, seite, SEITE)

    async def suche(self, wort: str = "", sprache: str = "", thema: str = "", seite: int = 1) -> Fundliste:
        """Wie die Suche bei Gutendex (Wort, Sprachen, Thema, Seite), für den Rückfall; ohne Wort nach Sprache und Thema."""
        if not await self.da():
            return Fundliste(seite=seite, herkunft="katalog")
        return await asyncio.to_thread(_suchen, ort(), wort, thema, sprache, seite, SEITE)

    async def abgleichen(self, fragen: list[Buchfrage]) -> list[Fundbuch | None]:
        """Je Frage (Titel, Autor, Sprache) das gemeinfreie Buch, das sicher dasselbe ist; nur im Katalog, ohne Netz."""
        if not fragen or not regeln.GUTENBERG.aktiv or not await self.da():
            return [None] * len(fragen)
        return await asyncio.to_thread(_abgleichen, ort(), fragen)


def _datum(last_modified: str) -> str:
    """"Sun, 08 Nov 2026 22:43:51 GMT" als "2026-11-08"; leer, wenn es keins ist."""
    try:
        return email.utils.parsedate_to_datetime(last_modified).strftime("%Y-%m-%d") if last_modified else ""
    except (TypeError, ValueError):
        return ""


katalog = Katalog()
