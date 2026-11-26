"""Fehlerantworten in einer Form (BF-50): immer ein Feld `detail` mit einem deutschen Satz.

- Eine ungültige Eingabe ergibt 422 mit Feld und Grund, etwa "Titel: darf nicht leer sein".
- Ein Pfad, der nichts bezeichnen kann (Nummer keine Zahl oder außerhalb des Bereichs), ergibt 404.
- Was die Datenbank selbst ablehnt, ist nie ein Fehler des Servers: einen Namen, der schon vergeben ist, gibt es schon
  (409), ein genannter Eintrag fehlt (404). Die Wege prüfen das vorher mit genauer Meldung; dies ist die Grenze für alle.
Zurückgerollt wird, was die Anfrage bis dahin geändert hat, in core/einheiten.py."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("buecherfreunde.fehler")

NICHT_GEFUNDEN = "Nicht gefunden"
GIBT_ES_SCHON = "Das gibt es schon"
BEZUG_FEHLT = "Ein genannter Eintrag fehlt"

# Felder, wie sie in der Oberfläche heißen; was hier fehlt, erscheint mit seinem Namen
FELDER = {
    "title": "Titel", "author": "Autor", "isbn": "ISBN", "publisher": "Verlag", "year": "Jahr", "language": "Sprache",
    "description": "Beschreibung", "page_count": "Seiten", "typ": "Typ", "gattung": "Gattung", "umschlag_wahl": "Umschlag", "sammlung_id": "Sammlung", "band_nummer": "Band",
    "content": "Notiz", "page_reference": "Seite", "cfi_reference": "Stelle", "cfi_range": "Stelle", "color": "Farbe",
    "text_snippet": "Text", "label_name": "Etikett", "label_note": "Notiz", "name": "Name", "note": "Notiz",
    "position_percent": "Position", "icon": "Symbol", "sort_order": "Reihenfolge", "spezial": "Besonders",
    "position": "Leseposition", "bewertung": "Bewertung", "book_ids": "Bücher", "aktion": "Aktion", "wert": "Wert",
    "biography": "Biografie", "birth_year": "Geburtsjahr", "death_year": "Sterbejahr", "nationality": "Herkunft",
    "website": "Website", "wikidata_id": "Wikidata", "wikipedia_url": "Wikipedia", "kategorien": "Kategorien",
    "system_prompt": "Anweisung", "temperatur": "Temperatur", "max_tokens": "Länge der Antwort", "beschreibung": "Beschreibung",
    "seite": "Seite", "pro_seite": "Einträge je Seite", "limit": "Anzahl", "offset": "Versatz", "q": "Suche",
    "groesse": "Größe", "sha256": "Prüfsumme", "quelle": "Quelle", "stand": "Zustand",
    # Katalog (BF-69)
    "bereiche": "Bereiche", "schluessel": "Schlüssel", "zeichen": "Zeichen", "farbe": "Farbe", "ki_beschreibung": "Beschreibung für die KI",
    "regeln": "Regeln", "sachgruppen": "Sachgruppen", "schlagworte": "Schlagworte", "titelwoerter": "Titelwörter", "verlage": "Verlage",
    "verborgen": "Verborgen", "herkunft": "Herkunft", "teile": "Teile", "arten": "Arten", "bereich_id": "Bereich", "weg": "Weg",
    "ids": "Auswahl", "ziel": "Ziel", "kategorie_id": "Kategorie", "stapel": "Stapel", "fassung": "Fassung", "kategorie": "Kategorie",
    "ki_je_anfrage": "Bücher je Anfrage", "sicher_ab": "Vorab angehakt ab", "teilen_ab": "Teilen ab",
    # Lücken in Sammlungen (BF-75)
    "suchadresse": "Suchadresse", "gesamt": "Bände je Sprache", "wahl": "Wahl", "zahl": "Zahl", "nummer": "Band", "an": "Platzhalter",
    "grund": "Grund", "sprache": "Sprache",
}


def _wert(v: Any) -> str:
    """Wie ein Mensch eine Grenze schreibt: 100 statt 100.0, 0,5 statt 0.5, gerade Anführungszeichen, oder statt or."""
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else str(v).replace(".", ",")
    return str(v).replace("'", '"').replace(" or ", " oder ")


def _grund(fehler: dict[str, Any]) -> str:
    art, ctx = fehler.get("type", ""), fehler.get("ctx") or {}
    if art == "value_error":
        return str(ctx.get("error") or fehler.get("msg", "ist ungültig"))
    texte = {
        "missing": "fehlt",
        "string_too_short": "darf nicht leer sein" if ctx.get("min_length") == 1 else "mindestens {min_length} Zeichen",
        "string_too_long": "höchstens {max_length} Zeichen",
        "too_long": "höchstens {max_length} Einträge",
        "too_short": "mindestens {min_length} Einträge",
        "string_pattern_mismatch": "hat nicht die erwartete Form",
        "greater_than_equal": "mindestens {ge}",
        "greater_than": "größer als {gt}",
        "less_than_equal": "höchstens {le}",
        "less_than": "kleiner als {lt}",
        "int_parsing": "keine ganze Zahl", "int_type": "keine ganze Zahl", "int_from_float": "keine ganze Zahl",
        "float_parsing": "keine Zahl", "float_type": "keine Zahl", "finite_number": "keine Zahl",
        "bool_parsing": "weder true noch false", "bool_type": "weder true noch false",
        "string_type": "kein Text", "list_type": "keine Liste",
        "dict_type": "hat nicht die erwartete Form", "model_type": "hat nicht die erwartete Form",
        "model_attributes_type": "hat nicht die erwartete Form",
        "literal_error": "erlaubt ist {expected}", "enum": "erlaubt ist {expected}",
        "json_invalid": "ist kein gültiges JSON", "json_type": "ist kein gültiges JSON",
        "extra_forbidden": "ist hier nicht vorgesehen",
    }
    vorlage = texte.get(art, "ist ungültig")
    try:
        return vorlage.format(**{k: _wert(v) for k, v in ctx.items()})
    except (KeyError, IndexError):
        return "ist ungültig"


def _feld(ort: Sequence[str | int]) -> str:
    """("body", "book_ids", 3) wird "Bücher, Eintrag 4"; der Ort der Eingabe (body, query) bleibt weg."""
    teile = [t for t in ort if t not in ("body", "query", "header", "cookie", "path")]
    if not teile:
        return "Anfrage"
    namen = [f"Eintrag {t + 1}" if isinstance(t, int) else FELDER.get(t, t) for t in teile]
    return ", ".join(namen)


def meldung(fehler: Sequence[dict[str, Any]]) -> str:
    """Ein Satz für alle Fehler einer Eingabe, jedes Feld einmal."""
    gesehen: dict[str, str] = {}
    for f in fehler:
        gesehen.setdefault(_feld(f.get("loc", ())), _grund(f))
    return "; ".join(f"{feld}: {grund}" for feld, grund in gesehen.items())


async def _ungueltig(_: Request, f: Exception) -> JSONResponse:
    assert isinstance(f, RequestValidationError)
    fehler = f.errors()
    if any(e.get("loc", ("",))[0] == "path" for e in fehler):
        return JSONResponse({"detail": NICHT_GEFUNDEN}, status_code=404)
    return JSONResponse({"detail": meldung(fehler)}, status_code=422)


async def _abgelehnt(request: Request, f: Exception) -> JSONResponse:
    text = str(f)
    if text.startswith("UNIQUE"):
        return JSONResponse({"detail": GIBT_ES_SCHON}, status_code=409)
    if text.startswith("FOREIGN KEY"):
        return JSONResponse({"detail": BEZUG_FEHLT}, status_code=404)
    logger.warning("Von der Datenbank abgelehnt (%s %s): %s", request.method, request.url.path, text)
    return JSONResponse({"detail": "Die Angaben passen nicht zusammen"}, status_code=422)


async def _zu_gross(request: Request, f: Exception) -> JSONResponse:
    logger.warning("Zahl außerhalb des Bereichs (%s %s): %s", request.method, request.url.path, f)
    return JSONResponse({"detail": "Eine Zahl liegt außerhalb des gültigen Bereichs"}, status_code=422)


class MitCode(HTTPException):
    """Ein Fehler, den die Oberfläche an `code` erkennt; `detail` bleibt der deutsche Satz (BF-78: profil_waehlen)."""

    def __init__(self, status_code: int, detail: str, code: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(status_code, detail, headers)
        self.code = code


async def _mit_code(_: Request, f: Exception) -> JSONResponse:
    assert isinstance(f, MitCode)
    return JSONResponse({"detail": f.detail, "code": f.code}, status_code=f.status_code, headers=f.headers)


def einrichten(app: FastAPI) -> None:
    app.add_exception_handler(MitCode, _mit_code)
    app.add_exception_handler(RequestValidationError, _ungueltig)
    app.add_exception_handler(sqlite3.IntegrityError, _abgelehnt)
    app.add_exception_handler(OverflowError, _zu_gross)
