"""Parser fuer erweiterte Suchsyntax.

Unterstuetzte Filter:
  "exakter Satz"       - Phrasensuche (FTS5-nativ)
  autor:Name           - Autorenfilter (LIKE)
  author:Name          - Alias fuer autor
  format:epub          - Formatfilter (exakt)
  datum:2020-2024      - Erscheinungsjahr (Bereich)
  datum:>2020          - Ab Erscheinungsjahr
  datum:<2024          - Bis Erscheinungsjahr
  datum:2023           - Exaktes Erscheinungsjahr
"""

import re
from dataclasses import dataclass, field


@dataclass
class ParsedQuery:
    """Ergebnis des Query-Parsers."""

    fts_query: str = ""
    autor: str | None = None
    format: str | None = None
    jahr_von: int | None = None
    jahr_bis: int | None = None
    jahr_exakt: int | None = None

    @property
    def hat_filter(self) -> bool:
        return any([self.autor, self.format, self.jahr_von, self.jahr_bis, self.jahr_exakt])

    @property
    def aktive_filter(self) -> dict:
        """Gibt die aktiven Filter als Dict zurueck (fuer die API-Response)."""
        f = {}
        if self.autor:
            f["autor"] = self.autor
        if self.format:
            f["format"] = self.format
        if self.jahr_exakt:
            f["jahr"] = str(self.jahr_exakt)
        elif self.jahr_von and self.jahr_bis:
            f["zeitraum"] = f"{self.jahr_von}-{self.jahr_bis}"
        elif self.jahr_von:
            f["ab_jahr"] = str(self.jahr_von)
        elif self.jahr_bis:
            f["bis_jahr"] = str(self.jahr_bis)
        return f


# Regex fuer Filter-Tokens (nur ausserhalb von Anfuehrungszeichen matchen)
_FILTER_AUTOR = re.compile(r'\b(?:autor|author):(\S+)', re.IGNORECASE)
_FILTER_FORMAT = re.compile(r'\bformat:(\S+)', re.IGNORECASE)
_FILTER_DATUM = re.compile(r'\b(?:datum|date):(\S+)', re.IGNORECASE)

# Phrasen in Anfuehrungszeichen erkennen
_PHRASE_RE = re.compile(r'"[^"]*"')


def parse_query(raw: str) -> ParsedQuery:
    """Zerlegt eine Suchanfrage in FTS-Teil und strukturierte Filter.

    Phrasen in Anfuehrungszeichen werden geschuetzt und korrekt an FTS5 durchgereicht.
    """
    if not raw or not raw.strip():
        return ParsedQuery()

    result = ParsedQuery()
    text = raw.strip()

    # 1. Phrasen schuetzen (durch Platzhalter ersetzen, damit Filter-Regex
    #    nicht innerhalb von Phrasen matcht)
    phrasen = []

    def phrase_ersetzen(m):
        idx = len(phrasen)
        phrasen.append(m.group(0))
        return f"\x00PHRASE{idx}\x00"

    text = _PHRASE_RE.sub(phrase_ersetzen, text)

    # 2. Autorenfilter extrahieren
    m = _FILTER_AUTOR.search(text)
    if m:
        result.autor = m.group(1).strip('"').strip("'")
        text = _FILTER_AUTOR.sub("", text)

    # 3. Formatfilter extrahieren
    m = _FILTER_FORMAT.search(text)
    if m:
        result.format = m.group(1).strip('"').strip("'").lower().lstrip(".")
        text = _FILTER_FORMAT.sub("", text)

    # 4. Datumsfilter extrahieren
    m = _FILTER_DATUM.search(text)
    if m:
        _parse_datum(m.group(1), result)
        text = _FILTER_DATUM.sub("", text)

    # 5. Phrasen zuruecksetzen
    for i, phrase in enumerate(phrasen):
        text = text.replace(f"\x00PHRASE{i}\x00", phrase)

    # 6. Bereinigen (Mehrfach-Leerzeichen, Trimmen)
    result.fts_query = re.sub(r'\s+', ' ', text).strip()

    return result


def _parse_datum(wert: str, result: ParsedQuery):
    """Parst Datumsangaben wie >2020, <2024, 2020-2024, 2023."""
    wert = wert.strip()

    # Bereich: 2020-2024
    m = re.match(r'^(\d{4})-(\d{4})$', wert)
    if m:
        result.jahr_von = int(m.group(1))
        result.jahr_bis = int(m.group(2))
        return

    # Ab: >2020 oder >=2020
    m = re.match(r'^>=?(\d{4})$', wert)
    if m:
        result.jahr_von = int(m.group(1))
        return

    # Bis: <2024 oder <=2024
    m = re.match(r'^<=?(\d{4})$', wert)
    if m:
        result.jahr_bis = int(m.group(1))
        return

    # Exakt: 2023
    m = re.match(r'^(\d{4})$', wert)
    if m:
        result.jahr_exakt = int(m.group(1))
        return
