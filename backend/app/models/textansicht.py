"""Textansicht eines PDF: Seiten als Fließtext."""

from pydantic import BaseModel


class TextSeite(BaseModel):
    """Eine Dateiseite als Absätze; leer, wenn die Seite keine Textschicht hat (Scan, Bild)."""

    nr: int
    gedruckt: str = ""
    absaetze: list[str]


class TextSeitenAntwort(BaseModel):
    """Ein Ausschnitt der Seiten ab einer Dateiseite."""

    gesamt: int
    seiten: list[TextSeite]
