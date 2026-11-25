"""Gemeinfreie Bücher aus dem Project Gutenberg. Gesucht wird über Gutendex. Die Dateien kommen von den Spiegeln: die Seite selbst
ist nur für Menschen gedacht und weist Programme ab (503, sechs Stunden Ruhe)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from backend.app.quellen import regeln
from backend.app.quellen.abruf import Frage, abruf, hole
from backend.app.quellen.fehler import AnfrageFalsch, QuelleFehler

logger = logging.getLogger("buecherfreunde.quellen.gutenberg")
SPIEGEL = sorted(regeln.GUTENBERG_DATEIEN.rechner, reverse=True)
BUCH_HOECHSTENS = 80_000_000
BILD_HOECHSTENS = 8_000_000
HOLEN_S = 90.0


class Fundbuch(BaseModel):
    gutenberg_id: int
    titel: str
    autor: str = ""
    sprachen: list[str] = Field(default_factory=list)
    download_url: str = ""
    download_format: str = ""
    cover_url: str = ""
    regale: list[str] = Field(default_factory=list)
    themen: list[str] = Field(default_factory=list)
    download_count: int = 0


class Fundliste(BaseModel):
    gesamt: int = 0
    seite: int = 1
    naechste: str | None = None
    vorherige: str | None = None
    buecher: list[Fundbuch] = Field(default_factory=list)


def _datei(formate: dict[str, str]) -> tuple[str, str]:
    """Adresse und Format: EPUB zuerst, sonst Text, am liebsten in UTF-8."""
    def passt(*worte: str) -> str:
        return next((a for art, a in formate.items() if all(w in art.lower() for w in worte)), "")

    if epub := passt("epub"):
        return epub, "epub"
    text = passt("text/plain", "utf-8") or passt("text/plain")
    return (text, "txt") if text else ("", "")


def deuten(roh: dict[str, Any]) -> Fundbuch | None:
    if not roh.get("id"):
        return None
    adresse, format_ = _datei(roh.get("formats") or {})
    return Fundbuch(gutenberg_id=roh["id"], titel=roh.get("title") or f"Gutenberg {roh['id']}", autor="; ".join(a["name"] for a in roh.get("authors") or [] if a.get("name")),
                    sprachen=roh.get("languages") or [], download_url=adresse, download_format=format_, cover_url=next((a for art, a in (roh.get("formats") or {}).items() if "image/jpeg" in art), ""),
                    regale=roh.get("bookshelves") or [], themen=roh.get("subjects") or [], download_count=roh.get("download_count") or 0)


def _verdichten(antwort: dict[str, Any]) -> dict[str, Any]:
    buecher = [b.model_dump(exclude_defaults=True) for r in antwort["results"] if (b := deuten(r))]
    return {"gesamt": antwort.get("count", 0), "naechste": antwort.get("next"), "vorherige": antwort.get("previous"), "buecher": buecher}


async def suche(query: str = "", sprache: str = "", topic: str = "", seite: int = 1) -> Fundliste:
    """Eine Seite der Suche; eine Seite hinter der letzten ist leer. Wirft QuelleFehler."""
    felder = (("search", query.strip()), ("languages", sprache.replace(" ", "").lower()), ("topic", topic.strip()), ("page", str(seite) if seite > 1 else ""))
    frage = Frage(f"{regeln.GUTENBERG.adresse}/books/", tuple(f for f in felder if f[1]), ist_leer=lambda w: not w["results"], verdichte=_verdichten)
    return Fundliste(**(await hole(regeln.GUTENBERG, frage) or {}), seite=seite)


def _von_spiegeln(pfad: str) -> list[str]:
    return [f"https://{s}{pfad}" for s in SPIEGEL]


def _adressen(nummer: int, endung: str) -> list[str]:
    dateien = [f"pg{nummer}.txt"] if endung == ".txt" else [f"pg{nummer}-images-3.epub", f"pg{nummer}.epub"]
    return [a for d in dateien for a in _von_spiegeln(f"/cache/epub/{nummer}/{d}")]


def _brauchbar(inhalt: bytes, endung: str) -> bool:
    """Ein EPUB ist ein Archiv; eine Fehlerseite ist keines von beiden."""
    if endung == ".epub":
        return inhalt.startswith(b"PK")
    return bool(inhalt.strip()) and not inhalt.lstrip()[:15].lower().startswith((b"<!doctype", b"<html"))


async def download_buch(gutenberg_id: int, download_url: str) -> Path:
    """Die Datei eines Buchs an einem vorläufigen Ort. Wirft QuelleFehler mit dem Grund."""
    if not download_url:
        raise AnfrageFalsch("Zu diesem Buch gibt es keine Datei")
    endung = ".txt" if ".txt" in download_url else ".epub"
    grund = "Die Datei ließ sich nicht holen"
    for adresse in _adressen(gutenberg_id, endung):
        try:
            inhalt = await abruf().lade(regeln.GUTENBERG_DATEIEN, adresse, BUCH_HOECHSTENS, HOLEN_S)
        except QuelleFehler as f:
            grund = f.grund
            continue
        if _brauchbar(inhalt, endung):
            with tempfile.NamedTemporaryFile(prefix=f"gutenberg_{gutenberg_id}_", suffix=endung, delete=False) as datei:
                datei.write(inhalt)
            return Path(datei.name)
        grund = "Statt des Buchs kam eine andere Seite"
    raise AnfrageFalsch(grund)


async def download_cover(cover_url: str) -> bytes | None:
    teile = urlsplit(cover_url or "")
    if not teile.path.startswith("/cache/epub/"):
        return None
    for adresse in _von_spiegeln(teile.path):
        try:
            inhalt = await abruf().lade(regeln.GUTENBERG_DATEIEN, adresse, BILD_HOECHSTENS)
        except QuelleFehler as f:
            logger.info("Umschlag nicht geholt: %s", f.grund)
            continue
        if len(inhalt) > 100:
            return inhalt
    return None


async def probe() -> None:
    frage = Frage(f"{regeln.GUTENBERG.adresse}/books/", (("ids", "2229"),), ist_leer=lambda w: not w["results"], verdichte=_verdichten)
    await hole(regeln.GUTENBERG, frage, probe=True)
