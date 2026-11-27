"""ISBN in allen Schreibweisen: mit und ohne Striche, zehn oder dreizehn Stellen."""

from __future__ import annotations

import re

import isbnlib


def sauber(isbn: str) -> str:
    """Nur Ziffern (und ein X am Ende); leer, wenn es keine ISBN ist."""
    z = re.sub(r"[^0-9Xx]", "", isbn or "").upper()
    return z if re.fullmatch(r"\d{13}|\d{9}[\dX]", z) else ""


def gueltig(isbn: str) -> bool:
    """Eine ISBN mit stimmender Prüfziffer, zehn- oder dreizehnstellig (dreizehn nur mit 978 oder 979)."""
    z = sauber(isbn)
    return bool(z) and (isbnlib.is_isbn13(z) if len(z) == 13 else isbnlib.is_isbn10(z))


def dreizehn(isbn: str) -> str:
    z = sauber(isbn)
    return z if len(z) == 13 else (isbnlib.to_isbn13(z) or "") if z else ""


def zehn(isbn: str) -> str:
    z = sauber(isbn)
    return z if len(z) == 10 else (isbnlib.to_isbn10(z) or "") if z else ""


def formen(isbn: str) -> list[str]:
    """Beide Längen ohne Striche, die dreizehnstellige zuerst."""
    return [f for f in dict.fromkeys((dreizehn(isbn), zehn(isbn), sauber(isbn))) if f]


def mit_strichen(isbn: str) -> str:
    z = sauber(isbn)
    return (isbnlib.mask(z) or "") if z and not isbnlib.notisbn(z) else ""


def gleich(a: str, b: str) -> bool:
    return bool(a and b) and bool(set(formen(a)) & set(formen(b)))


def deutschsprachig(isbn: str) -> bool:
    """Sprachgruppe 3: Deutschland, Österreich, deutschsprachige Schweiz."""
    return dreizehn(isbn).startswith("9783")
