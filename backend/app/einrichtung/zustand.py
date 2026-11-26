"""Zustand der Ersteinrichtung (BF-82): ob die Installation neu ist, welche Ausgangslage gilt, welcher Schritt offen ist.

Neu ist eine Installation nur, wenn beim ersten Start der Bestand leer war und keine Markerdatei trug (`ablage/orte.py`); das
merkt `erkennen` einmal in der Tabelle `einrichtung`. Eine laufende Installation bekommt dabei `aus` und sieht den Assistenten
nie von selbst. Die Schritte je Ausgangslage stehen in `schritte.json`; gemerkt wird, was erledigt oder übersprungen ist, und
so geht es nach einem Neustart am ersten offenen Schritt weiter. Ob es ein Konto gibt und ob ein Schritt wegen einer Bedingung
entfällt, bestimmt der Zustand jedes Mal selbst (eine Wahrheit: die Anmeldung, die Kellerwolke).

Unter Wartung (`oeffnen`) zeigt der Assistent nur die Schritte von "Neu beginnen" ohne Konto; was er dort ändern würde, steht
als Änderung da und gilt erst nach der Bestätigung (einrichtung/wartung.py)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from backend.app.ablage.wolke import wolke
from backend.app.core import anmeldung as anmeldung_modul
from backend.app.core.database import db
from backend.app.einrichtung.modelle import Ausgangslage, Ausgangslagename, Einrichtung, Modus, Schritt

DATEI = Path(__file__).with_name("schritte.json")


class Einrichtungsfehler(Exception):
    """Ein Schritt geht so nicht; `status` für die Antwort."""

    status = 409

    def __init__(self, meldung: str, status: int | None = None) -> None:
        super().__init__(meldung)
        self.meldung = meldung
        if status is not None:
            self.status = status


class Schrittbeschreibung(BaseModel):
    name: str
    pflicht: bool
    erledigt: str
    wenn: str = ""                     # ohne_kellerwolke: entfällt mit Kellerwolke


class Schrittbuch(BaseModel):
    schritte: dict[str, Schrittbeschreibung]
    ausgangslagen: list[Ausgangslage]
    wartung: list[str]

    def lage(self, schluessel: str) -> Ausgangslage:
        return next(a for a in self.ausgangslagen if a.schluessel == schluessel)


@lru_cache(maxsize=1)
def schrittbuch() -> Schrittbuch:
    buch = Schrittbuch.model_validate(json.loads(DATEI.read_text(encoding="utf-8")))
    for liste in [buch.wartung, *(a.schritte for a in buch.ausgangslagen)]:
        if fremd := [s for s in liste if s not in buch.schritte]:
            raise ValueError(f"schritte.json nennt unbekannte Schritte: {', '.join(fremd)}")
    return buch


def jetzt() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def erkennen(neu: bool) -> None:
    """Beim Start: einmal merken, ob die Installation neu ist; eine gemerkte Zeile bleibt, wie sie ist."""
    await db.execute("INSERT OR IGNORE INTO einrichtung(id, neu, modus) VALUES (1, ?, ?)", (int(neu), "neu" if neu else "aus"))
    await db.commit()


async def zeile() -> dict | None:
    return await db.fetch_one("SELECT * FROM einrichtung WHERE id = 1")


async def modus() -> Modus:
    z = await zeile()
    return z["modus"] if z else "aus"


async def konto_da() -> bool:
    """Ein Konto, mit dem man sich anmelden kann: eigenes angelegt, oder die Kellerwolke ist mit App-Zugang eingetragen."""
    eigene = anmeldung_modul.anmeldung.eigene
    return await eigene.eingerichtet() if eigene is not None else wolke.bereit


async def bestand_leer() -> bool:
    return await db.fetch_one("SELECT 1 FROM books LIMIT 1") is None


async def _gemerkt() -> dict[str, dict]:
    return {z["schritt"]: z for z in await db.fetch_all("SELECT * FROM einrichtung_schritt")}


async def vermerken(schritt: str, stand: str = "erledigt", text: str = "") -> None:
    """Ein Schritt ist erledigt oder übersprungen; `text` sagt, was eingerichtet ist (für den Abschluss)."""
    if stand == "erledigt" and not text:
        text = schrittbuch().schritte[schritt].erledigt
    await db.execute("INSERT INTO einrichtung_schritt(schritt, stand, text, geaendert_am) VALUES (?, ?, ?, ?) "
                     "ON CONFLICT(schritt) DO UPDATE SET stand = excluded.stand, text = excluded.text, geaendert_am = excluded.geaendert_am",
                     (schritt, stand, text, jetzt()))
    await db.execute("UPDATE einrichtung SET geaendert_am = ? WHERE id = 1", (jetzt(),))
    await db.commit()


async def _weiter(schritt: str) -> tuple[bool, str]:
    """Ob ein Schritt als erledigt gelten darf; sonst der Grund (Weiter gesperrt)."""
    from backend.app.einrichtung import auftrag, orte as orte_schritt

    if schritt == "konto":
        return (True, "") if await konto_da() else (False, "Erst ein Konto anlegen oder mit der Kellerwolke anmelden")
    if schritt == "orte":
        return await orte_schritt.bereit()
    if schritt in ("pruefung", "neuaufbau"):
        s = await auftrag.stand_von(schritt)
        return (True, "") if s.stand == "fertig" else (False, f"Erst wenn der Auftrag \"{s.was}\" fertig ist")
    if schritt in ("sicherung", "verbinden", "ordner", "originale"):
        return False, "Dieser Schritt ist erledigt, sobald er gelaufen ist"
    return True, ""


async def _schritte(lage: list[str], gemerkt: dict[str, dict]) -> list[Schritt]:
    buch, aus = schrittbuch(), []
    for s in lage:
        b = buch.schritte[s]
        if b.wenn == "ohne_kellerwolke" and wolke.bereit:
            aus.append(Schritt(schluessel=s, name=b.name, pflicht=b.pflicht, stand="entfaellt", text="Die Originale liegen in der Kellerwolke"))
            continue
        weiter, grund = await _weiter(s)
        if s == "konto":
            stand, text = ("erledigt", b.erledigt) if weiter else ("offen", "")
        else:
            g = gemerkt.get(s)
            stand, text = (g["stand"], g["text"]) if g else ("offen", "")
        if stand == "erledigt":
            weiter, grund = True, ""
        aus.append(Schritt(schluessel=s, name=b.name, pflicht=b.pflicht, stand=stand, text=text, weiter=weiter, grund=grund))
    return aus


async def lesen(angemeldet: bool = True) -> Einrichtung:
    """Der ganze Zustand. Ohne Anmeldung nur, solange die Ersteinrichtung offen ist; sonst `aus` ohne Einzelheiten."""
    z = await zeile()
    m: Modus = z["modus"] if z else "aus"
    anmeldung = "eigen" if anmeldung_modul.anmeldung.eigene is not None else "kellerwolke"
    if m == "aus" or (m == "wartung" and not angemeldet):
        return Einrichtung(modus="aus", zeigen=False, anmeldung=anmeldung, abgeschlossen_am=z["abgeschlossen_am"] if z and angemeldet else None)
    buch = schrittbuch()
    if m == "wartung":
        lage = buch.wartung
        aenderungen = (await db.fetch_one("SELECT COUNT(*) AS n FROM einrichtung_aenderung"))["n"]
        schritte = [s.model_copy(update={"stand": "offen", "text": ""}) for s in await _schritte(lage, {})]
    else:
        lage = buch.lage(z["ausgangslage"]).schritte if z["ausgangslage"] else []
        aenderungen = 0
        schritte = await _schritte(lage, await _gemerkt())
    offen = next((s.schluessel for s in schritte if s.stand == "offen"), None)
    return Einrichtung(modus=m, zeigen=True, ausgangslage=z["ausgangslage"], schritt=offen, schritte=schritte,
                       ausgangslagen=buch.ausgangslagen if m == "neu" else [], konto=await konto_da(), anmeldung=anmeldung,
                       aenderungen=aenderungen, begonnen_am=z["begonnen_am"], abgeschlossen_am=z["abgeschlossen_am"])


async def nur_neu() -> dict:
    """Die Zeile, wenn die Ersteinrichtung offen ist; sonst 409. Eine laufende Installation ändert so nichts."""
    z = await zeile()
    if z is None or z["modus"] != "neu":
        raise Einrichtungsfehler("Die Ersteinrichtung gibt es nur bei einer neuen Installation; unter Wartung lässt sich der Assistent "
                                 "wieder öffnen")
    return z


async def ausgangslage_waehlen(wahl: Ausgangslagename) -> Einrichtung:
    """Wählbar, solange nichts aus einer Sicherung, einem Umzug oder der Kellerwolke übernommen ist und keine Bücher da sind."""
    z = await nur_neu()
    uebernommen = await db.fetch_one("SELECT 1 FROM einrichtung_schritt WHERE schritt IN ('sicherung', 'verbinden', 'neuaufbau') "
                                     "AND stand = 'erledigt'")
    if z["ausgangslage"] != wahl and (uebernommen or not await bestand_leer()):
        raise Einrichtungsfehler("Die Ausgangslage lässt sich nicht mehr wechseln, es ist schon etwas übernommen")
    if z["ausgangslage"] != wahl:
        await db.execute("DELETE FROM einrichtung_schritt")
    await db.execute("UPDATE einrichtung SET ausgangslage = ?, begonnen_am = COALESCE(begonnen_am, ?), geaendert_am = ? WHERE id = 1",
                     (wahl, jetzt(), jetzt()))
    await db.commit()
    return await lesen()


async def _lage_gilt(schritt: str) -> None:
    z = await nur_neu()
    if not z["ausgangslage"]:
        raise Einrichtungsfehler("Erst eine Ausgangslage wählen")
    if schritt not in schrittbuch().lage(z["ausgangslage"]).schritte:
        raise Einrichtungsfehler(f"Den Schritt {schritt} gibt es in dieser Ausgangslage nicht", 404)


async def schritt_setzen(schritt: str, aktion: str) -> Einrichtung:
    if schritt not in schrittbuch().schritte:
        raise Einrichtungsfehler("Diesen Schritt gibt es nicht", 404)
    await _lage_gilt(schritt)
    b = schrittbuch().schritte[schritt]
    if schritt in ("konto", "abschluss"):
        raise Einrichtungsfehler("Dieser Schritt ergibt sich von selbst: das Konto mit dem Anlegen, der Abschluss mit Abschließen", 422)
    if aktion == "ueberspringen":
        if b.pflicht:
            raise Einrichtungsfehler(f"{b.name} ist Pflicht und lässt sich nicht überspringen", 422)
        await vermerken(schritt, "uebersprungen", "Übersprungen, später unter Einstellungen")
        return await lesen()
    weiter, grund = await _weiter(schritt)
    if not weiter:
        raise Einrichtungsfehler(grund)
    await vermerken(schritt, "erledigt")
    return await lesen()


async def abschliessen() -> Einrichtung:
    """Nur, wenn jede Pflicht erledigt ist; danach sieht die Installation den Assistenten nur noch unter Wartung."""
    await _lage_gilt("abschluss")
    e = await lesen()
    if offen := [s.name for s in e.schritte if s.schluessel != "abschluss" and s.pflicht and s.stand == "offen"]:
        raise Einrichtungsfehler(f"Noch offen: {', '.join(offen)}")
    await vermerken("abschluss", "erledigt")
    await db.execute("UPDATE einrichtung SET modus = 'aus', abgeschlossen_am = ?, geaendert_am = ? WHERE id = 1", (jetzt(), jetzt()))
    await db.commit()
    from backend.app.einrichtung import katalog_schritt

    await katalog_schritt.nach_dem_abschluss()
    return await lesen()


async def uebersicht() -> list[Schritt]:
    """Was eingerichtet und was übersprungen ist, auch nach dem Abschluss (für die Übersicht)."""
    z = await zeile()
    if not z or not z["ausgangslage"]:
        return []
    return await _schritte(schrittbuch().lage(z["ausgangslage"]).schritte, await _gemerkt())


# -- über das Tauschen des Bestands hinweg (Wiederherstellen, Umzug) --------------------------------------------------------

class Mitnahme(BaseModel):
    """Was beim Tausch des Bestands bleiben muss: der Zustand dieser Einrichtung, nicht der des alten Geräts."""

    einrichtung: dict
    schritte: list[dict]
    auftraege: list[dict]                  # auch der Auftrag, der gerade einspielt


async def mitnehmen() -> Mitnahme:
    return Mitnahme(einrichtung=await zeile() or {}, schritte=await db.fetch_all("SELECT * FROM einrichtung_schritt"),
                    auftraege=await db.fetch_all("SELECT * FROM einrichtung_auftrag"))
