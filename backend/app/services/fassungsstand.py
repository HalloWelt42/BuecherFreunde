"""Was man über eine Übersetzung wissen will (BF-71): die Fassungen eines Buchs, die Rückfrage vor dem Start, der Stand mit
Stationen und Kapiteln, der Prüfbericht (docs/neubau/UEBERSETZUNG.md, Schnittstelle).

Geschätzt wird aus dem Tempo dieses Rechners in Sekunden je Seite (eine Seite: UEBERSETZEN_WOERTER_JE_SEITE Wörter Text):
im Lauf aus dem Tempo dieses Laufs, sobald eine Seite fertig ist; sonst aus dem Mittel der letzten fertigen Läufe
(UEBERSETZEN_TEMPO_LAEUFE); vor dem ersten aus der Vorgabe UEBERSETZEN_S_JE_SEITE."""

from __future__ import annotations

import asyncio
import math
from collections import Counter
from datetime import datetime, timedelta, timezone

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.models.fassung import (
    IN_ARBEIT, MIT_DEUTSCH, Bericht, FassungEintrag, FassungStand, Folgen, KapitelStand, LaufEintrag, OffeneStelle, Station, Stationsstand,
    Zahlen,
)
from backend.app.quellen.sprache import kuerzel
from backend.app.services import begriffsliste, fassung_ablage, fassungen
from backend.app.services.fassungen import BlockZeile, Buchangaben, FassungZeile
from backend.app.services.ki import ki
from backend.app.services.uebersetzungslauf import uebersetzungslauf
from backend.app.uebersetzung import begriffe, marken
from backend.app.uebersetzung.sprache import buch_ist_englisch
from backend.app.uebersetzung.zerlegen_epub import NichtLesbar

ARTWORT = {"ueberschrift": "Überschrift", "absatz": "Absatz", "listenpunkt": "Listenpunkt", "tabellenzelle": "Tabellenzelle",
           "bildunterschrift": "Bildunterschrift", "fussnote": "Fußnote"}
PROBE_WOERTER = 3000                                 # so viel Text entscheidet, ob ein Buch ohne Angabe englisch ist
FORMATE = ("epub",)                                  # was schon übersetzt wird


def _seiten(woerter: int) -> float:
    return woerter / settings.uebersetzen_woerter_je_seite


def _um(sekunden: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=sekunden)).strftime("%Y-%m-%dT%H:%M:%SZ")


async def tempo(f: FassungZeile | None = None) -> float:
    """Sekunden je Seite: im Lauf aus diesem Lauf, sonst aus den letzten fertigen Läufen, sonst die Vorgabe."""
    if f is not None and f.bisher_s > 0:
        z = await db.fetch_one(f"SELECT COALESCE(SUM(woerter), 0) AS w FROM uebersetzung_block WHERE fassung_id = ? "
                               f"AND stand NOT IN ({','.join('?' * len(IN_ARBEIT))})", (f.id, *IN_ARBEIT))
        if _seiten(z["w"]) >= 1:
            return f.bisher_s / _seiten(z["w"])
    laeufe = await db.fetch_all("SELECT bisher_s, woerter FROM fassung WHERE stand = 'fertig' AND bisher_s > 0 AND woerter > 0 "
                                "ORDER BY geaendert_am DESC LIMIT ?", (settings.uebersetzen_tempo_laeufe,))
    werte = [z["bisher_s"] / _seiten(z["woerter"]) for z in laeufe if _seiten(z["woerter"]) >= 1]
    return sum(werte) / len(werte) if werte else settings.uebersetzen_s_je_seite


# -- Zahlen -------------------------------------------------------------------------------------------------------------------

def zahlen_aus(zeilen: list[BlockZeile]) -> Zahlen:
    n = Counter(z.stand for z in zeilen)
    return Zahlen(bloecke=len(zeilen), uebersetzt=sum(n[s] for s in MIT_DEUTSCH), bestanden=n["bestanden"],
                  nachgearbeitet=n["nachgearbeitet"], offen=n["offen"])


def _kapitel_fertig(zeilen: list[BlockZeile]) -> bool:
    return not any(z.stand in IN_ARBEIT for z in zeilen)


class _Kapitelzahlen:
    """Kapitel und Restzeit einer Fassung aus ihren Blöcken."""

    def __init__(self, zeilen: list[BlockZeile], s_je_seite: float) -> None:
        je_kapitel: dict[int, list[BlockZeile]] = {}
        for z in zeilen:
            je_kapitel.setdefault(z.kapitel, []).append(z)
        self.fertig = sum(map(_kapitel_fertig, je_kapitel.values()))
        self.gesamt = len(je_kapitel)
        self.noch_s = _seiten(sum(z.woerter for z in zeilen if z.stand in IN_ARBEIT)) * s_je_seite
        self.anteil = (len(zeilen) - sum(z.stand in IN_ARBEIT for z in zeilen)) / len(zeilen) if zeilen else 0.0


async def eintraege(b: Buchangaben, angelegt: str, wahl: str = "") -> list[FassungEintrag]:
    """Das Original zuerst, dann jede Fassung; `wahl` (Sprache, leer: das Original) ist die gewählte."""
    aus = [FassungEintrag(id=None, sprache=kuerzel(b.language) or "en", original=True, stand="fertig", angelegt=angelegt, geaendert=angelegt)]
    for f in await fassungen.alle_zum_buch(b.id):
        k = _Kapitelzahlen(await fassungen.bloecke(f.id), await tempo(f))
        aus.append(FassungEintrag(id=f.id, sprache=f.sprache, original=False, stand=f.stand, kapitel_fertig=k.fertig, kapitel_gesamt=k.gesamt,
                                  fertig_gegen=_um(k.noch_s) if f.stand == "laeuft" else None, modell=f.modell, pruefmodell=f.pruefmodell,
                                  angelegt=f.angelegt_am, geaendert=f.geaendert_am, gewaehlt=f.sprache == wahl))
    if not any(e.gewaehlt for e in aus):
        aus[0].gewaehlt = True
    return aus


async def laeufe() -> list[LaufEintrag]:
    """Jede Fassung in Arbeit (läuft, Pause, Fehler) mit dem Titel ihres Buchs, in der Folge, in der der Lauf sie nimmt."""
    aus = []
    for z in await db.fetch_all("SELECT f.id, b.title FROM fassung f JOIN books b ON b.id = f.buch_id "
                                "WHERE f.stand IN ('laeuft', 'pause', 'fehler') ORDER BY f.angelegt_am, f.id"):
        f = await fassungen.holen(z["id"])
        if f is None:
            continue
        k = _Kapitelzahlen(await fassungen.bloecke(f.id), await tempo(f))
        aus.append(LaufEintrag(id=f.id, buch_id=f.buch_id, titel=z["title"] or "", sprache=f.sprache, stand=f.stand, anteil=round(k.anteil, 4),
                               kapitel_fertig=k.fertig, kapitel_gesamt=k.gesamt, fertig_gegen=_um(k.noch_s) if f.stand == "laeuft" else None,
                               grund=f.grund))
    return aus


# -- Rückfrage vor dem Start --------------------------------------------------------------------------------------------------

async def folgen(b: Buchangaben, sprache: str = "de") -> Folgen:
    """Was das Übersetzen bedeutet; liest und zerlegt dafür das Original."""
    if b.file_format.lower().lstrip(".") not in FORMATE:
        return Folgen(geht=False, grund=f"Das Format {b.file_format.upper() or 'ohne Endung'} wird noch nicht übersetzt, bisher nur EPUB")
    if not ki.bereit:
        return Folgen(geht=False, grund="Keine Leitstelle eingetragen: ohne KI wird nicht übersetzt")
    original = await fassungen.original_lesen(b)
    if original is None:
        return Folgen(geht=False, grund="Das Original ist gerade nicht zu holen")
    try:
        zerlegung = await asyncio.to_thread(fassungen.zerlegung_aus, original)
    except NichtLesbar as e:
        return Folgen(geht=False, grund=str(e))
    bloecke = zerlegung.bloecke()
    probe, summe = [], 0
    for x in bloecke:
        if summe >= PROBE_WOERTER:
            break
        probe.append(marken.klartext(x.vorlage))
        summe += x.woerter
    if not buch_ist_englisch(b.language or zerlegung.sprache, " ".join(probe)):
        return Folgen(geht=False, grund=f"Das Buch ist nicht englisch (Sprache: {kuerzel(b.language or zerlegung.sprache) or 'nach dem Text'})")
    f = await fassungen.zum_buch(b.id, sprache)
    if f is not None and f.zerlegt == fassungen.zerlegt_mit():
        offen = sum(z.woerter for z in await fassungen.bloecke(f.id, staende=IN_ARBEIT))
    else:
        offen = sum(x.woerter for x in bloecke)
    vorhanden = await begriffsliste.vorhandene(b.id)
    s_je_seite = await tempo(f)
    dauer = _seiten(offen) * s_je_seite
    return Folgen(seiten=math.ceil(_seiten(sum(x.woerter for x in bloecke))), kapitel=len(zerlegung.mit_bloecken()), bloecke=len(bloecke),
                  begriffe=len(vorhanden) + len(begriffe.namen(bloecke, vorhanden)), abbildungen=zerlegung.abbildungen,
                  dauer_s=round(dauer, 1), fertig_gegen=_um(dauer), tempo_s_je_seite=round(s_je_seite, 1),
                  ablage=await fassung_ablage.ort(sprache, b), geht=True)


# -- Stand --------------------------------------------------------------------------------------------------------------------

def _station(name: str, laeuft: bool, fertig: bool, text: str) -> Station:
    stand: Stationsstand = "laeuft" if laeuft else "fertig" if fertig else "wartet"
    return Station(name=name, stand=stand, text=text)


def _stationen(f: FassungZeile, zeilen: list[BlockZeile], station: str | None) -> list[Station]:
    n = Counter(z.stand for z in zeilen)
    zerlegt = bool(f.zerlegt)
    kapitel = len({z.kapitel for z in zeilen})
    nicht = f"; {len(f.nicht_lesbar)} Dateien nicht lesbar, sie bleiben im Original" if f.nicht_lesbar else ""
    uebersetzt = len(zeilen) - n["wartet"]
    geprueft = sum(z.geprueft for z in zeilen)
    return [
        _station("Zerlegen", station == "Zerlegen", zerlegt, f"{len(zeilen)} Blöcke in {kapitel} Kapiteln{nicht}" if zerlegt else ""),
        _station("Begriffe", station == "Begriffe", f.begriffe_fertig, f.begriffe_text),
        _station("Übersetzen", station == "Übersetzen", zerlegt and not n["wartet"], f"{uebersetzt} von {len(zeilen)} Blöcken"),
        _station("Prüfen", station == "Prüfen", zerlegt and not (n["wartet"] or n["uebersetzt"]), f"{geprueft} von {len(zeilen)} Blöcken geprüft"),
        _station("Nacharbeit", station == "Nacharbeit", zerlegt and not any(n[s] for s in IN_ARBEIT),
                 f"{n['nachgearbeitet']} nachgearbeitet, {n['nacharbeit']} warten, {n['offen']} offen"),
        _station("Setzen", station == "Setzen", f.datei_aktuell, f"Abgelegt: {f.datei}" if f.datei else ""),
    ]


async def stand(f: FassungZeile) -> FassungStand:
    zeilen = await fassungen.bloecke(f.id)
    jetzt = uebersetzungslauf.jetzt if uebersetzungslauf.jetzt is not None and uebersetzungslauf.jetzt.fassung == f.id else None
    s_je_seite = await tempo(f)
    kapitel = []
    for k in await fassungen.kapitel(f.id):
        im = [z for z in zeilen if z.kapitel == k.nr]
        n = Counter(z.stand for z in im)
        rest = _seiten(sum(z.woerter for z in im if z.stand in IN_ARBEIT)) * s_je_seite
        laeuft = jetzt is not None and jetzt.kapitel == k.nr
        fertig = _kapitel_fertig(im)
        kapitel.append(KapitelStand(nr=k.nr, titel=k.titel, stand="laeuft" if laeuft else "fertig" if fertig else "wartet",
                                    dauer_s=round(k.dauer_s + (0 if fertig else rest), 1), geschaetzt=not fertig, bloecke=len(im),
                                    fertig=len(im) - sum(n[s] for s in IN_ARBEIT), geprueft=sum(z.geprueft for z in im),
                                    nachgearbeitet=n["nachgearbeitet"], offen=n["offen"]))
    noch = _seiten(sum(z.woerter for z in zeilen if z.stand in IN_ARBEIT)) * s_je_seite
    return FassungStand(id=f.id, stand=f.stand, begonnen=f.begonnen, bisher_s=round(f.bisher_s, 1), noch_s=round(noch, 1),
                        fertig_gegen=_um(noch) if f.stand == "laeuft" else None, tempo_s_je_seite=round(s_je_seite, 1),
                        kapitel_jetzt=jetzt.kapitel if jetzt else None, block_jetzt=jetzt.block if jetzt else None,
                        stationen=_stationen(f, zeilen, jetzt.station if jetzt else None), kapitel=kapitel, zahlen=zahlen_aus(zeilen),
                        grund=f.grund)


# -- Bericht ------------------------------------------------------------------------------------------------------------------

async def bericht(f: FassungZeile) -> Bericht:
    zeilen = await fassungen.bloecke(f.id)
    titel = {k.nr: k.titel for k in await fassungen.kapitel(f.id)}
    offen = [OffeneStelle(kennung=z.kennung, kapitel=z.kapitel, ort=f"{titel.get(z.kapitel, z.kapitel)}, {ARTWORT.get(z.art, z.art)} {z.nr}",
                          original=z.vorlage, deutsch=z.uebersetzung, befunde=z.befunde)
             for z in zeilen if z.stand == "offen"]
    return Bericht(zahlen=zahlen_aus(zeilen), offen=offen)

