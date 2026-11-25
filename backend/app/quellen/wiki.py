"""Wikidata und Wikipedia: suchen, Einträge lesen, Artikel lesen. Je Aufruf eine Anfrage, mehrere Einträge auf einmal, und aus
jedem Eintrag bleibt nur, was die App braucht."""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, Field

from backend.app.quellen import regeln
from backend.app.quellen.abruf import Frage, hole
from backend.app.quellen.fehler import AnfrageFalsch, BitteWarten

WIKIDATA = "https://www.wikidata.org/w/api.php"
EINTRAEGE_HOECHSTENS = 50
SPRACHEN = ("de", "en")
# Autor, Autor als Text, Verlag, Erschienen, Seiten, Sprache, Gattung, Thema, Art, ISBN, Bild, Website, geboren, gestorben, Land,
# Beruf, Werke, Normdateien (GND, VIAF, ISNI, ORCID), Titel, Untertitel, Ausgabe von
EIGENSCHAFTEN = ("P50", "P2093", "P123", "P577", "P1104", "P407", "P136", "P921", "P31", "P212", "P957", "P18", "P856", "P569", "P570", "P27", "P106", "P800", "P227", "P214", "P213", "P496",
                 "P1476", "P1680", "P629")
JAHR_GENAU = 9                      # Genauigkeit eines Datums, ab der das Jahr stimmt
_UEBERGEHEN = {"literatur", "weblinks", "einzelnachweise", "quellen", "anmerkungen", "siehe auch", "werke", "bibliografie", "bibliographie", "diskografie", "filmografie", "filmographie",
               "references", "external links", "bibliography", "works", "further reading", "notes", "selected works", "publications", "discography", "filmography", "see also"}
_INHALT = {"inhalt", "handlung", "zusammenfassung", "überblick", "plot", "synopsis", "plot summary"}
ABSCHNITT_AB = 20                   # kürzere Abschnitte sind meist nur Verweise


class Eintrag(BaseModel):
    """Ein Wikidata-Eintrag, auf das Nötige gekürzt."""

    id: str
    name: str = ""
    beschreibung: str = ""
    auch: list[str] = Field(default_factory=list)
    artikel: dict[str, str] = Field(default_factory=dict)               # Sprache -> Titel des Artikels
    werte: dict[str, list[Any]] = Field(default_factory=dict)

    def texte(self, eigenschaft: str) -> list[str]:
        return [w for w in self.werte.get(eigenschaft, []) if isinstance(w, str)]

    def erster(self, eigenschaft: str) -> str:
        return next(iter(self.texte(eigenschaft)), "")

    def jahr(self, eigenschaft: str) -> int | None:
        return next((w for w in self.werte.get(eigenschaft, []) if isinstance(w, int)), None)


def _pruefe(antwort: dict[str, Any]) -> None:
    """Fehler kommen hier mit Status 200 im Text."""
    fehler = antwort.get("error")
    if not fehler:
        return
    if fehler.get("code") in ("maxlag", "ratelimited", "readonly"):
        raise BitteWarten(30, "ist gerade überlastet")
    raise AnfrageFalsch(f"{regeln.WIKIPEDIA.name} meldet {fehler.get('code', 'einen Fehler')}")


def _wert(aussage: dict[str, Any]) -> Any:
    """Der Wert einer Aussage: Text, Kennung eines Eintrags oder Jahr."""
    daten = (aussage.get("mainsnak") or {}).get("datavalue") or {}
    wert, art = daten.get("value"), daten.get("type")
    if art == "wikibase-entityid":
        return wert.get("id", "")
    if art == "quantity":
        return wert.get("amount", "").lstrip("+")
    if art == "monolingualtext":
        return wert.get("text", "")
    if art == "time":
        treffer = re.match(r"([+-]\d+)-", wert.get("time", ""))
        return int(treffer.group(1)) if treffer and wert.get("precision", 0) >= JAHR_GENAU else None
    return wert if art == "string" else None


def _werte(aussagen: list[dict[str, Any]]) -> list[Any]:
    """Ohne verworfene Aussagen; bevorzugte zuerst."""
    gueltig = [a for a in aussagen if a.get("rank") != "deprecated"]
    gueltig.sort(key=lambda a: a.get("rank") != "preferred")
    return [w for a in gueltig if (w := _wert(a)) not in (None, "")]


def _in_sprache(texte: dict[str, Any]) -> str:
    return next((unicodedata.normalize("NFC", texte[s]["value"]) for s in (*SPRACHEN, "mul") if s in texte), "")


def _verdichten(antwort: dict[str, Any]) -> dict[str, Any]:
    aus = {}
    for nummer, e in antwort["entities"].items():
        if "missing" in e:
            continue
        auch = [a["value"] for s in SPRACHEN for a in (e.get("aliases") or {}).get(s, [])]
        artikel = {s: e["sitelinks"][f"{s}wiki"]["title"] for s in SPRACHEN if f"{s}wiki" in (e.get("sitelinks") or {})}
        werte = {p: w for p in EIGENSCHAFTEN if (w := _werte((e.get("claims") or {}).get(p, [])))}
        aus[nummer] = Eintrag(id=nummer, name=_in_sprache(e.get("labels") or {}), beschreibung=_in_sprache(e.get("descriptions") or {}), auch=auch, artikel=artikel, werte=werte).model_dump(exclude_defaults=True)
    return aus


async def suche(anfrage: str, hoechstens: int = 8) -> dict[str, int]:
    """Nummern der Einträge, bester zuerst, mit der Zahl ihrer Artikel (Bekanntheit)."""
    felder = (("action", "query"), ("generator", "search"), ("gsrsearch", anfrage), ("gsrnamespace", "0"), ("gsrlimit", str(hoechstens)), ("prop", "pageprops"), ("ppprop", "wb-sitelinks"),
              ("format", "json"), ("formatversion", "2"))
    frage = Frage(WIKIDATA, felder, pruefe=_pruefe, ist_leer=lambda w: not (w.get("query") or {}).get("pages"),
                  verdichte=lambda w: {s["title"]: int((s.get("pageprops") or {}).get("wb-sitelinks", 0)) for s in sorted(w["query"]["pages"], key=lambda s: s.get("index", 0))})
    return await hole(regeln.WIKIPEDIA, frage) or {}


async def eintraege(nummern: list[str], probe: bool = False) -> dict[str, Eintrag]:
    gefragt = [n for n in dict.fromkeys(nummern) if re.fullmatch(r"Q\d+", n)][:EINTRAEGE_HOECHSTENS]
    if not gefragt:
        return {}
    felder = (("action", "wbgetentities"), ("ids", "|".join(gefragt)), ("props", "claims|labels|descriptions|aliases|sitelinks"), ("languages", "|".join((*SPRACHEN, "mul"))),
              ("sitefilter", "|".join(f"{s}wiki" for s in SPRACHEN)), ("format", "json"))
    daten = await hole(regeln.WIKIPEDIA, Frage(WIKIDATA, felder, pruefe=_pruefe, verdichte=_verdichten), probe=probe) or {}
    return {n: Eintrag(**daten[n]) for n in gefragt if n in daten}


async def namen(nummern: list[str]) -> dict[str, str]:
    """Nur die Namen zu Nummern, in einer Anfrage."""
    gefragt = [n for n in dict.fromkeys(nummern) if re.fullmatch(r"Q\d+", n)][:EINTRAEGE_HOECHSTENS]
    if not gefragt:
        return {}
    felder = (("action", "wbgetentities"), ("ids", "|".join(gefragt)), ("props", "labels"), ("languages", "|".join((*SPRACHEN, "mul"))), ("format", "json"))
    frage = Frage(WIKIDATA, felder, pruefe=_pruefe, verdichte=lambda w: {n: _in_sprache(e.get("labels") or {}) for n, e in w["entities"].items() if "missing" not in e})
    daten = await hole(regeln.WIKIPEDIA, frage) or {}
    return {n: daten[n] for n in gefragt if daten.get(n)}


# -- Artikel -----------------------------------------------------------------------------------------------------------
def adresse(sprache: str, titel: str) -> str:
    return f"https://{sprache}.wikipedia.org/wiki/{titel.replace(' ', '_')}"


async def artikel(sprache: str, titel: str) -> str:
    """Der Text eines Artikels mit "== Überschriften ==", leer wenn es ihn nicht gibt."""
    felder = (("action", "query"), ("prop", "extracts"), ("explaintext", "1"), ("exsectionformat", "wiki"), ("redirects", "1"), ("titles", titel), ("format", "json"), ("formatversion", "2"))
    frage = Frage(f"https://{sprache}.wikipedia.org/w/api.php", felder, pruefe=_pruefe, ist_leer=lambda w: not w["query"]["pages"][0].get("extract"), verdichte=lambda w: w["query"]["pages"][0]["extract"])
    return await hole(regeln.WIKIPEDIA, frage) or ""


def abschnitte(text: str) -> list[tuple[int, str, str]]:
    """(Ebene, Überschrift, Text); die Einleitung hat Ebene 1 und keine Überschrift."""
    aus: list[tuple[int, str, str]] = []
    ebene, titel, ab = 1, "", 0
    for treffer in re.finditer(r"^(={2,5})\s*(.+?)\s*\1\s*$", text, re.MULTILINE):
        aus.append((ebene, titel, text[ab:treffer.start()].strip()))
        ebene, titel, ab = len(treffer.group(1)), treffer.group(2), treffer.end()
    return [*aus, (ebene, titel, text[ab:].strip())]


def lebenslauf(text: str) -> str:
    """Einleitung und inhaltliche Abschnitte als Markdown, ohne Literatur, Weblinks und Werklisten."""
    teile: list[str] = []
    uebergangen = False
    for ebene, titel, inhalt in abschnitte(text):
        if ebene == 2:
            uebergangen = titel.strip().lower() in _UEBERGEHEN
        if uebergangen or ebene > 3 or titel.strip().lower() in _UEBERGEHEN or not inhalt or (titel and len(inhalt) <= ABSCHNITT_AB):
            continue
        teile.append(f"{'#' * ebene} {titel}\n\n{inhalt}" if titel else inhalt)
    return "\n\n".join(teile)


def buchtext(text: str) -> str:
    """Für ein Buch: Einleitung und der Abschnitt über den Inhalt."""
    alle = abschnitte(text)
    einleitung = next((i for e, t, i in alle if e == 1), "")
    inhalt = next((i for e, t, i in alle if e == 2 and t.strip().lower() in _INHALT and i), "")
    return "\n\n".join(t for t in (einleitung, inhalt) if t)


def bild(datei: str) -> str:
    """Adresse eines Bildes in einer Größe, die der Dienst fertig vorhält."""
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(datei.replace(' ', '_'))}?width=500" if datei else ""
