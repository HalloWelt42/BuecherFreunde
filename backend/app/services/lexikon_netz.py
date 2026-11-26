"""Das öffentliche Lexikon im Netz für alle ohne Nachschlag: Titel und Volltext in einer Anfrage, der Artikel als lesbares HTML,
das erste Bild des Artikels. Gefragt wird nur über den gemeinsamen Abruf der Quellen (Takt aller Wikis zusammen, Vorrat, Pausen),
mit der Einstellung des Lexikons (`WIKIPEDIA_ENABLED`); was einmal geholt ist, kommt aus dem Vorrat."""

from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import quote, unquote

from bs4 import BeautifulSoup, Tag

from backend.app.quellen import regeln
from backend.app.quellen import stand as quellenstand
from backend.app.quellen.abruf import Frage, abruf, hole
from backend.app.quellen.fehler import AnfrageFalsch, QuelleFehler
from backend.app.quellen.wiki import _pruefe as pruefe_wiki
from backend.app.services.hausdienst import DienstFehler, Guete
from backend.app.services.lexikon import Abschnitt, Nachschlagartikel, Nachschlagtreffer, klartext, ordnen, zum_lesen

SPRACHE = "de"
RECHNER = f"https://{SPRACHE}.wikipedia.org"
API = f"{RECHNER}/w/api.php"
BUCH = f"wikipedia_{SPRACHE}"
NAME = "Wikipedia (Deutsch)"                       # Herkunft, die die Lizenz des Lexikons zu nennen verlangt
BILDER = ("upload.wikimedia.org", "thumb.wikimedia.org")    # Rechner der Bilder; der Weg zum Bild nennt ihn zuerst
BILD_HOECHSTENS = 5_000_000
BILD_WEG = re.compile(r"^(upload|thumb)\.wikimedia\.org/wikipedia/[\w%.()',!~*/-]{1,600}$")
WEG_KLASSEN = frozenset({"reference", "mw-editsection", "navbox", "navbox-styles", "reflist", "references", "mw-references-wrap", "noprint",
                         "metadata", "mw-empty-elt", "toc", "mw-cite-backlink", "sistersitebox", "gallery", "thumb"})
ANHANG = {"literatur", "weblinks", "einzelnachweise", "quellen", "anmerkungen", "siehe auch", "belege", "fußnoten", "audiodateien", "bildergalerie", "galerie"}
TITEL_HOECHSTENS, TREFFER_HOECHSTENS = 8, 12
ZEICHEN_IM_WEG = "/%()',!~*-._"                     # bleiben in der Adresse des Bildes, wie das Lexikon sie schreibt
ARTEN = ((b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG", "image/png"), (b"GIF8", "image/gif"), (b"RIFF", "image/webp"))


def adresse(titel: str, anker: str = "") -> str:
    return f"{RECHNER}/wiki/{quote(titel.replace(' ', '_'), safe='()_,:-')}" + (f"#{quote(anker, safe='_.-')}" if anker else "")


def _als_dienstfehler(f: QuelleFehler) -> DienstFehler:
    return DienstFehler(f.grund, 404 if isinstance(f, AnfrageFalsch) else 503)


def _pruefe(antwort: dict[str, Any]) -> None:
    if (antwort.get("error") or {}).get("code") != "missingtitle":     # fehlt der Artikel, ist das "nichts gefunden"
        pruefe_wiki(antwort)


# -- Suche ---------------------------------------------------------------------------------------------------------------
def _treffer(antwort: dict[str, Any]) -> dict[str, Any]:
    q = antwort.get("query") or {}
    return {"titel": [t["title"] for t in q.get("prefixsearch", [])],
            "treffer": [{"titel": t["title"], "auszug": klartext(t.get("snippet", ""))} for t in q.get("search", [])]}


def suchfrage(frage: str) -> Frage:
    """Titel, die so beginnen, und die Suche im Text in einer Anfrage; ein schneller Blick nur auf Titel braucht keine eigene."""
    felder = (("action", "query"), ("list", "prefixsearch|search"), ("pssearch", frage[:200]), ("pslimit", str(TITEL_HOECHSTENS)), ("psnamespace", "0"),
              ("srsearch", frage[:300]), ("srlimit", str(TREFFER_HOECHSTENS)), ("srnamespace", "0"), ("srprop", "snippet"), ("srinfo", ""),
              ("format", "json"), ("formatversion", "2"))
    return Frage(API, felder, pruefe=pruefe_wiki, verdichte=_treffer, ist_leer=lambda w: not _treffer(w)["titel"] and not _treffer(w)["treffer"])


# -- Artikel -------------------------------------------------------------------------------------------------------------
def _verweis(href: str) -> str | None:
    """Nur Verweise auf Artikel; keine Dateien, Kategorien, Hilfeseiten, fremden Rechner."""
    m = re.match(r"^/wiki/([^#?]+)", href)
    if not m:
        return None
    titel = unquote(m.group(1)).replace("_", " ")
    return None if ":" in titel else titel


def _ohne_anhang(inhalt: Tag) -> None:
    """Literatur, Weblinks, Einzelnachweise und Ähnliches fallen samt ihrem Abschnitt weg."""
    weg = False
    for kind in list(inhalt.children):
        if not isinstance(kind, Tag):
            continue
        kopf = kind if kind.name == "h2" else kind.find("h2") if "mw-heading2" in (kind.get("class") or []) else None
        if kopf is not None:
            weg = kopf.get_text(" ", strip=True).casefold() in ANHANG
        if weg:
            kind.decompose()


def _erstes_bild(inhalt: Tag) -> str:
    for img in inhalt.select(".infobox img, figure img, .mw-file-element"):
        weg = img.get("src", "").removeprefix("//").partition("?")[0]
        if weg.startswith(BILDER) and int(img.get("width") or 0) >= 100 and BILD_WEG.fullmatch(weg):
            return f"/api/nachschlag/bild/{BUCH}/{weg}"
    return ""


def _lesbar(antwort: dict[str, Any]) -> dict[str, Any]:
    p = antwort["parse"]
    doc = BeautifulSoup(p.get("text") or "", "html.parser")
    inhalt = doc.find(class_="mw-parser-output") or doc
    _ohne_anhang(inhalt)
    bild = _erstes_bild(inhalt)
    abschnitte = [{"anker": s["anchor"], "titel": klartext(s.get("line", ""))} for s in p.get("sections", [])
                  if str(s.get("level")) == "2" and klartext(s.get("line", "")).casefold() not in ANHANG]
    return {"titel": p["title"], "html": zum_lesen(str(inhalt), _verweis, WEG_KLASSEN), "bild": bild, "abschnitte": abschnitte}


def artikelfrage(titel: str) -> Frage:
    felder = (("action", "parse"), ("page", titel[:300]), ("prop", "text|sections"), ("redirects", "1"), ("disableeditsection", "1"), ("disabletoc", "1"),
              ("disablelimitreport", "1"), ("format", "json"), ("formatversion", "2"))
    return Frage(API, felder, pruefe=_pruefe, ist_leer=lambda w: "parse" not in w, verdichte=_lesbar)


def _art(inhalt: bytes) -> str:
    return next((art for anfang, art in ARTEN if inhalt.startswith(anfang)), "")


class Netzlexikon:
    art = "netz"
    adresse = RECHNER

    async def vorwaermen(self) -> None:
        return None

    async def stand(self) -> tuple[Guete | Literal["aus"], str]:
        """Der gemerkte Stand der Quelle Lexikon, wie beim Nachschlagen erlebt. Gefragt wird sie dafür nie: wie bei allen
        Quellen fragt erst "Neu prüfen" in den Einstellungen (die Verbindungen werden alle paar Minuten geprüft)."""
        s = await quellenstand.einer(regeln.WIKIPEDIA.kennung)
        return s.stand, f"Öffentliches Lexikon im Netz: {s.wort}"

    async def schliessen(self) -> None:
        return None

    async def suche(self, frage: str, anzahl: int, sitzung: str, nur_titel: bool) -> list[Nachschlagtreffer]:
        try:
            d = await hole(regeln.WIKIPEDIA, suchfrage(frage)) or {"titel": [], "treffer": []}
        except QuelleFehler as f:
            raise _als_dienstfehler(f) from f
        aus: dict[str, Nachschlagtreffer] = {}
        for titel in d["titel"]:
            aus.setdefault(titel, Nachschlagtreffer(buch=BUCH, buchtitel=NAME, pfad=titel, titel=titel))
        for t in d["treffer"]:
            aus.setdefault(t["titel"], Nachschlagtreffer(buch=BUCH, buchtitel=NAME, pfad=t["titel"], titel=t["titel"])).auszug = t["auszug"]
        return ordnen(frage, list(aus.values()))[:anzahl]

    async def artikel(self, buch: str, pfad: str, frage: str, anker: str, sitzung: str) -> Nachschlagartikel:
        try:
            a = await hole(regeln.WIKIPEDIA, artikelfrage(pfad))
        except QuelleFehler as f:
            raise _als_dienstfehler(f) from f
        if a is None:
            raise DienstFehler("Diesen Artikel gibt es im Lexikon nicht", 404)
        return Nachschlagartikel(buch=BUCH, buchtitel=NAME, pfad=a["titel"], titel=a["titel"], html=a["html"], anker=anker, bild=a["bild"],
                                 abschnitte=[Abschnitt(**x) for x in a["abschnitte"]], adresse=adresse(a["titel"], anker))

    async def bild(self, buch: str, pfad: str) -> tuple[bytes, str]:
        if buch != BUCH or not BILD_WEG.fullmatch(pfad):
            raise DienstFehler("Das Bild gibt es nicht", 404)
        try:
            inhalt = await abruf().lade(regeln.WIKIPEDIA_BILDER, f"https://{quote(pfad, safe=ZEICHEN_IM_WEG)}", BILD_HOECHSTENS)
        except QuelleFehler as f:
            raise _als_dienstfehler(f) from f
        art = _art(inhalt)
        if not art:
            raise DienstFehler("Das ist kein Bild", 404)
        return inhalt, art
