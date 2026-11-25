"""Je Quelle die Regeln des Anstands: Abstand, Zahl je Minute, Haltbarkeit der Antworten, Tagesgrenze im Hintergrund.
Nachgelesen bei den Anbietern, Stand November 2026. Wer sich mit QUELLEN_KONTAKT zu erkennen gibt, darf bei manchen mehr."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.app.core.config import settings

TAG_S = 24 * 3600


class Regel(BaseModel):
    model_config = ConfigDict(frozen=True)

    kennung: str
    name: str                                  # so heißt sie in der Oberfläche
    anbieter: str
    schalter: str                              # Name der Einstellung, die sie abschaltet
    schluessel: str = ""                       # Name der Einstellung mit einem eigenen Schlüssel, ohne den sie nicht antwortet
    art: Literal["buch", "autor", "bestand"]
    adresse: str
    rechner: frozenset[str]                    # nur von hier wird geholt
    gehoert_zu: str = ""                       # Bilder und Dateien einer Quelle: eigener Stand, damit ein Ausfall dort die Suche nicht trifft
    ein_takt: bool = False                     # alle Rechner zusammen zählen, nicht jeder für sich
    abstand_s: float = 1.0
    abstand_mit_kontakt_s: float | None = None
    je_sekunde: str = ""                       # Name einer Einstellung mit Anfragen je Sekunde, die langsamer stellen darf
    je_minute: int = 30
    je_minute_mit_kontakt: int | None = None
    zeit_s: float = 15.0
    treffer_tage: float = 90
    leer_tage: float = 14
    fehler_s: float = 120
    hintergrund_tag: int = 500

    @property
    def aktiv(self) -> bool:
        return bool(getattr(settings, self.schalter))

    @property
    def hindernis(self) -> str:
        """Warum sie gar nicht erst gefragt wird; leer, wenn sie bereit ist."""
        if not self.aktiv:
            return "ist abgeschaltet"
        if self.schluessel and not getattr(settings, self.schluessel):
            return f"antwortet nur mit eigenem Schlüssel ({self.schluessel.upper()})"
        return ""

    @property
    def abstand(self) -> float:
        mit_kontakt = settings.quellen_kontakt and self.abstand_mit_kontakt_s is not None
        eingestellt = 1.0 / max(getattr(settings, self.je_sekunde), 0.1) if self.je_sekunde else 0.0
        return max(self.abstand_mit_kontakt_s if mit_kontakt else self.abstand_s, eingestellt)

    @property
    def minute(self) -> int:
        if settings.quellen_kontakt and self.je_minute_mit_kontakt is not None:
            return self.je_minute_mit_kontakt
        return self.je_minute

    @property
    def tagesgrenze(self) -> int:
        return min(self.hintergrund_tag, settings.quellen_hintergrund_tag)


# Seit 2026 steht die Tagesmenge ohne eigenen Schlüssel auf 0
GOOGLE_BOOKS = Regel(kennung="google_books", name="Verzeichnis 1", anbieter="Google Books", schalter="google_books_enabled", schluessel="google_books_api_key", art="buch", adresse="https://www.googleapis.com/books/v1",
                     rechner=frozenset({"www.googleapis.com"}), abstand_s=1.0, je_minute=30, hintergrund_tag=300)
# 1 je Sekunde, mit Kontakt 3; Umschläge über die ISBN höchstens 100 in 5 Minuten
OPEN_LIBRARY = Regel(kennung="open_library", name="Verzeichnis 2", anbieter="Open Library", schalter="openlibrary_enabled", art="buch", adresse="https://openlibrary.org/api",
                     rechner=frozenset({"openlibrary.org"}), abstand_s=1.1, abstand_mit_kontakt_s=0.5, je_sekunde="openlibrary_rate_limit", je_minute=18, je_minute_mit_kontakt=60, hintergrund_tag=400)
DNB = Regel(kennung="dnb", name="Verzeichnis 3", anbieter="Deutsche Nationalbibliothek", schalter="dnb_enabled", art="buch", adresse="https://services.dnb.de/sru/dnb",
            rechner=frozenset({"services.dnb.de"}), abstand_s=1.0, je_minute=30, hintergrund_tag=1000)
K10PLUS = Regel(kennung="k10plus", name="Verzeichnis 4", anbieter="K10plus, Verbundkatalog", schalter="k10plus_enabled", art="buch", adresse="https://sru.k10plus.de/opac-de-627",
                rechner=frozenset({"sru.k10plus.de"}), abstand_s=1.0, je_minute=30, hintergrund_tag=1000)
# Suche ohne Kontakt: 1 je Sekunde, eine zugleich
CROSSREF = Regel(kennung="crossref", name="Verzeichnis 5", anbieter="Crossref", schalter="crossref_enabled", art="buch", adresse="https://api.crossref.org",
                 rechner=frozenset({"api.crossref.org"}), abstand_s=1.2, je_minute=30, treffer_tage=180, hintergrund_tag=500)
# Ohne Kontaktangabe 10 je Minute über alle Wikis zusammen, mit Kontakt 200
WIKIPEDIA = Regel(kennung="wikipedia", name="Lexikon", anbieter="Wikipedia und Wikidata", schalter="wikipedia_enabled", art="buch", adresse="https://www.wikidata.org/w/api.php",
                  rechner=frozenset({"www.wikidata.org", "de.wikipedia.org", "en.wikipedia.org"}),
                  ein_takt=True, abstand_s=1.0, abstand_mit_kontakt_s=0.5, je_minute=9, je_minute_mit_kontakt=90, treffer_tage=60, hintergrund_tag=4000)
# Einfache Abrufe reichlich, Suchen höchstens 30 je Minute; Antworten mindestens 12 Stunden behalten
GND = Regel(kennung="gnd", name="Normdatei", anbieter="Gemeinsame Normdatei über lobid.org", schalter="gnd_enabled", art="autor", adresse="https://lobid.org/gnd",
            rechner=frozenset({"lobid.org"}), abstand_s=0.8, je_minute=25, treffer_tage=60, hintergrund_tag=2000)
GUTENBERG = Regel(kennung="gutenberg", name="Gemeinfreie Bücher", anbieter="Project Gutenberg über Gutendex", schalter="gutenberg_enabled", art="bestand", adresse="https://gutendex.com",
                  rechner=frozenset({"gutendex.com"}), abstand_s=2.0, je_minute=15, zeit_s=40, treffer_tage=14, leer_tage=3, hintergrund_tag=200)



def _dateien(quelle: Regel, was: str, rechner: set[str], abstand_s: float, je_minute: int, **weitere: object) -> Regel:
    felder = {"kennung": f"{quelle.kennung}_dateien", "name": f"{quelle.name}, {was}", "rechner": frozenset(rechner), "gehoert_zu": quelle.kennung, "abstand_s": abstand_s, "je_minute": je_minute,
              "abstand_mit_kontakt_s": None, "je_minute_mit_kontakt": None, "je_sekunde": ""}
    return quelle.model_copy(update={**felder, **weitere})


REGELN: dict[str, Regel] = {r.kennung: r for r in (GOOGLE_BOOKS, OPEN_LIBRARY, DNB, K10PLUS, CROSSREF, WIKIPEDIA, GND, GUTENBERG)}
GOOGLE_BILDER = _dateien(GOOGLE_BOOKS, "Umschläge", {"books.google.com"}, 1.0, 20)
OPEN_LIBRARY_BILDER = _dateien(OPEN_LIBRARY, "Umschläge", {"covers.openlibrary.org", "archive.org"}, 1.5, 18)
WIKIPEDIA_BILDER = _dateien(WIKIPEDIA, "Fotos", {"commons.wikimedia.org", "upload.wikimedia.org", "thumb.wikimedia.org"}, 1.5, 9, treffer_tage=90)
GUTENBERG_DATEIEN = _dateien(GUTENBERG, "Dateien", {"gutenberg.pglaf.org", "aleph.pglaf.org"}, 2.0, 15, zeit_s=40.0)
_ALLE = (*REGELN.values(), GOOGLE_BILDER, OPEN_LIBRARY_BILDER, WIKIPEDIA_BILDER, GUTENBERG_DATEIEN)


def regel_fuer_rechner(rechner: str) -> Regel | None:
    return next((r for r in _ALLE if rechner in r.rechner), None)
