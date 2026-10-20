"""Seiten eines Volltexts: eine Regel für Leser, Suche im Buch und den Anbieterweg für Fundus.

fulltext.txt trennt Seiten mit Seitenvorschub; fehlt er, wird gleichmäßig nach der Seitenzahl aus der Datenbank
geteilt (mindestens 500 Zeichen je Seite). Seite N ist die N-te Seite der Datei, wie im Leser (?page=N)."""


def seiten_aus(text: str, page_count: int | None) -> list[str]:
    if not text:
        return []
    if "\f" in text:
        return text.split("\f")
    je_seite = max(len(text) // (page_count or 1), 500)
    return [text[i:i + je_seite] for i in range(0, len(text), je_seite)]
