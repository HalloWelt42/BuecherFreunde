"""Gemeinsame Normdatei (über lobid.org): wer ein Autor ist, mit Lebensdaten, Beruf, kurzer Biografie und Verweisen auf VIAF, ISNI
und Wikidata. Ohne Anmeldung, Angaben unter CC0."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from backend.app.quellen import regeln
from backend.app.quellen.abgleich import namen_gleich, natuerlich
from backend.app.quellen.abruf import Frage, hole

SUCHE_HOECHSTENS = 20
_VERWEISE = {"viaf": r"viaf\.org/viaf/(\d+)", "isni": r"isni\.org/(?:isni/)?(\d{15}[\dX])", "wikidata": r"wikidata\.org/entity/(Q\d+)", "orcid": r"orcid\.org/([\dX-]{19})", "lc": r"id\.loc\.gov/.*?/(n[a-z]*\d+)$"}


class Person(BaseModel):
    """Ein Datensatz der Normdatei, auf das Nötige gekürzt."""

    gnd: str
    name: str = ""
    weitere_namen: list[str] = Field(default_factory=list)
    geboren: int | None = None
    gestorben: int | None = None
    geburtsort: str = ""
    berufe: list[str] = Field(default_factory=list)
    biografie: str = ""
    land: str = ""
    werke: list[str] = Field(default_factory=list)
    wikipedia: str = ""
    website: str = ""
    verweise: dict[str, str] = Field(default_factory=dict)


class Suchergebnis(BaseModel):
    """Personen dieses Namens; `vollstaendig`, wenn es keine weiteren gibt."""

    personen: list[Person] = Field(default_factory=list)
    vollstaendig: bool = True

    @property
    def einzige(self) -> Person | None:
        return self.personen[0] if self.vollstaendig and len(self.personen) == 1 else None


def _jahr(werte: list[str]) -> int | None:
    treffer = re.match(r"(-?\d{1,4})\b", werte[0].strip()) if werte else None
    return int(treffer.group(1)) if treffer else None


def _namen(liste: list[Any] | None) -> list[str]:
    return [e["label"] if isinstance(e, dict) else str(e) for e in liste or [] if not isinstance(e, dict) or e.get("label")]


def _verweise(gleich: list[dict[str, Any]]) -> dict[str, str]:
    aus: dict[str, str] = {}
    for e in gleich:
        for art, muster in _VERWEISE.items():
            treffer = re.search(muster, e.get("id", ""))
            if treffer:
                aus.setdefault(art, treffer.group(1))
    return aus


def deuten(satz: dict[str, Any]) -> Person:
    biografie = "; ".join(satz.get("biographicalOrHistoricalInformation") or [])
    laender = [land for land in _namen(satz.get("geographicAreaCode")) if land]
    website = next((h.get("id", "") for h in satz.get("homepage") or [] if isinstance(h, dict)), "")
    return Person(gnd=satz["gndIdentifier"], name=natuerlich(satz.get("preferredName", "")), weitere_namen=[natuerlich(n) for n in satz.get("variantName") or []][:40],
                  geboren=_jahr(satz.get("dateOfBirth") or []), gestorben=_jahr(satz.get("dateOfDeath") or []), geburtsort=next(iter(_namen(satz.get("placeOfBirth"))), ""),
                  berufe=_namen(satz.get("professionOrOccupation")), biografie=" ".join(biografie.split()), land=laender[0] if len(laender) == 1 else "",
                  werke=[str(w if not isinstance(w, dict) else w.get("label", "")) for w in satz.get("publication") or []], wikipedia=next((w.get("id", "") for w in satz.get("wikipedia") or []), ""),
                  website=website, verweise=_verweise(satz.get("sameAs") or []))


def _als_wert(p: Person) -> dict[str, Any]:
    return p.model_dump(exclude_defaults=True)


def _frage(anfrage: str, hoechstens: int) -> Frage:
    felder = (("q", anfrage), ("filter", "type:DifferentiatedPerson"), ("format", "json"), ("size", str(hoechstens)))
    return Frage(f"{regeln.GND.adresse}/search", felder, ist_leer=lambda w: not w["member"], verdichte=lambda w: {"gesamt": w["totalItems"], "personen": [_als_wert(deuten(m)) for m in w["member"]]})


async def person(gnd: str, probe: bool = False) -> Person | None:
    """Ein Datensatz nach seiner Kennung. Über die Suche, denn unbekannte Kennungen beantwortet der Einzelabruf mit 500."""
    if not re.fullmatch(r"[\dX-]{6,12}", gnd or ""):
        return None
    daten = await hole(regeln.GND, _frage(f'gndIdentifier:"{gnd}"', 1), probe=probe)
    return Person(**daten["personen"][0]) if daten else None


async def suche(name: str) -> Suchergebnis:
    """Alle Personen dieses Namens, höchstens die ersten zwanzig."""
    *vor, zu = natuerlich(name).split() or [""]
    gesucht = re.sub(r'["\\]', " ", f"{zu}, {' '.join(vor)}" if vor else zu)
    daten = await hole(regeln.GND, _frage(f'preferredName:"{gesucht}" OR variantName:"{gesucht}"', SUCHE_HOECHSTENS))
    if not daten:
        return Suchergebnis()
    personen = [Person(**p) for p in daten["personen"]]
    return Suchergebnis(personen=[p for p in personen if any(namen_gleich(name, n) for n in (p.name, *p.weitere_namen))], vollstaendig=daten["gesamt"] <= SUCHE_HOECHSTENS)


async def probe() -> None:
    await person("118540238", probe=True)
