"""Zentrale Datenbereinigung für externe Metadaten.

Alle Daten aus externen Quellen (OpenLibrary, Google Books, EPUB-Metadaten,
KI-Kategorisierung) muessen durch diesen Service laufen, bevor sie in die
Datenbank geschrieben werden.

Bereinigt:
- Kommagetrennte Kategorien aufsplitten
- Sonderzeichen-Muell erkennen und ablehnen
- Zu lange oder zu kurze Eintraege filtern
- Duplikate und Varianten zusammenfuehren
- Allgemeine Textbereinigung (Whitespace, Steuerzeichen)
"""

import logging
import re
import unicodedata

logger = logging.getLogger("buecherfreunde.data_cleaner")

# --- Maximale Laengen ---
MAX_KATEGORIE_LAENGE = 60
MIN_KATEGORIE_LAENGE = 2
MAX_TAG_LAENGE = 40
MAX_TITEL_LAENGE = 500
MAX_AUTOR_LAENGE = 300

# --- Verdaechtige Muster (wahrscheinlich keine echte Kategorie/Tag) ---
_VERDAECHTIG_RE = re.compile(
    r"[{}()\[\]<>\"'`]"        # Klammern, Anfuehrungszeichen
    r"|\.{2,}"                  # Mehrere Punkte
    r"|\d{5,}"                  # Lange Zahlenfolgen
    r"|https?://"               # URLs
    r"|www\."                   # URLs
    r"|@"                       # E-Mail-Adressen
    r"|[;!?#$%^&*+=|\\~]"      # Programmier-Sonderzeichen
)

# Meta-Kategorien die keine echten Kategorien sind
_SKIP_KATEGORIEN = {
    "general", "general fiction", "fiction", "nonfiction", "non-fiction",
    "book", "books", "ebook", "ebooks", "e-book",
    "accessible book", "protected daisy",
    "in library", "lending library",
    "large type books", "large print",
    "reading level", "open syllabus project",
    "internet archive wishlist",
}

# Haeufige Trennzeichen in zusammengesetzten Kategorie-Strings
_TRENNZEICHEN_RE = re.compile(r"\s*[,;/|]\s*")


def bereinige_kategorien(roh_liste: list[str]) -> list[str]:
    """Bereinigt eine Liste von Kategorienamen aus externen Quellen.

    - Spaltet kommagetrennte Eintraege auf
    - Filtert Muell und Meta-Kategorien
    - Normalisiert Gross/Kleinschreibung
    - Entfernt Duplikate (case-insensitive)

    Returns:
        Bereinigte, sortierte Liste eindeutiger Kategorienamen.
    """
    ergebnis = []
    gesehen = set()  # Lowercase fuer Duplikat-Check

    for eintrag in roh_liste:
        if not isinstance(eintrag, str):
            continue

        # Aufsplitten bei Komma, Semikolon, Pipe, Slash
        teile = _TRENNZEICHEN_RE.split(eintrag)

        for teil in teile:
            bereinigt = _bereinige_einzelwert(teil)
            if not bereinigt:
                continue

            lower = bereinigt.lower()

            # Bekannte Meta-Kategorien ueberspringen
            if lower in _SKIP_KATEGORIEN:
                logger.debug("Meta-Kategorie uebersprungen: '%s'", bereinigt)
                continue

            # Zu lang oder zu kurz
            if len(bereinigt) < MIN_KATEGORIE_LAENGE:
                continue
            if len(bereinigt) > MAX_KATEGORIE_LAENGE:
                logger.debug("Kategorie zu lang, abgelehnt: '%s'", bereinigt)
                continue

            # Verdaechtige Zeichen pruefen
            if _VERDAECHTIG_RE.search(bereinigt):
                logger.debug("Verdaechtige Kategorie abgelehnt: '%s'", bereinigt)
                continue

            # Satz-Erkennung: zu viele Woerter = wahrscheinlich ein Satz, kein Kategoriename
            wort_count = len(bereinigt.split())
            if wort_count > 5:
                logger.debug("Zu viele Woerter, abgelehnt: '%s'", bereinigt)
                continue
            if "." in bereinigt and wort_count > 3:
                logger.debug("Satz als Kategorie abgelehnt: '%s'", bereinigt)
                continue

            # Duplikat-Check (case-insensitive)
            if lower in gesehen:
                continue
            gesehen.add(lower)

            ergebnis.append(bereinigt)

    if len(ergebnis) != len(roh_liste):
        logger.info(
            "Kategorien bereinigt: %d -> %d (Eingabe: %s)",
            len(roh_liste), len(ergebnis), roh_liste[:5],
        )

    return sorted(ergebnis)


def bereinige_tags(roh_liste: list[str]) -> list[str]:
    """Bereinigt eine Liste von Tag-Namen. Gleiche Logik wie Kategorien."""
    ergebnis = []
    gesehen = set()

    for eintrag in roh_liste:
        if not isinstance(eintrag, str):
            continue

        teile = _TRENNZEICHEN_RE.split(eintrag)

        for teil in teile:
            bereinigt = _bereinige_einzelwert(teil)
            if not bereinigt:
                continue
            if len(bereinigt) > MAX_TAG_LAENGE or len(bereinigt) < MIN_KATEGORIE_LAENGE:
                continue
            if _VERDAECHTIG_RE.search(bereinigt):
                continue

            lower = bereinigt.lower()
            if lower in gesehen:
                continue
            gesehen.add(lower)
            ergebnis.append(bereinigt)

    return sorted(ergebnis)


def bereinige_text(text: str, max_laenge: int = 0) -> str:
    """Bereinigt einen Textstring (Titel, Autor, Beschreibung etc.).

    - Entfernt Steuerzeichen
    - Normalisiert Whitespace
    - Kuerzt auf max_laenge falls angegeben
    """
    if not text or not isinstance(text, str):
        return ""

    # Steuerzeichen entfernen (ausser Newlines in Beschreibungen)
    text = "".join(
        ch for ch in text
        if unicodedata.category(ch)[0] != "C" or ch in ("\n", "\r", "\t")
    )

    # Whitespace normalisieren
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()

    if max_laenge and len(text) > max_laenge:
        text = text[:max_laenge].rsplit(" ", 1)[0]

    return text


def bereinige_titel(titel: str) -> str:
    """Bereinigt einen Buchtitel."""
    bereinigt = bereinige_text(titel, MAX_TITEL_LAENGE)
    # Titel in Grossbuchstaben -> Title Case
    if bereinigt and bereinigt == bereinigt.upper() and len(bereinigt) > 5:
        bereinigt = bereinigt.title()
    return bereinigt


def bereinige_autor(autor: str) -> str:
    """Bereinigt einen Autorennamen."""
    bereinigt = bereinige_text(autor, MAX_AUTOR_LAENGE)
    # Autor komplett in Grossbuchstaben -> Title Case
    if bereinigt and bereinigt == bereinigt.upper() and len(bereinigt) > 5:
        bereinigt = bereinigt.title()
    return bereinigt


def bereinige_metadaten(daten: dict) -> dict:
    """Bereinigt ein komplettes Metadaten-Dictionary aus externen Quellen.

    Erwartet das Format wie von OpenLibrary/Google Books:
    {
        "titel": "...",
        "autor": "...",
        "kategorien": [...],
        "beschreibung": "...",
        ...
    }

    Returns:
        Bereinigtes Dictionary. Entfernte Felder werden nicht zurueckgegeben.
    """
    bereinigt = {}

    for key, value in daten.items():
        if key == "kategorien" and isinstance(value, list):
            bereinigt[key] = bereinige_kategorien(value)
        elif key == "themen" and isinstance(value, list):
            bereinigt[key] = bereinige_kategorien(value)
        elif key == "tags" and isinstance(value, list):
            bereinigt[key] = bereinige_tags(value)
        elif key == "titel":
            bereinigt[key] = bereinige_titel(value) if isinstance(value, str) else value
        elif key == "autor":
            bereinigt[key] = bereinige_autor(value) if isinstance(value, str) else value
        elif key == "beschreibung" and isinstance(value, str):
            bereinigt[key] = bereinige_text(value)
        elif key == "verlag" and isinstance(value, str):
            bereinigt[key] = bereinige_text(value, 200)
        elif key == "sprache" and isinstance(value, str):
            bereinigt[key] = bereinige_text(value, 10)
        else:
            # Alles andere durchreichen
            bereinigt[key] = value

    return bereinigt


def _bereinige_einzelwert(text: str) -> str:
    """Bereinigt einen einzelnen String-Wert.

    - Entfernt fuehrende/nachfolgende Whitespace und Sonderzeichen
    - Normalisiert Unicode
    - Entfernt Steuerzeichen
    """
    if not text or not isinstance(text, str):
        return ""

    # Unicode normalisieren (NFC)
    text = unicodedata.normalize("NFC", text)

    # Steuerzeichen entfernen
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")

    # Whitespace normalisieren
    text = re.sub(r"\s+", " ", text).strip()

    # Fuehrende/nachfolgende Interpunktion entfernen
    text = text.strip(".-_:; ")

    return text
