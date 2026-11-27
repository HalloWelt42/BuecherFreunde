"""Auskunft zu einem Autor. Der sicherste Weg zuerst: die ISBN eines seiner Bücher führt über die Nationalbibliothek zu seiner
Kennung in der Normdatei, von dort zu Wikidata und zum Artikel. Nur ohne diesen Weg wird nach dem Namen gesucht und bewertet."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from backend.app.quellen import gnd, wiki
from backend.app.quellen import isbn as nummern
from backend.app.quellen.abgleich import namen_gleich, natuerlich, titel_naehe
from backend.app.quellen.auskunft import QUELLEN
from backend.app.quellen.fehler import QuelleFehler, ruhig
from backend.app.quellen.modelle import Autorangaben, Autorfrage, Werk
from backend.app.quellen.regeln import GND, WIKIPEDIA
from backend.app.quellen.wiki import Eintrag

logger = logging.getLogger("buecherfreunde.quellen.autoren")
ISBN_HOECHSTENS = 2                 # so viele Bücher werden für die Normdatei nachgesehen
WERKE_HOECHSTENS = 30
KANDIDATEN = 8
MENSCH = "Q5"
# Schriftsteller, Autor, Romancier, Dichter, Dramatiker, Essayist, Kinderbuchautor, Science-Fiction-Autor, Journalist,
# Drehbuchautor, Übersetzer, Historiker, Hochschullehrer, Sachbuchautor, Literaturkritiker
SCHREIBENDE = {"Q36180", "Q482980", "Q6625963", "Q49757", "Q214917", "Q11774202", "Q4853732", "Q18844224", "Q1930187", "Q28389", "Q333634", "Q201788", "Q1622272", "Q15980158", "Q4263842"}
# Informatiker, Programmierer, Mathematiker, Physiker, Ingenieur, Ökonom, Jurist, Philosoph, Psychologe, Chemiker, Biologe, Arzt, Wissenschaftler
FACHLEUTE = {"Q82594", "Q5482740", "Q170790", "Q169470", "Q81096", "Q188094", "Q185351", "Q4964182", "Q212980", "Q593644", "Q864503", "Q39631", "Q901"}
PUNKTE_NORMDATEI, PUNKTE_ISBN, PUNKTE_WERK, PUNKTE_BERUF, PUNKTE_NAME, PUNKTE_FACH, PUNKTE_ARTIKEL, PUNKTE_BEKANNT = 30, 30, 15, 10, 8, 6, 5, 10
HOCH, MITTEL = 15, 8
WERK_NAH = 0.9                      # so gleich müssen Werktitel und Buchtitel sein


class Autorauskunft(BaseModel):
    angaben: Autorangaben | None = None
    hinweise: list[str] = Field(default_factory=list)
    ruht: bool = False


@dataclass
class _Lauf:
    """Eine Suche: was gesucht wird und welche Quellen dabei nicht antworteten."""

    frage: Autorfrage
    fehler: list[QuelleFehler] = field(default_factory=list)

    async def oder_nichts(self, aufgabe: Awaitable):
        try:
            return await aufgabe
        except QuelleFehler as f:
            self.fehler.append(f)
            return None


@dataclass
class _Treffer:
    eintrag: Eintrag
    punkte: int
    belegt: bool                       # ein Werk, eine ISBN oder die Normdatei verbindet ihn mit der Bibliothek
    bezuege: dict[str, Eintrag] = field(default_factory=dict)      # Werke und Länder, auf die sich die Einträge beziehen
    einziger: bool = False             # kein anderer Mensch dieses Namens kam in Frage


# -- Normdatei ---------------------------------------------------------------------------------------------------------
async def _kennung_aus_buechern(lauf: _Lauf) -> str:
    """Die Kennung, die ein Katalog für genau diesen Namen an einem Buch der Bibliothek führt."""
    for isbn in lauf.frage.isbns[:ISBN_HOECHSTENS]:
        for kennung in ("dnb", "k10plus") if nummern.deutschsprachig(isbn) else ("k10plus",):
            if QUELLEN[kennung].regel.hindernis:
                continue
            buch = await lauf.oder_nichts(QUELLEN[kennung].nach_isbn(isbn))
            treffer = next((g for n, g in (buch.personen if buch else {}).items() if namen_gleich(n, lauf.frage.name)), "")
            if treffer:
                return treffer
    return ""


def _schrieb_eines(p: gnd.Person, titel: list[str]) -> bool:
    return any(titel_naehe(t, w) >= WERK_NAH for t in titel for w in p.werke if w)


async def _normperson(lauf: _Lauf) -> tuple[gnd.Person | None, bool]:
    """Die Person der Normdatei und ob sie über ein Buch der Bibliothek feststeht."""
    if not GND.aktiv:
        return None, False
    kennung = await _kennung_aus_buechern(lauf)
    person = await lauf.oder_nichts(gnd.person(kennung)) if kennung else None
    if person:
        return person, True
    gefunden = await lauf.oder_nichts(gnd.suche(lauf.frage.name))
    if gefunden is None:
        return None, False
    mit_werk = [p for p in gefunden.personen if _schrieb_eines(p, lauf.frage.titel)]
    if len(mit_werk) == 1:
        return mit_werk[0], True
    return gefunden.einzige, False


# -- Wikidata ----------------------------------------------------------------------------------------------------------
async def _kandidaten(lauf: _Lauf, person: gnd.Person | None) -> tuple[list[Eintrag], dict[str, int]]:
    """Menschen, die gemeint sein könnten, mit ihrer Bekanntheit; steht die Person fest, nur ihr Eintrag."""
    nummer = person.verweise.get("wikidata", "") if person else ""
    if nummer:
        bekannt = {nummer: 0}
    elif person:
        bekannt = await lauf.oder_nichts(wiki.suche(f"haswbstatement:P227={person.gnd}", 1)) or {}
    else:
        bekannt = await lauf.oder_nichts(wiki.suche(f'"{lauf.frage.name}" haswbstatement:P31={MENSCH}', KANDIDATEN)) or {}
    eintraege = (await lauf.oder_nichts(wiki.eintraege(list(bekannt))) or {}) if bekannt else {}
    menschen = [e for e in eintraege.values() if MENSCH in e.texte("P31")]
    return [e for e in menschen if person or any(namen_gleich(lauf.frage.name, n) for n in (e.name, *e.auch))], bekannt


def _bewerten(frage: Autorfrage, e: Eintrag, bekannt: int, bezuege: dict[str, Eintrag], bestaetigt: bool) -> _Treffer:
    berufe = set(e.texte("P106"))
    punkte = PUNKTE_BERUF if berufe & SCHREIBENDE else PUNKTE_FACH if berufe & FACHLEUTE else 0
    punkte += min(bekannt, PUNKTE_BEKANNT) + (PUNKTE_ARTIKEL if "de" in e.artikel else 0)
    punkte += PUNKTE_NAME if any(n.lower() == frage.name.lower() for n in (e.name, *e.auch)) else 0
    werke = [bezuege[n] for n in e.texte("P800") if n in bezuege]
    belege = 0
    if any(titel_naehe(t, w.name) >= WERK_NAH for t in frage.titel for w in werke):
        belege += PUNKTE_WERK
    if any(nummern.gleich(i, n) for w in werke for p in ("P212", "P957") for n in w.texte(p) for i in frage.isbns):
        belege += PUNKTE_ISBN
    if bestaetigt:
        belege += PUNKTE_NORMDATEI
    return _Treffer(e, punkte + belege, belege > 0, bezuege)


async def _bester(lauf: _Lauf, person: gnd.Person | None, steht_fest: bool) -> _Treffer | None:
    menschen, bekannt = await _kandidaten(lauf, person)
    if not menschen:
        return None
    gemeint = [n for e in menschen for p in ("P800", "P27") for n in e.texte(p)]
    bezuege = (await lauf.oder_nichts(wiki.eintraege(gemeint)) or {}) if gemeint else {}
    kennung = person.gnd if person and steht_fest else ""
    treffer = [_bewerten(lauf.frage, e, bekannt.get(e.id, 0), bezuege, kennung in e.texte("P227")) for e in menschen]
    bester = max(treffer, key=lambda t: t.punkte)
    bester.einziger = len(treffer) == 1
    return bester


# -- Zusammensetzen ----------------------------------------------------------------------------------------------------
def _stufe(t: _Treffer, steht_fest: bool, genannt: bool, hat_text: bool) -> str:
    """Sicher ist nur, wer über ein Buch der Bibliothek belegt ist oder als einziger dieses Namens viele Punkte hat."""
    if steht_fest or t.belegt or genannt or (t.punkte >= HOCH and t.einziger):
        return "hoch"
    if t.punkte < HOCH and hat_text:
        return "niedrig"                                     # ein Lebenslauf, der kein einziges Buch nennt
    return "mittel" if t.punkte >= MITTEL else "niedrig"


def _nennt_ein_buch(frage: Autorfrage, text: str) -> bool:
    klein = text.lower()
    ziffern = klein.replace("-", "").replace(" ", "")
    return any(t.lower() in klein for t in frage.titel if len(t) > 3) or any(f.lower() in ziffern for i in frage.isbns for f in nummern.formen(i))


async def _aus_wikidata(lauf: _Lauf, t: _Treffer, steht_fest: bool) -> Autorangaben:
    e = t.eintrag
    sprache = next(iter(e.artikel), "")
    artikel = (await lauf.oder_nichts(wiki.artikel(sprache, e.artikel[sprache])) or "") if sprache else ""
    text = wiki.lebenslauf(artikel) if artikel else ""
    namen = {n: b.name for n, b in t.bezuege.items() if b.name}
    werke = [Werk(titel=namen[n], wikidata_id=n) for n in e.texte("P800")[:WERKE_HOECHSTENS] if n in namen]
    verweise = {art: e.erster(p) for art, p in (("gnd", "P227"), ("viaf", "P214"), ("isni", "P213"), ("orcid", "P496")) if e.erster(p)}
    genannt = _nennt_ein_buch(lauf.frage, f"{artikel} {e.beschreibung}")
    return Autorangaben(name=e.name, wikidata_id=e.id, biography=text, beschreibung=e.beschreibung, birth_year=e.jahr("P569"), death_year=e.jahr("P570"),
                        nationality=next((namen[n] for n in e.texte("P27") if n in namen), ""), photo_url=wiki.bild(e.erster("P18")),
                        wikipedia_url=wiki.adresse(sprache, e.artikel[sprache]) if sprache else "", website=e.erster("P856"), score=t.punkte, quelle="wikidata", verweise=verweise,
                        konfidenz=_stufe(t, steht_fest, genannt, bool(text)), werke=werke)


def _beschreibung(p: gnd.Person) -> str:
    """Beruf und was die Normdatei sonst über einen Menschen sagt."""
    return "; ".join(t for t in (", ".join(p.berufe), p.biografie) if t)


def _aus_normdatei(p: gnd.Person, steht_fest: bool) -> Autorangaben:
    verweise = {"gnd": p.gnd, **{a: k for a, k in p.verweise.items() if a in ("viaf", "isni", "orcid")}}
    return Autorangaben(name=p.name, wikidata_id=p.verweise.get("wikidata", ""), beschreibung=_beschreibung(p), birth_year=p.geboren, death_year=p.gestorben, nationality=p.land, wikipedia_url=p.wikipedia,
                        website=p.website, score=PUNKTE_NORMDATEI if steht_fest else MITTEL, konfidenz="hoch" if steht_fest else "mittel", quelle="gnd", verweise=verweise)


def _vereint(lexikon: Autorangaben | None, norm: Autorangaben | None) -> Autorangaben | None:
    """Das Lexikon geht vor, die Normdatei füllt die Lücken; die Herkunft steht je Feld dabei."""
    if lexikon is None or norm is None:
        eine = lexikon or norm
        return eine and eine.model_copy(update={"herkunft": _herkunft(eine, eine.quelle)})
    luecken = {f: getattr(norm, f) for f in Autorangaben.model_fields if f not in ("konfidenz", "score", "quelle", "herkunft", "verweise") and not getattr(lexikon, f) and getattr(norm, f)}
    vereint = lexikon.model_copy(update={**luecken, "verweise": {**norm.verweise, **lexikon.verweise}})
    return vereint.model_copy(update={"herkunft": _herkunft(lexikon, "wikidata") | dict.fromkeys(luecken, "gnd")})


def _herkunft(a: Autorangaben, quelle: str) -> dict[str, str]:
    ohne = ("konfidenz", "score", "quelle", "herkunft")
    return {f: quelle for f in Autorangaben.model_fields if f not in ohne and getattr(a, f)}


def suchname(name: str) -> str:
    """"Beispiel, Erika (Hrsg.)" -> "Erika Beispiel", "E.T.A. Muster" -> "E. T. A. Muster"."""
    ohne = re.sub(r"\s*\(?\b(?:Hrsg|Hg|Herausgeber(?:in)?|Ed|Eds)\b\.?\)?\s*$", "", (name or "").strip(" ;"), flags=re.IGNORECASE)
    return re.sub(r"\.(?=\w)", ". ", natuerlich(ohne))


async def suche(frage: Autorfrage) -> Autorauskunft:
    """Angaben zu einem Autor aus Normdatei und Lexikon. Antwortet eine Quelle nicht, steht das in den Hinweisen."""
    if not GND.aktiv and not WIKIPEDIA.aktiv:
        return Autorauskunft(hinweise=[f"{WIKIPEDIA.name} und {GND.name} sind abgeschaltet"])
    lauf = _Lauf(frage.model_copy(update={"name": suchname(frage.name), "isbns": [i for i in frage.isbns if nummern.sauber(i)]}))
    if len(lauf.frage.name) < 2:
        return Autorauskunft()
    person, steht_fest = await _normperson(lauf)
    treffer = await _bester(lauf, person, steht_fest) if WIKIPEDIA.aktiv else None
    lexikon = await _aus_wikidata(lauf, treffer, steht_fest) if treffer else None
    norm = _aus_normdatei(person, steht_fest) if person else None
    return Autorauskunft(angaben=_vereint(lexikon, norm), hinweise=list(dict.fromkeys(f.grund for f in lauf.fehler)), ruht=any(ruhig(f) for f in lauf.fehler))
