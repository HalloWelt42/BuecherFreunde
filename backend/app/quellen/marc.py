"""Bibliothekskataloge antworten in MARC 21 (XML). Hier wird daraus `Angaben`, für alle Kataloge gleich."""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Iterator

from backend.app.quellen import isbn as nummern
from backend.app.quellen import sachgruppen
from backend.app.quellen.abgleich import natuerlich
from backend.app.quellen.modelle import Angaben
from backend.app.quellen.sprache import kuerzel

_NS = {"s": "http://www.loc.gov/zing/srw/", "m": "http://www.loc.gov/MARC21/slim"}
_STEUER = re.compile("[\x80-\x9f  ]")        # Sortierzeichen um führende Artikel
_SEITEN = re.compile(r"(\d{1,5})\s*(?:S\b|Seiten|p\b|pages|Bl\b|Blätter)", re.IGNORECASE)
_VORSATZ = re.compile(r"^\([^)]*\)")                   # "(Produktform)Paperback": Handelsangabe, kein Schlagwort
_AUFBEREITUNG = ("Fiktionale Darstellung", "Belletristische Darstellung")
SCHLAGWORTE_HOECHSTENS = 8
AUTOR, HERAUSGEBER = {"aut", "cre"}, {"edt"}


class Satz:
    """Ein Datensatz mit seinen Feldern."""

    def __init__(self, element: ET.Element) -> None:
        self._e = element
        self.leader = element.findtext("m:leader", "", _NS) or ""

    @staticmethod
    def _text(t: str | None) -> str:
        return " ".join(unicodedata.normalize("NFC", _STEUER.sub("", t or "")).split())

    def steuerfeld(self, nummer: str) -> str:
        return self._e.findtext(f"m:controlfield[@tag='{nummer}']", "", _NS) or ""

    def felder(self, *nummern_: str) -> Iterator[ET.Element]:
        for f in self._e.iterfind("m:datafield", _NS):
            if f.get("tag") in nummern_:
                yield f

    def alle(self, feld: ET.Element, code: str) -> list[str]:
        return [t for s in feld.iterfind("m:subfield", _NS) if s.get("code") == code and (t := self._text(s.text))]

    def eins(self, feld: ET.Element, code: str) -> str:
        return next(iter(self.alle(feld, code)), "")

    def werte(self, nummer: str, code: str) -> list[str]:
        return [w for f in self.felder(nummer) for w in self.alle(f, code)]


def saetze(inhalt: bytes) -> list[Satz]:
    """Alle Datensätze einer Antwort. Wirft ValueError, wenn sie kein lesbares XML ist oder einen Fehler meldet."""
    try:
        wurzel = ET.fromstring(inhalt)
    except ET.ParseError as f:
        raise ValueError("kein XML") from f
    if wurzel.find(".//s:diagnostics", _NS) is not None and wurzel.find(".//s:records", _NS) is None:
        raise ValueError("Anfrage nicht verstanden")
    return [Satz(e) for e in wurzel.iterfind(".//m:record", _NS)]


def _nummern(s: Satz) -> list[str]:
    roh = [n for f in s.felder("020") for n in (*s.alle(f, "9"), *s.alle(f, "a"))]
    return list(dict.fromkeys(n for r in roh if (n := nummern.dreizehn(r) or nummern.sauber(r))))


def _personen(s: Satz) -> tuple[list[str], list[str], dict[str, str]]:
    """Autoren, Herausgeber, und je Name die Kennung in der Normdatei."""
    autoren: list[str] = []
    herausgeber: list[str] = []
    kennungen: dict[str, str] = {}
    for f in s.felder("100", "700"):
        name = natuerlich(s.eins(f, "a"))
        rollen = set(s.alle(f, "4"))
        if not name or s.eins(f, "t"):                   # mit Titel: Verweis auf ein anderes Werk
            continue
        gnd = next((k.removeprefix("(DE-588)") for k in s.alle(f, "0") if k.startswith("(DE-588)")), "")
        if gnd:
            kennungen[name] = gnd
        if rollen & AUTOR or (f.get("tag") == "100" and not rollen):
            autoren.append(name)
        elif rollen & HERAUSGEBER:
            herausgeber.append(name)
    return list(dict.fromkeys(autoren)), list(dict.fromkeys(herausgeber)), kennungen


def _titel(s: Satz) -> tuple[str, str]:
    f = next(s.felder("245"), None)
    if f is None:
        return "", ""
    haupt = s.eins(f, "a").strip(" /:;=")
    band, teil = (s.eins(f, c).strip(" /:;.=") for c in "np")
    unter = "" if s.eins(f, "b").startswith("=") else s.eins(f, "b").strip(" /:;.=")      # "=": Titel in anderer Sprache
    band = re.sub(r"^(?:Bd\.?|Band|Teil)?\s*(\d+)$", r"Band \1", band)
    return f"{haupt}, {band}" if band else haupt, " - ".join(t for t in (teil, unter) if t)


def _erschienen(s: Satz) -> tuple[str, int | None]:
    verlag, jahr = "", None
    for f in sorted(s.felder("264", "260"), key=lambda f: f.get("ind2") != "1"):
        verlag = verlag or s.eins(f, "b").strip(" ,;:")
        treffer = re.search(r"\d{4}", s.eins(f, "c"))
        jahr = jahr or (int(treffer.group()) if treffer else None)
    if jahr is None and re.fullmatch(r"\d{4}", s.steuerfeld("008")[7:11]):
        jahr = int(s.steuerfeld("008")[7:11])
    return re.sub(r"^\[.*nicht ermittelbar\]$", "", verlag), jahr


def _seiten(s: Satz) -> int:
    return max((int(n) for w in s.werte("300", "a") for n in _SEITEN.findall(w)), default=0)


def _sachgruppen(s: Satz) -> list[str]:
    aus: list[str] = []
    for f in s.felder("082", "083", "084"):
        art = s.eins(f, "2")
        if art.endswith("sdnb"):
            aus += sachgruppen.aus_dnb(s.alle(f, "a"))
        elif f.get("tag") in ("082", "083"):
            aus += [g for n in s.alle(f, "a") if (g := sachgruppen.aus_dewey(n))]
    return list(dict.fromkeys(aus))


def _schlagworte(s: Satz) -> list[str]:
    """Kontrollierte Schlagworte (Normdatei) und Gattungen; freie Wörter des Handels bleiben bei den Rohdaten."""
    aus: list[str] = []
    for f in s.felder("650", "651", "600", "655"):
        if "gnd" not in s.eins(f, "2") and s.eins(f, "2") != "gatbeg":
            continue
        wort = natuerlich(s.eins(f, "a")) if f.get("tag") == "600" else s.eins(f, "a")
        wort = wort.split(": ", 1)[-1]                    # "Erzählende Literatur: Gegenwartsliteratur ab 1945"
        if wort and wort not in _AUFBEREITUNG:
            aus.append(wort)
    return list(dict.fromkeys(aus))[:SCHLAGWORTE_HOECHSTENS]


def _beschreibung(s: Satz) -> str:
    """Die längste Inhaltsangabe, die kein Verzeichnis ist."""
    return max((t for t in s.werte("520", "a") if t.count(" -- ") < 3), key=len, default="")


def _roh(s: Satz) -> dict[str, object]:
    reihe = [" ".join(filter(None, (s.eins(f, "a"), s.eins(f, "v")))) for f in s.felder("490")]
    verweise = {s.eins(f, "3"): s.eins(f, "u") for f in s.felder("856") if s.eins(f, "3") and s.eins(f, "u").startswith("http")}
    daten = {
        "nummer": s.steuerfeld("001"), "auflage": next(iter(s.werte("250", "a")), ""), "reihe": list(dict.fromkeys(reihe)), "umfang": next(iter(s.werte("300", "a")), ""),
        "notationen": ", ".join(dict.fromkeys(f"{s.eins(f, '2') or 'ddc'} {n}" for f in s.felder("082", "084") for n in s.alle(f, "a"))),
        "freie_schlagworte": list(dict.fromkeys(w for w in s.werte("653", "a") if not _VORSATZ.match(w))), "verweise": verweise,
    }
    return {k: w for k, w in daten.items() if w}


def angaben(s: Satz, quelle: str) -> Angaben:
    autoren, herausgeber, kennungen = _personen(s)
    titel, untertitel = _titel(s)
    verlag, jahr = _erschienen(s)
    isbns = _nummern(s)
    sprachen = [k for w in (*s.werte("041", "a"), s.steuerfeld("008")[35:38]) if (k := kuerzel(w))]
    roh = _roh(s)
    if herausgeber and autoren:
        roh["herausgeber"] = herausgeber
    return Angaben(quelle=quelle, titel=titel, untertitel=untertitel, autoren=autoren or herausgeber, verlag=verlag, jahr=jahr, seiten=_seiten(s), isbn=isbns[0] if isbns else "",
                   isbns=isbns, doi=next((s.eins(f, "a") for f in s.felder("024") if s.eins(f, "2") == "doi"), ""), sprache=sprachen[0] if sprachen else "",
                   beschreibung=_beschreibung(s), kategorien=list(dict.fromkeys(_sachgruppen(s) + _schlagworte(s))), personen=kennungen, roh=roh)


def ist_buch(s: Satz) -> bool:
    """Text, keine Zeitschrift und kein Tonträger."""
    return len(s.leader) < 8 or (s.leader[6] in "at " and s.leader[7] in "mac ")
