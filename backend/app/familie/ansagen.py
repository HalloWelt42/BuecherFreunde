"""Feste Ansagen für den Kinderbereich (BF-78): Tasten, Hinweise und Bausteine der Uhr aus `ansagen.json`, dazu die Ansagen, die
von Dingen abhängen (Titel der Bücher, die ein Kind sieht, der Name seiner Katze, seine Ruhezeit, die Namen der Profile für
"Wer liest?"). Gesprochen werden sie vorab über die Vertonung mit der gewählten Stimme (familie/ansagelauf.py, eingebaut,
privat oder fremd) und dauerhaft abgelegt im Ort texte unter `ansagen/<ordner der stimme>/<schluessel>-<pruefsumme>.wav`
(vorlesen/tonablage.py); die Prüfsumme gehört zu Fassung und Text, so entsteht bei geändertem Text ein neuer Ton.

Die Schlüssel heißen `gruppe.name` wie in der Oberfläche (frontend/src/lib/kind/ansagen.ts): `tasten.weiter`,
`hinweise.frag_eltern`, `uhr.4`, `minute.35`, `noch.25`, `heute.45`, `titel.<buch>`, `katze`, `katze.<vorschlag>`,
`profil.<profil>`, `ruhezeit`. Die Probe einer Stimme ist eine Stimmprobe (vorlesen/proben.py).

Welche Stimme gilt: die Wahl der Eltern je Kind (`lesehilfen.stimme`), sonst die Vorlesestimme der Familie, sonst keine (dann
schweigen die Ansagen). `geraet` ist die Stimme des Geräts, nur als ausdrückliche Wahl: dann spricht die Oberfläche die Texte.

Hörer sind jedes Kind und die Profilwahl (dort hören auch Erwachsene). Je Hörer steht in `ansage_hoerer` die Stimme, deren
Ansagen er zuletzt ganz hatte; nach einem Wechsel der Stimme gelten ihre Töne weiter, bis die der neuen fertig sind."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.core import einstellungen
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.familie import lesezeit, profile
from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht
from backend.app.familie.stufen import stufenbuch
from backend.app.vorlesen import tonablage
from backend.app.vorlesen.modelle import vertont

DATEI = Path(__file__).with_name("ansagen.json")
ORDNER = "ansagen"
FAMILIENSTIMME = "familie_stimme"             # Schlüssel in app_settings: die Vorlesestimme der Familie
PROFILWAHL = "profilwahl"                     # der Hörer der Profilwahl (und der Erwachsenen) in ansage_hoerer


# -- Texte ----------------------------------------------------------------------------------------------------------------------

class Baustein(BaseModel):
    gruppe: str
    text: str
    einzahl: str = ""                         # wenn das Zahlwort auf "eine" endet: "Noch eine Minute"
    von: int = Field(ge=0)
    bis: int = Field(ge=0)
    form: Literal["zahl", "vor", "weiblich"]  # eins, ein (Uhr), eine (Minute)


class Zahlen(BaseModel):
    null: str
    eins: dict[Literal["zahl", "vor", "weiblich"], str]
    einer: list[str] = Field(min_length=10, max_length=10)
    zehn_bis_neunzehn: list[str] = Field(min_length=10, max_length=10)
    zehner: list[str] = Field(min_length=10, max_length=10)
    und: str
    hundert: str
    uhr: str


class Texte(BaseModel):
    fassung: int
    tasten: dict[str, str]
    hinweise: dict[str, str]
    bausteine: list[Baustein]
    dinge: dict[Literal["titel", "katze", "katzenvorschlag", "profil", "ruhezeit"], str]
    zahlen: Zahlen


@lru_cache(maxsize=1)
def texte() -> Texte:
    return Texte.model_validate(json.loads(DATEI.read_text(encoding="utf-8")))


def zahlwort(n: int, form: Literal["zahl", "vor", "weiblich"] = "zahl") -> str:
    """0 bis 999 als deutsches Wort: 1 eins, ein oder eine, 21 einundzwanzig, 101 hunderteins."""
    z = texte().zahlen
    if not 0 <= n <= 999:
        raise ValueError(f"{n} liegt außerhalb von 0 bis 999")
    if n == 0:
        return z.null
    hunderter, rest = divmod(n, 100)
    vorne = (z.einer[hunderter] if hunderter > 1 else "") + z.hundert if hunderter else ""
    if rest == 0:
        return vorne
    if rest == 1:
        return vorne + z.eins[form]
    if rest < 10:
        return vorne + z.einer[rest]
    if rest < 20:
        return vorne + z.zehn_bis_neunzehn[rest - 10]
    zehner, einer = divmod(rest, 10)
    return vorne + (z.einer[einer] + z.und if einer else "") + z.zehner[zehner]


def uhrzeit_wort(text: str) -> str:
    """"06:30" wird "sechs Uhr dreißig", "07:00" wird "sieben Uhr"."""
    stunde, minute = (int(t) for t in text.split(":"))
    worte = f"{zahlwort(stunde, 'vor')} {texte().zahlen.uhr}"
    return f"{worte} {zahlwort(minute)}" if minute else worte


class Eintrag(BaseModel):
    schluessel: str                           # so heißt die Ansage für die Oberfläche, gruppe.name
    text: str

    @property
    def datei(self) -> str:
        """Schlüssel und Prüfsumme aus Fassung und Text: ein geänderter Text gibt einen neuen Ton."""
        return tonablage.dateiname(self.schluessel, str(texte().fassung), self.text)


def allgemeine() -> list[Eintrag]:
    """Tasten, Hinweise und Bausteine der Uhr, für jede Stimme gleich."""
    t = texte()
    aus = [Eintrag(schluessel=f"tasten.{k}", text=v) for k, v in t.tasten.items()]
    anzahl = zahlwort(stufenbuch().zugang.bild_pin_anzahl)
    aus += [Eintrag(schluessel=f"hinweise.{k}", text=v.replace("{anzahl}", anzahl)) for k, v in t.hinweise.items()]
    for b in t.bausteine:
        for n in range(b.von, b.bis + 1):
            wort = zahlwort(n, b.form)
            vorlage = b.einzahl if b.einzahl and wort.endswith(t.zahlen.eins["weiblich"]) else b.text
            aus.append(Eintrag(schluessel=f"{b.gruppe}.{n}", text=vorlage.replace("{n}", wort)))
    return aus


async def eigene(kind: Profil) -> list[Eintrag]:
    """Was nur dieses Kind hört: die Titel der Bücher, die es sieht (erst nach der Freigabe), der Name seiner Katze, im
    Vorlesealter die Vorschläge dafür (stufen.json, `katze.vorschlaege`), seine Ruhezeit."""
    d = texte().dinge
    bedingung, werte = Sicht.von(kind).bedingung("b.id")
    buecher = await db.fetch_all(f"SELECT b.id, b.title FROM books b WHERE {bedingung} AND TRIM(b.title) != '' ORDER BY b.id", werte)
    aus = [Eintrag(schluessel=f"titel.{b['id']}", text=d["titel"].replace("{titel}", b["title"].strip())) for b in buecher]
    if name := kind.einstellungen.katze.name.strip():
        aus.append(Eintrag(schluessel="katze", text=d["katze"].replace("{name}", name)))
    if kind.stufe and stufenbuch().stufe(kind.stufe).katze_name == "vorschlaege":
        aus += [Eintrag(schluessel=f"katze.{v}", text=d["katzenvorschlag"].replace("{name}", v)) for v in stufenbuch().katze.vorschlaege]
    regel = lesezeit.wirksam(kind)
    if regel and regel.ruhe_an:
        aus.append(Eintrag(schluessel="ruhezeit", text=d["ruhezeit"].replace("{uhrzeit}", uhrzeit_wort(regel.ruhe_bis))))
    return aus


async def namen() -> list[Eintrag]:
    """Die Namen der Profile für "Wer liest?"."""
    return [Eintrag(schluessel=f"profil.{p.id}", text=texte().dinge["profil"].replace("{name}", p.name)) for p in await profile.alle()]


# -- Stimmen ----------------------------------------------------------------------------------------------------------------------

async def familienstimme() -> str:
    return await einstellungen.lesen(FAMILIENSTIMME) or ""


async def familienstimme_setzen(stimme: str) -> None:
    await einstellungen.schreiben(FAMILIENSTIMME, stimme)


async def stimme_fuer(p: Profil | None) -> str:
    """Ein Kind hört die Wahl der Eltern, sonst die Familienstimme; Erwachsene und die Profilwahl die Familienstimme."""
    if p is not None and p.kind and p.einstellungen.lesehilfen.stimme:
        return p.einstellungen.lesehilfen.stimme
    return await familienstimme()


async def fuer(p: Profil | None) -> tuple[str, list[Eintrag]]:
    """Stimme und Ansagen, die dieses Profil hört; ohne Profil die der Profilwahl."""
    eintraege = allgemeine() + (await eigene(p) if p is not None and p.kind else await namen())
    return await stimme_fuer(p), eintraege


def hoerer(p: Profil | None) -> str:
    """Wer die Ansagen hört: ein Kind seine eigenen, alle anderen die der Profilwahl."""
    return p.id if p is not None and p.kind else PROFILWAHL


async def je_hoerer() -> dict[str, tuple[str, list[Eintrag]]]:
    """Je Hörer die Stimme, die gilt, und alles, was er mit ihr hört."""
    aus = {PROFILWAHL: (await familienstimme(), allgemeine() + await namen())}
    for p in await profile.alle():
        if p.kind:
            aus[p.id] = (await stimme_fuer(p), allgemeine() + await eigene(p))
    return aus


async def zuletzt(wer: str) -> str:
    """Die Stimme, deren Ansagen dieser Hörer zuletzt ganz hatte; leer: noch keine."""
    z = await db.fetch_one("SELECT stimme FROM ansage_hoerer WHERE hoerer = ?", (wer,))
    return z["stimme"] if z else ""


async def zuletzt_alle() -> dict[str, str]:
    return {z["hoerer"]: z["stimme"] for z in await db.fetch_all("SELECT hoerer, stimme FROM ansage_hoerer")}


def pfad(stimme: str, e: Eintrag | None = None) -> Path:
    ort = settings.storage_dir / ORDNER / tonablage.ordner(stimme)
    return ort / e.datei if e is not None else ort


def pfad_im_ordner(ordner_der_stimme: str, datei: str) -> Path:
    """Die Datei eines Tons nach Ordner und Namen (beide vorher nach ihrer Form geprüft)."""
    return settings.storage_dir / ORDNER / ordner_der_stimme / datei


def adresse(stimme: str, e: Eintrag) -> str:
    return f"/api/familie/ansagen/ton/{tonablage.ordner(stimme)}/{e.datei}"


def bedarf(hoerende: dict[str, tuple[str, list[Eintrag]]]) -> dict[str, list[Eintrag]]:
    """Je vorab gesprochener Stimme alles, was jemand mit ihr hört; jede Datei einmal."""
    je: dict[str, dict[str, Eintrag]] = {}
    for stimme, eintraege in hoerende.values():
        if vertont(stimme):
            ziel = je.setdefault(stimme, {})
            for e in eintraege:
                ziel.setdefault(e.datei, e)
    return {s: list(e.values()) for s, e in je.items()}


def ganz(stimme: str, eintraege: list[Eintrag]) -> bool:
    """Liegt jede dieser Ansagen in dieser Stimme bereit?"""
    ort = pfad(stimme)
    return all((ort / e.datei).exists() for e in eintraege)
