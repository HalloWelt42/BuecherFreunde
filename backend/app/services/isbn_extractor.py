"""ISBN-Extraktion aus Buchtext mit mehreren Strategien.

Durchsucht die ersten und letzten Seiten eines Textes nach ISBN-10 und ISBN-13
Mustern. Validiert gefundene Kandidaten mit Prüfsummen.
"""

import re
import logging

logger = logging.getLogger("buecherfreunde.isbn")

# ISBN-13: 978 oder 979, gefolgt von 10 Ziffern (mit optionalen Trennzeichen)
ISBN_13_PATTERN = re.compile(
    r"(?:ISBN[-:\s]*)?(?:97[89])[-\s]?\d[-\s]?\d{2}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d"
)

# ISBN-10: 10 Ziffern (letzte kann X sein), mit optionalen Trennzeichen
ISBN_10_PATTERN = re.compile(
    r"(?:ISBN[-:\s]*)?\d[-\s]?\d{2}[-\s]?\d{3}[-\s]?\d{3}[-\s]?[\dXx]"
)

# Einfaches Muster: "ISBN" gefolgt von Ziffern mit Trennzeichen
ISBN_LABELED_PATTERN = re.compile(
    r"ISBN[-:\s]*(?:13|10)?[-:\s]*([\d][\d\s-]{8,16}[\dXx])",
    re.IGNORECASE,
)


def validate_isbn_13(isbn: str) -> bool:
    """Prüft die ISBN-13 Prüfsumme."""
    if len(isbn) != 13 or not isbn.isdigit():
        return False
    total = sum(
        int(d) * (1 if i % 2 == 0 else 3)
        for i, d in enumerate(isbn)
    )
    return total % 10 == 0


def validate_isbn_10(isbn: str) -> bool:
    """Prüft die ISBN-10 Prüfsumme."""
    if len(isbn) != 10:
        return False
    if not isbn[:9].isdigit():
        return False
    if isbn[9] not in "0123456789Xx":
        return False
    total = 0
    for i, ch in enumerate(isbn[:9]):
        total += int(ch) * (10 - i)
    check = isbn[9].upper()
    total += 10 if check == "X" else int(check)
    return total % 11 == 0


def clean_isbn(raw: str) -> str:
    """Entfernt Trennzeichen und Leerzeichen aus einem ISBN-String."""
    return raw.replace("-", "").replace(" ", "").replace("\u2010", "").replace("\u2011", "").strip()


def validate_isbn(isbn: str) -> bool:
    """Validiert eine bereinigte ISBN (10 oder 13)."""
    if len(isbn) == 13:
        return validate_isbn_13(isbn)
    if len(isbn) == 10:
        return validate_isbn_10(isbn)
    return False


def extract_isbns_from_text(text: str) -> list[str]:
    """Extrahiert alle gültigen ISBNs aus einem Text.

    Returns:
        Liste validierter ISBNs, ISBN-13 bevorzugt, dedupliziert.
    """
    candidates = set()

    # Strategie 1: Explizit markierte ISBNs ("ISBN: ...")
    for match in ISBN_LABELED_PATTERN.finditer(text):
        raw = clean_isbn(match.group(1))
        if validate_isbn(raw):
            candidates.add(raw)

    # Strategie 2: ISBN-13 Muster (978/979...)
    for match in ISBN_13_PATTERN.finditer(text):
        raw = clean_isbn(match.group())
        # "ISBN" Präfix entfernen falls vorhanden
        raw = re.sub(r"^ISBN[-:\s]*", "", raw, flags=re.IGNORECASE)
        raw = clean_isbn(raw)
        if validate_isbn(raw):
            candidates.add(raw)

    # Strategie 3: ISBN-10 Muster
    for match in ISBN_10_PATTERN.finditer(text):
        raw = clean_isbn(match.group())
        raw = re.sub(r"^ISBN[-:\s]*", "", raw, flags=re.IGNORECASE)
        raw = clean_isbn(raw)
        if validate_isbn(raw):
            candidates.add(raw)

    # ISBN-13 bevorzugen, dann ISBN-10
    isbn_13s = sorted(c for c in candidates if len(c) == 13)
    isbn_10s = sorted(c for c in candidates if len(c) == 10)

    return isbn_13s + isbn_10s


def extract_isbn_from_pages(page_texts: list[str], scan_pages: int = 10) -> str:
    """Durchsucht die ersten und letzten Seiten nach ISBNs.

    Args:
        page_texts: Liste von Texten pro Seite/Kapitel.
        scan_pages: Anzahl der Seiten am Anfang und Ende die durchsucht werden.

    Returns:
        Beste gefundene ISBN (ISBN-13 bevorzugt) oder leerer String.
    """
    if not page_texts:
        return ""

    # Erste N Seiten und letzte N Seiten zusammenfügen
    first_pages = page_texts[:scan_pages]
    last_pages = page_texts[-scan_pages:] if len(page_texts) > scan_pages else []

    # Duplikate vermeiden wenn das Buch weniger als 2*scan_pages Seiten hat
    scan_text = "\n".join(first_pages)
    if last_pages:
        scan_text += "\n" + "\n".join(last_pages)

    isbns = extract_isbns_from_text(scan_text)

    if isbns:
        logger.info("ISBN gefunden: %s (aus %d Kandidaten)", isbns[0], len(isbns))
        return isbns[0]

    return ""


def extract_isbn_from_fulltext(fulltext: str, char_limit: int = 20000) -> str:
    """Durchsucht die ersten und letzten Zeichen des Volltexts nach ISBNs.

    Fallback wenn keine seitenweise Aufteilung verfügbar ist.

    Args:
        fulltext: Gesamter Text des Buches.
        char_limit: Anzahl Zeichen am Anfang/Ende die durchsucht werden.

    Returns:
        Beste gefundene ISBN oder leerer String.
    """
    if not fulltext:
        return ""

    text_start = fulltext[:char_limit]
    text_end = fulltext[-char_limit:] if len(fulltext) > char_limit else ""

    scan_text = text_start + "\n" + text_end
    isbns = extract_isbns_from_text(scan_text)

    if isbns:
        logger.info("ISBN im Volltext gefunden: %s", isbns[0])
        return isbns[0]

    return ""
