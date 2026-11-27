"""Was die Vertonung zum Sprechen anbietet, aus ihrer eigenen Beschreibung statt aus einer festen Liste (STIMMEN.md,
Entscheidung 3). Die Vertonung führt den Vertrag ihres Stroms im Schema der App (OpenAPI, Modell der Anfrage an
`POST /api/v1/sprechen/strom`); jedes Feld darin außer Text und Stimme ist eine Einstellung: ihr Name, ihre Art (Zahl, ganze
Zahl, Schalter, Text, Wahl), ihre Grenzen und ihre Vorgabe. Deutsche Namen kommen aus `beschriftungen.json`; ein Feld, das dort
fehlt, behält den Namen der Vertonung und steht unter "Mehr". Was sich nicht als einfacher Wert einstellen lässt (Listen,
Objekte), bleibt weg.

Gelesen wird das Schema über `SCHEMA`, den Weg, über den das Gerüst des Appkerns es zeigt. Lehnt die Vertonung ab oder fehlt
etwas darin, gibt es keine Beschreibung, und der Hinweis sagt warum; gespeicherte Werte prüft `pruefen` gegen die Beschreibung."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from appkern.verbund import ABFRAGE, VerbundFehler
from appkern.vorlesen import STROM
from pydantic import BaseModel, Field

from backend.app.vorlesen import zugang
from backend.app.vorlesen.modelle import Beschreibung, Feld, Feldart, Sprechwert, Wahlwert

logger = logging.getLogger("buecherfreunde.vorlesen")
SCHEMA = "/api/v1/schnittstelle"
DATEI = Path(__file__).with_name("beschriftungen.json")
SELBST = frozenset({"text", "stimme"})        # Text und Stimme nennt BücherFreunde bei jedem Aufruf selbst
ARTEN: dict[str, Feldart] = {"number": "zahl", "integer": "ganzzahl", "boolean": "schalter", "string": "text"}


class Unlesbar(Exception):
    """Das Schema der Vertonung trägt nicht, was hier gebraucht wird."""


class Unpassend(Exception):
    """Ein Wert passt nicht zur Beschreibung; `meldung` nennt Feld und Grund."""

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


class _Beschriftung(BaseModel):
    name: str
    erklaerung: str = ""
    werte: dict[str, str] = Field(default_factory=dict)


class _Beschriftungen(BaseModel):
    felder: dict[str, _Beschriftung]


@lru_cache(maxsize=1)
def beschriftungen() -> dict[str, _Beschriftung]:
    return _Beschriftungen.model_validate(json.loads(DATEI.read_text(encoding="utf-8"))).felder


# -- Schema lesen -----------------------------------------------------------------------------------------------------------------

def _aufloesen(schema: Mapping[str, Any], teil: Mapping[str, Any]) -> Mapping[str, Any]:
    """Ein Verweis (`$ref` auf `#/components/schemas/...`) wird zu dem, worauf er zeigt."""
    while "$ref" in teil:
        ziel: Any = schema
        for schritt in str(teil["$ref"]).removeprefix("#/").split("/"):
            if not isinstance(ziel, Mapping) or schritt not in ziel:
                raise Unlesbar(f"Verweis {teil['$ref']} fehlt")
            ziel = ziel[schritt]
        teil = ziel
    return teil


def _anfrage(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    """Die Felder der Anfrage an den Strom."""
    try:
        koerper = schema["paths"][STROM]["post"]["requestBody"]["content"]["application/json"]["schema"]
    except (KeyError, TypeError) as f:
        raise Unlesbar(f"im Schema fehlt die Anfrage an {STROM}") from f
    felder = _aufloesen(schema, koerper).get("properties")
    if not isinstance(felder, Mapping):
        raise Unlesbar(f"die Anfrage an {STROM} nennt keine Felder")
    return felder


def _ohne_leer(schema: Mapping[str, Any], teil: Mapping[str, Any]) -> Mapping[str, Any]:
    """Ein Feld, das auch leer sein darf (`anyOf` mit null), gilt als seine eigentliche Art."""
    teil = _aufloesen(schema, teil)
    if isinstance(teil.get("anyOf"), list):
        echte = [_aufloesen(schema, t) for t in teil["anyOf"] if isinstance(t, Mapping) and t.get("type") != "null"]
        if len(echte) == 1:
            return {**echte[0], **{k: v for k, v in teil.items() if k != "anyOf"}}
    return teil


def _feld(schema: Mapping[str, Any], schluessel: str, roh: Mapping[str, Any]) -> Feld | None:
    teil = _ohne_leer(schema, roh)
    art = ARTEN.get(str(teil.get("type") or ""))
    if art is None:
        return None                            # keine einfache Einstellung (Liste, Objekt, Mischung)
    bekannt = beschriftungen().get(schluessel)
    werte = [Wahlwert(wert=str(w), name=bekannt.werte.get(str(w), str(w)) if bekannt else str(w))
             for w in teil.get("enum") or [] if isinstance(w, str | int | float)]
    von = teil.get("minimum", teil.get("exclusiveMinimum"))
    bis = teil.get("maximum", teil.get("exclusiveMaximum"))
    vorgabe = teil.get("default")
    return Feld(schluessel=schluessel, name=bekannt.name if bekannt else str(teil.get("title") or schluessel),
                art="wahl" if werte else art, von=von, bis=bis, werte=werte,
                vorgabe=vorgabe if isinstance(vorgabe, bool | int | float | str) else None,
                erklaerung=bekannt.erklaerung if bekannt and bekannt.erklaerung else str(teil.get("description") or ""),
                mehr=bekannt is None)


def felder_aus(schema: Mapping[str, Any]) -> list[Feld]:
    """Die Einstellungen aus dem Schema, erst die benannten in der Folge der Datei, dann "Mehr" in der Folge der Vertonung."""
    felder = [f for k, roh in _anfrage(schema).items() if k not in SELBST and isinstance(roh, Mapping) and (f := _feld(schema, k, roh))]
    folge = list(beschriftungen())
    return sorted(felder, key=lambda f: (f.mehr, folge.index(f.schluessel) if f.schluessel in folge else 0))


async def lesen() -> Beschreibung:
    """Die Beschreibung, jedes Mal von der Vertonung; ohne Vertonung leer ohne Hinweis."""
    if not zugang.bereit():
        return Beschreibung(da=False, felder=[])
    try:
        schema = (await zugang.verbund.anfrage("GET", zugang.adresse(), SCHEMA, timeout=ABFRAGE)).json()
        return Beschreibung(da=True, felder=felder_aus(schema))
    except VerbundFehler as f:
        grund = zugang.fehler(f).meldung if f.status is None else f.meldung
        return Beschreibung(da=False, felder=[], hinweis=f"Die Vertonung beschreibt ihre Einstellungen BücherFreunde nicht: {grund}")
    except (Unlesbar, ValueError) as f:
        logger.info("Beschreibung der Vertonung nicht lesbar: %s", f)
        return Beschreibung(da=False, felder=[], hinweis=f"Die Beschreibung der Vertonung ist nicht lesbar: {f}")


# -- Werte prüfen -----------------------------------------------------------------------------------------------------------------

def _zahl(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def _passt(f: Feld, wert: Sprechwert) -> str:
    """Leer, wenn der Wert zum Feld passt; sonst der Grund."""
    if f.art == "schalter":
        return "" if isinstance(wert, bool) else "an oder aus"
    if f.art in ("zahl", "ganzzahl"):
        if isinstance(wert, bool) or not isinstance(wert, int | float) or (f.art == "ganzzahl" and not isinstance(wert, int)):
            return "eine ganze Zahl" if f.art == "ganzzahl" else "eine Zahl"
        if (f.von is not None and wert < f.von) or (f.bis is not None and wert > f.bis):
            return " ".join(t for t in (f"von {_zahl(f.von)}" if f.von is not None else "", f"bis {_zahl(f.bis)}" if f.bis is not None else "") if t)
        return ""
    if not isinstance(wert, str):
        return "ein Text"
    if f.art == "wahl" and wert not in {w.wert for w in f.werte}:
        return "eine von " + ", ".join(w.name for w in f.werte)
    return ""


def pruefen(werte: Mapping[str, Sprechwert], b: Beschreibung) -> dict[str, Sprechwert]:
    """Die Werte, wenn jeder zu seinem Feld der Beschreibung passt; sonst `Unpassend`. Leer geht immer (alles ab Werk)."""
    if not werte:
        return {}
    if not b.da:
        raise Unpassend(b.hinweis or "Die Vertonung beschreibt ihre Einstellungen gerade nicht")
    felder = {f.schluessel: f for f in b.felder}
    for schluessel, wert in werte.items():
        if (f := felder.get(schluessel)) is None:
            raise Unpassend(f"{schluessel}: bietet die Vertonung nicht an")
        if grund := _passt(f, wert):
            raise Unpassend(f"{f.name}: {grund}")
    return dict(werte)
