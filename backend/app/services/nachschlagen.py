"""Nachschlagen in Lexika und Handbüchern: Treffer, ein Artikel zum Lesen im kleinen Fenster und der Verweis an die Stelle in der
Anwendung. Angeschlossen ist Nachschlag (`NACHSCHLAG_URL`); ohne ihn fehlt die Fähigkeit."""

from __future__ import annotations

import asyncio
import re
from urllib.parse import quote, unquote, urlencode

from bs4 import BeautifulSoup, NavigableString, Tag
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.services.hausdienst import DienstFehler, Hausdienst

dienst = Hausdienst("Nachschlag", lambda: settings.nachschlag_url)
LEXIKON = "wikipedia_de_all"                       # bei gleichem Titel zuerst
ERLAUBT = {"p", "h2", "h3", "h4", "ul", "ol", "li", "b", "strong", "i", "em", "sub", "sup", "code", "pre", "blockquote", "dl", "dt", "dd", "br"}
WEG = ["script", "style", "table", "figure", "img", "svg", "math", "video", "audio", "iframe", "form", "button", "input", "nav"]
KENNUNG = re.compile(r"[\w()., -]{1,120}")


class Nachschlagtreffer(BaseModel):
    buch: str
    buchtitel: str
    pfad: str
    titel: str
    auszug: str = ""
    anker: str = ""
    bild: str = ""


class Abschnitt(BaseModel):
    anker: str
    titel: str


class Nachschlagartikel(BaseModel):
    buch: str
    buchtitel: str
    pfad: str
    titel: str
    html: str
    anker: str = ""
    bild: str = ""
    abschnitte: list[Abschnitt] = []
    adresse: str                                   # dieselbe Seite in der Anwendung


_buecher: dict[str, str] = {}


async def _titel_der_buecher(sitzung: str) -> dict[str, str]:
    if not _buecher:
        d = (await dienst.hole("GET", "/api/v1/buecher", sitzung)).json()
        _buecher.update({b["kennung"]: b["titel"] for b in d.get("buecher", [])})
    return _buecher


def adresse(buch: str, pfad: str, frage: str = "", anker: str = "") -> str:
    zusatz = urlencode({k: w for k, w in (("frage", frage), ("anker", anker)) if w})
    return f"{dienst.adresse}/lesen/{quote(buch, safe='')}/{quote(pfad)}" + (f"?{zusatz}" if zusatz else "")


def _bild(verweis: str) -> str:
    m = re.match(r"/api/v1/inhalt/medien/([^/]+)/(.+)$", verweis or "")
    return f"/api/nachschlag/bild/{m.group(1)}/{m.group(2)}" if m else ""


def _klartext(auszug: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(auszug or "", "html.parser").get_text()).strip()


def _ordnen(frage: str, treffer: list[Nachschlagtreffer]) -> list[Nachschlagtreffer]:
    """Genauer Titel zuerst, dann Titel, die so beginnen, darin das große Lexikon; sonst bleibt die Reihenfolge der Suche."""
    f = frage.casefold().strip()

    def rang(nr_t: tuple[int, Nachschlagtreffer]) -> tuple:
        nr, t = nr_t
        titel = t.titel.casefold()
        return (0 if titel == f else 1 if titel.startswith(f) else 2, 0 if t.buch.startswith(LEXIKON) else 1, nr)

    return [t for _, t in sorted(enumerate(treffer), key=rang)]


async def suche(frage: str, anzahl: int = 12, sitzung: str = "") -> list[Nachschlagtreffer]:
    titel = await _titel_der_buecher(sitzung)
    vorschlaege, gefunden = await asyncio.gather(
        dienst.hole("GET", "/api/v1/vorschlaege", sitzung, params={"anfang": frage[:200], "anzahl": 8}),
        dienst.hole("GET", "/api/v1/suche", sitzung, params={"frage": frage[:400], "anzahl": 12, "wege": "index"}))
    aus: dict[tuple[str, str], Nachschlagtreffer] = {}
    for v in vorschlaege.json():
        pfad, _, anker = (v.get("weiterleitung") or v["pfad"]).partition("#")
        aus.setdefault((v["buch"], pfad), Nachschlagtreffer(buch=v["buch"], buchtitel=titel.get(v["buch"], ""), pfad=pfad, titel=v["titel"],
                                                            auszug=_klartext(v.get("kurztext", "")), anker=anker, bild=_bild(v.get("bild", ""))))
    for t in gefunden.json()["treffer"]:
        neu = Nachschlagtreffer(buch=t["buch"], buchtitel=titel.get(t["buch"], ""), pfad=t["pfad"], titel=t["titel"],
                                auszug=_klartext(t.get("ausschnitt", "")), anker=t.get("anker", ""), bild=_bild(t.get("bild", "")))
        vorhanden = aus.setdefault((t["buch"], t["pfad"]), neu)
        vorhanden.auszug = vorhanden.auszug or neu.auszug
    return _ordnen(frage, list(aus.values()))[:anzahl]


async def artikel(buch: str, pfad: str, frage: str = "", anker: str = "", sitzung: str = "") -> Nachschlagartikel:
    a = (await dienst.hole("GET", f"/api/v1/artikel/{quote(buch, safe='')}/{quote(pfad)}", sitzung)).json()
    titel = await _titel_der_buecher(sitzung)
    stelle = anker or a.get("anker", "")
    return Nachschlagartikel(buch=a["buch"], buchtitel=titel.get(a["buch"], ""), pfad=a["pfad"], titel=a["titel"], anker=stelle,
                             html=zum_lesen(a.get("html") or "", a["buch"]) or f"<p>{_klartext(a.get('einleitung', ''))}</p>", bild=_bild(a.get("bild", "")),
                             abschnitte=[Abschnitt(anker=x["anker"], titel=x["titel"]) for x in a.get("abschnitte", []) if x.get("ebene") == 2],
                             adresse=adresse(a["buch"], a["pfad"], frage, stelle))


def zum_lesen(html: str, buch: str) -> str:
    """Nur Text, Überschriften, Listen und Verweise im selben Buch; alles andere fällt weg, kein fremdes HTML kommt durch."""
    quelle = BeautifulSoup(html, "html.parser")
    for t in quelle.find_all(WEG):
        t.decompose()
    ziel = BeautifulSoup("", "html.parser")
    _uebernehmen(quelle, ziel, ziel, buch)
    return str(ziel)


def _uebernehmen(von: Tag, nach: Tag, doc: BeautifulSoup, buch: str) -> None:
    for kind in list(von.children):
        if isinstance(kind, Tag):
            neu = _neues(kind, doc, buch)
            _uebernehmen(kind, nach if neu is None else neu, doc, buch)
            if neu is not None:
                nach.append(neu)
        elif type(kind) is NavigableString:                # keine Kommentare, keine Anweisungen
            nach.append(NavigableString(str(kind)))


def _neues(alt: Tag, doc: BeautifulSoup, buch: str) -> Tag | None:
    if alt.name == "a":
        m = re.match(rf"/lesen/{re.escape(buch)}/([^#?]+)", alt.get("href", ""))
        return doc.new_tag("a", attrs={"href": "#", "data-pfad": unquote(m.group(1))}) if m else None
    if alt.name not in ERLAUBT:
        return None
    neu = doc.new_tag(alt.name)
    if alt.name in ("h2", "h3", "h4") and KENNUNG.fullmatch(alt.get("id") or ""):
        neu["id"] = "ns-" + alt["id"]
    return neu


async def bild(buch: str, pfad: str) -> tuple[bytes, str]:
    r = await dienst.hole("GET", f"/api/v1/inhalt/medien/{quote(buch, safe='')}/{quote(pfad)}")
    art = r.headers.get("content-type", "").split(";")[0]
    if not art.startswith("image/") or art == "image/svg+xml":
        raise DienstFehler("Das ist kein Bild", 404)
    return r.content, art
