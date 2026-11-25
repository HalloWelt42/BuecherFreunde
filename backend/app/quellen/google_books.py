"""Google Books: gute Beschreibungen und Umschläge. Seit 2026 gibt es ohne eigenen Schlüssel keine Antworten mehr (die geteilte
Tagesmenge steht auf 0); der Schlüssel geht im Kopf mit, nie in der Adresse."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.core.config import settings
from backend.app.quellen import isbn as nummern
from backend.app.quellen import regeln
from backend.app.quellen.abgleich import bester, haupttitel, suchbar
from backend.app.quellen.abruf import Frage, hole
from backend.app.quellen.anschluss import OhneDoi
from backend.app.quellen.fehler import BitteWarten
from backend.app.quellen.modelle import Angaben, Buchfrage
from backend.app.quellen.sprache import kuerzel
from backend.app.quellen.versand import Rohantwort
from backend.app.services.html_utils import html_to_markdown

TREFFER_HOECHSTENS = 8
_OHNE_AUSSAGE = {"general"}
_ROHFELDER = {"publishedDate": "erscheinungsdatum", "readingModes": "lesemodi", "maturityRating": "altersfreigabe", "contentVersion": "inhaltsversion", "previewLink": "vorschau_link",
              "infoLink": "info_link", "canonicalVolumeLink": "google_books_link", "averageRating": "durchschnittsbewertung", "ratingsCount": "anzahl_bewertungen", "dimensions": "abmessungen"}


def _bis_mitternacht() -> float:
    """Die Tagesmenge beginnt um Mitternacht kalifornischer Zeit neu."""
    jetzt = datetime.now(timezone(timedelta(hours=-8)))
    return ((jetzt + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0) - jetzt).total_seconds()


def _abweisung(antwort: Rohantwort) -> BitteWarten | None:
    """429 wegen der Tagesmenge: bis morgen Ruhe."""
    if antwort.status not in (429, 403):
        return None
    try:
        fehler = json.loads(antwort.inhalt)["error"]
    except (ValueError, LookupError, TypeError):
        return None
    if "per day" not in fehler.get("message", "").lower() and "dailylimit" not in json.dumps(fehler).lower():
        return None
    return BitteWarten(_bis_mitternacht(), "die Tagesmenge des Schlüssels ist verbraucht")


def _jahr(datum: str) -> int | None:
    treffer = re.search(r"\b(\d{4})\b", datum or "")
    return int(treffer.group(1)) if treffer else None


def _kategorien(roh: list[str]) -> list[str]:
    """"Fiction / Romance / Historical" -> einzelne Wörter, ohne Nichtssagendes."""
    teile = [t.strip() for k in roh for t in k.split("/")]
    return list(dict.fromkeys(t for t in teile if len(t) > 1 and t.lower() not in _OHNE_AUSSAGE))


def _umschlag(bilder: dict[str, str]) -> str:
    """Das größte Bild, über https und ohne geknickte Ecke."""
    adresse = next((bilder[k] for k in ("extraLarge", "large", "medium", "thumbnail", "smallThumbnail") if bilder.get(k)), "")
    return re.sub(r"&edge=\w+", "", adresse.replace("http://", "https://"))


def _nummern(info: dict[str, Any]) -> list[str]:
    kennungen = {i.get("type", ""): i.get("identifier", "") for i in info.get("industryIdentifiers", [])}
    return [n for art in ("ISBN_13", "ISBN_10") if (n := nummern.sauber(kennungen.get(art, "")))]


def deuten(band: dict[str, Any]) -> Angaben | None:
    info = band.get("volumeInfo") or {}
    if not info.get("title"):
        return None
    isbns = _nummern(info)
    roh = {name: info[feld] for feld, name in _ROHFELDER.items() if info.get(feld)}
    if info.get("subtitle"):
        roh["untertitel"] = info["subtitle"]
    if info.get("industryIdentifiers"):
        roh["identifiers"] = {i.get("type", ""): i.get("identifier", "") for i in info["industryIdentifiers"]}
    return Angaben(quelle=regeln.GOOGLE_BOOKS.kennung, titel=info["title"], untertitel=info.get("subtitle", ""), autoren=info.get("authors", []), verlag=info.get("publisher", ""),
                   jahr=_jahr(info.get("publishedDate", "")), seiten=info.get("pageCount") or 0, isbn=isbns[0] if isbns else "", isbns=isbns, sprache=kuerzel(info.get("language")),
                   beschreibung=html_to_markdown(info.get("description", "")), kategorien=_kategorien(info.get("categories", [])), umschlag=_umschlag(info.get("imageLinks", {})), roh=roh)


class GoogleBooks(OhneDoi):
    regel = regeln.GOOGLE_BOOKS

    def _frage(self, suche: str, hoechstens: int) -> Frage:
        return Frage(f"{self.regel.adresse}/volumes", (("q", suche), ("maxResults", str(hoechstens)), ("printType", "books")), kopf=(("X-Goog-Api-Key", settings.google_books_api_key),), abweisung=_abweisung,
                     ist_leer=lambda w: not w.get("items"), verdichte=lambda w: [{"volumeInfo": {k: v for k, v in (i.get("volumeInfo") or {}).items() if k != "panelizationSummary"}} for i in w["items"]])

    async def _funde(self, suche: str, hoechstens: int, probe: bool = False) -> list[Angaben]:
        baende = await hole(self.regel, self._frage(suche, hoechstens), probe=probe) or []
        return [a for b in baende if (a := deuten(b))]

    async def nach_isbn(self, isbn: str) -> Angaben | None:
        """Die Suche liefert auch Ähnliches; nur ein Band mit genau dieser ISBN gilt."""
        formen = nummern.formen(isbn)
        if not formen:
            return None
        treffer = next((a for a in await self._funde(f"isbn:{formen[0]}", 3) if any(nummern.gleich(n, isbn) for n in a.isbns)), None)
        return treffer and treffer.model_copy(update={"fund": "isbn"})

    async def nach_titel(self, frage: Buchfrage) -> Angaben | None:
        titel = haupttitel(frage.titel).replace('"', " ").strip()
        if not suchbar(titel):
            return None
        suche = f'intitle:"{titel}"' + (f' inauthor:"{frage.autoren[0]}"' if frage.autoren else "")
        return bester(frage, await self._funde(suche, TREFFER_HOECHSTENS))

    async def probe(self) -> None:
        await self._funde("isbn:9783257229530", 1, probe=True)
