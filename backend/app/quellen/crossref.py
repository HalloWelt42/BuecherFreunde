"""Crossref: alles mit DOI, also Fachartikel, Tagungsbände und viele Fachbücher, mit Zeitschrift, Heft, Seiten und oft einer
Zusammenfassung. Ohne Anmeldung, Angaben frei."""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import quote

from backend.app.quellen import isbn as nummern
from backend.app.quellen import regeln
from backend.app.quellen.abgleich import bester, suchbar
from backend.app.quellen.abruf import Frage, hole
from backend.app.quellen.modelle import Angaben, Buchfrage
from backend.app.quellen.sprache import kuerzel

_AUSWAHL = ("select", "DOI,type,title,subtitle,author,editor,publisher,issued,ISBN,ISSN,container-title,abstract,page,volume,issue,URL")
_BUCHARTEN = ("book", "monograph", "edited-book", "reference-book")
_FELDER = ("DOI", "type", "title", "subtitle", "author", "editor", "publisher", "issued", "ISBN", "ISSN", "container-title", "abstract", "page", "volume", "issue", "URL", "language")
_ROHFELDER = {"type": "art", "container-title": "zeitschrift", "volume": "band", "issue": "heft", "page": "seitenbereich", "ISSN": "issn", "URL": "verweis"}
_DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"<>{}|\\^`\[\]]+", re.IGNORECASE)
TITEL_HOECHSTENS = 5
DOI_IM_TEXT = 6000                  # so viel vom Anfang eines Textes wird nach einer DOI durchsucht


def doi_aus_text(text: str) -> str:
    """Die erste DOI am Anfang eines Textes, ohne angehängte Satzzeichen; die eines Kapitels zählt als die des Buchs."""
    treffer = _DOI.search((text or "")[:DOI_IM_TEXT])
    if not treffer:
        return ""
    doi = treffer.group().rstrip(".,;:'")
    while doi.endswith(")") and doi.count("(") < doi.count(")"):
        doi = doi[:-1].rstrip(".,;:")
    kapitel = re.fullmatch(r"(10\.\d{4,9}/97[89][\d-]+)_\d+", doi)
    return kapitel.group(1) if kapitel else doi


def _eins(wert: Any) -> str:
    text = wert[0] if isinstance(wert, list) and wert else wert
    return " ".join(unicodedata.normalize("NFC", re.sub(r"<[^>]+>", "", text)).split()) if isinstance(text, str) else ""


def _namen(personen: list[dict[str, Any]]) -> list[str]:
    roh = (" ".join(filter(None, (p.get("given"), p.get("family")))) or p.get("name", "") for p in personen)
    return list(dict.fromkeys(n for r in roh if (n := _eins(r))))


def _jahr(werk: dict[str, Any]) -> int | None:
    teile = ((werk.get("issued") or {}).get("date-parts") or [[None]])[0]
    return teile[0] if teile and isinstance(teile[0], int) else None


def _zusammenfassung(jats: str) -> str:
    """JATS-Auszeichnung zu Absätzen, ohne das Wort "Abstract" davor."""
    text = re.sub(r"</jats:p>|</jats:title>", "\n\n", jats or "")
    absaetze = (" ".join(re.sub(r"<[^>]+>", "", a).split()) for a in text.split("\n\n"))
    return "\n\n".join(a for a in absaetze if a and a.lower() not in ("abstract", "zusammenfassung"))


def deuten(werk: dict[str, Any]) -> Angaben | None:
    if not _eins(werk.get("title")):
        return None
    isbns = [n for n in (nummern.sauber(i) for i in werk.get("ISBN", [])) if n]
    roh = {name: werk[feld] if feld == "ISSN" else _eins(werk[feld]) for feld, name in _ROHFELDER.items() if werk.get(feld)}
    herausgeber = _namen(werk.get("editor", []))
    if herausgeber:
        roh["herausgeber"] = herausgeber
    return Angaben(quelle=regeln.CROSSREF.kennung, titel=_eins(werk["title"]), untertitel=_eins(werk.get("subtitle")), autoren=_namen(werk.get("author", [])) or herausgeber,
                   verlag=_eins(werk.get("publisher")), jahr=_jahr(werk), isbn=isbns[0] if isbns else "", isbns=isbns, doi=werk.get("DOI", ""), sprache=kuerzel(werk.get("language")),
                   beschreibung=_zusammenfassung(werk.get("abstract", "")), roh=roh)


class Crossref:
    regel = regeln.CROSSREF

    @staticmethod
    def _kurz(werk: dict[str, Any]) -> dict[str, Any]:
        return {k: werk[k] for k in _FELDER if werk.get(k)}

    def _einzeln(self, doi: str) -> Frage:
        return Frage(f"{self.regel.adresse}/works/{quote(doi, safe='/')}", verdichte=lambda w: self._kurz(w["message"]))

    async def _liste(self, felder: tuple[tuple[str, str], ...], hoechstens: int) -> list[Angaben]:
        frage = Frage(f"{self.regel.adresse}/works", (*felder, ("rows", str(hoechstens)), _AUSWAHL), ist_leer=lambda w: not w["message"]["items"],
                      verdichte=lambda w: [self._kurz(i) for i in w["message"]["items"]])
        return [a for w in await hole(self.regel, frage) or [] if (a := deuten(w))]

    async def nach_isbn(self, isbn: str) -> Angaben | None:
        formen = nummern.formen(isbn)
        if not formen:
            return None
        arten = ",".join(f"type:{a}" for a in _BUCHARTEN)
        treffer = next((a for a in await self._liste((("filter", f"isbn:{formen[0]},{arten}"),), 3) if any(nummern.gleich(n, isbn) for n in a.isbns)), None)
        return treffer and treffer.model_copy(update={"fund": "isbn"})

    async def nach_doi(self, doi: str) -> Angaben | None:
        werk = await hole(self.regel, self._einzeln(doi)) if doi else None
        fund = deuten(werk) if werk else None
        return fund and fund.model_copy(update={"fund": "doi"})

    async def nach_titel(self, frage: Buchfrage) -> Angaben | None:
        if not suchbar(frage.titel):
            return None
        suche = " ".join([frage.titel, *frage.autoren[:2]])[:300]
        return bester(frage, await self._liste((("query.bibliographic", suche),), TITEL_HOECHSTENS))

    async def probe(self) -> None:
        await hole(self.regel, self._einzeln("10.1007/978-3-658-05620-9"), probe=True)
