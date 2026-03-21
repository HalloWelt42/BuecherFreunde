"""Basisklasse für Buchprozessoren."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BookProcessingResult:
    """Ergebnis der Buchverarbeitung."""

    title: str = ""
    author: str = ""
    isbn: str = ""
    publisher: str = ""
    year: int | None = None
    language: str = ""
    description: str = ""
    page_count: int = 0
    fulltext: str = ""
    cover_data: bytes | None = None
    metadata_raw: dict = field(default_factory=dict)
    error: str = ""

    @property
    def fts_content(self) -> str:
        """Gibt den Text für den FTS-Index zurück (max 100.000 Zeichen)."""
        return self.fulltext[:100_000]


class BaseProcessor:
    """Basisklasse - jeder Prozessor implementiert process()."""

    def process(self, file_path: Path) -> BookProcessingResult:
        """Verarbeitet eine Buchdatei und gibt das Ergebnis zurück."""
        raise NotImplementedError
