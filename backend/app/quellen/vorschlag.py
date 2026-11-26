"""Aus dem Buch eine Frage an die Quellen, aus ihren Angaben ein Vorschlag für den Vergleich in der Oberfläche."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.quellen.abgleich import norm, titel_naehe
from backend.app.quellen.crossref import DOI_IM_TEXT, doi_aus_text
from backend.app.quellen.modelle import Angaben, Buchfrage
from backend.app.quellen.sprache import kuerzel
from backend.app.services.autorennamen import zerlegen
from backend.app.services.data_cleaner import bereinige_metadaten
from backend.app.services.storage import get_sidecar_path

TITEL_GLEICH = 0.97


def textanfang(file_hash: str) -> str:
    """Der Anfang des Volltexts, ohne die ganze Datei zu lesen."""
    try:
        with get_sidecar_path(file_hash, "fulltext.txt").open(encoding="utf-8", errors="ignore") as datei:
            return datei.read(DOI_IM_TEXT)
    except OSError:
        return ""


def frage_aus(buch: Mapping[str, Any]) -> Buchfrage:
    isbn = buch.get("isbn") or ""
    return Buchfrage(isbn=isbn, titel=buch.get("title") or "", autoren=zerlegen(buch.get("author") or ""), jahr=buch.get("year"), sprache=kuerzel(buch.get("language")),
                     seiten=buch.get("page_count") or 0, doi="" if isbn else doi_aus_text(textanfang(buch["hash"])))


def _titel(a: Angaben, bisher: str) -> str:
    """Der Haupttitel; trägt das Buch schon Titel und Untertitel, bleibt es dabei."""
    traegt_beides = len(norm(bisher)) > len(norm(a.titel)) and titel_naehe(bisher, a.titel, a.untertitel) >= TITEL_GLEICH
    return bisher if a.untertitel and traegt_beides else a.titel


def vorschlag(a: Angaben, buch: Mapping[str, Any]) -> dict[str, Any]:
    """Die Felder des Vergleichs, bereinigt; `raw` trägt alles Übrige, `herkunft` je Feld die Quelle."""
    namen = {"autoren": "autor", "umschlag": "cover_url"}
    roh = {"untertitel": a.untertitel, "doi": a.doi, **a.roh} if a.untertitel or a.doi else a.roh
    return bereinige_metadaten({
        "titel": _titel(a, buch.get("title") or ""), "untertitel": a.untertitel, "autor": ", ".join(a.autoren), "isbn": a.isbn, "verlag": a.verlag, "jahr": a.jahr, "seiten": a.seiten,
        "beschreibung": a.beschreibung, "sprache": a.sprache, "kategorien": a.kategorien, "cover_url": a.umschlag, "doi": a.doi, "quelle": a.quelle, "fund": a.fund, "sicher": a.sicher,
        "alter_von": a.alter.von if a.alter else None, "alter_bis": a.alter.bis if a.alter else None,
        "herkunft": {namen.get(f, f): q for f, q in a.herkunft.items()}, "raw": {k: w for k, w in roh.items() if w},
    })
