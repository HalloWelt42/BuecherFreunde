"""Tests fuer die FTS5-Volltextsuche.

Testet Suche, Snippets, Trefferanzahl, Vorschlaege und Index-Verwaltung
gegen eine echte SQLite-Datenbank mit FTS5.
"""

import hashlib

import pytest
import pytest_asyncio

from backend.app.core.database import Database
from backend.app.services.search import (
    SearchResult,
    search_books,
    search_count,
    suggest,
    rebuild_index,
    optimize_index,
)


# ---------------------------------------------------------------------------
# Hilfsfunktion: search-Modul mit Test-DB verbinden
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def such_db(test_db_mit_daten, monkeypatch):
    """Patcht das db-Objekt im search-Modul auf die Testdatenbank."""
    monkeypatch.setattr("backend.app.services.search.db", test_db_mit_daten)
    yield test_db_mit_daten


# ---------------------------------------------------------------------------
# Suche
# ---------------------------------------------------------------------------

class TestBuecherSuche:
    """Tests fuer die Hauptsuchfunktion."""

    @pytest.mark.asyncio
    async def test_einfache_suche_python(self, such_db):
        """Suche nach 'Python' muss passende Buecher finden."""
        ergebnisse = await search_books("Python")
        assert len(ergebnisse) >= 1
        titel = [e.title for e in ergebnisse]
        assert any("Python" in t for t in titel)

    @pytest.mark.asyncio
    async def test_suche_ergebnis_ist_search_result(self, such_db):
        """Jedes Ergebnis muss ein SearchResult-Objekt sein."""
        ergebnisse = await search_books("Python")
        assert len(ergebnisse) > 0
        for e in ergebnisse:
            assert isinstance(e, SearchResult)
            assert isinstance(e.book_id, int)
            assert isinstance(e.title, str)
            assert isinstance(e.author, str)
            assert isinstance(e.relevance, float)

    @pytest.mark.asyncio
    async def test_suche_mit_snippet(self, such_db):
        """Suchergebnisse muessen Snippets mit Markierungen enthalten."""
        ergebnisse = await search_books("Programmiersprache")
        assert len(ergebnisse) >= 1
        # Snippet muss <mark>-Tags enthalten
        hat_markierung = any("<mark>" in e.snippet for e in ergebnisse)
        assert hat_markierung

    @pytest.mark.asyncio
    async def test_suche_linux(self, such_db):
        """Suche nach 'Linux' muss das Linux-Buch finden."""
        ergebnisse = await search_books("Linux")
        assert len(ergebnisse) >= 1
        titel = [e.title for e in ergebnisse]
        assert any("Linux" in t for t in titel)

    @pytest.mark.asyncio
    async def test_suche_ohne_treffer(self, such_db):
        """Suche nach einem nicht vorhandenen Begriff muss leere Liste ergeben."""
        ergebnisse = await search_books("Quantenphysik")
        assert ergebnisse == []

    @pytest.mark.asyncio
    async def test_suche_leerer_string(self, such_db):
        """Leerer Suchstring muss leere Liste ergeben."""
        ergebnisse = await search_books("")
        assert ergebnisse == []

    @pytest.mark.asyncio
    async def test_suche_nur_leerzeichen(self, such_db):
        """Suchstring mit nur Leerzeichen muss leere Liste ergeben."""
        ergebnisse = await search_books("   ")
        assert ergebnisse == []

    @pytest.mark.asyncio
    async def test_suche_mit_limit(self, such_db):
        """Das Limit muss die Anzahl der Ergebnisse begrenzen."""
        ergebnisse = await search_books("Python", limit=1)
        assert len(ergebnisse) <= 1

    @pytest.mark.asyncio
    async def test_suche_mit_offset(self, such_db):
        """Der Offset muss Ergebnisse ueberspringen."""
        alle = await search_books("Python", limit=10)
        mit_offset = await search_books("Python", limit=10, offset=1)
        if len(alle) > 1:
            assert len(mit_offset) == len(alle) - 1

    @pytest.mark.asyncio
    async def test_praefix_suche(self, such_db):
        """Praefixsuche mit Stern muss funktionieren."""
        ergebnisse = await search_books("Pyth*")
        assert len(ergebnisse) >= 1


# ---------------------------------------------------------------------------
# Trefferanzahl
# ---------------------------------------------------------------------------

class TestTrefferanzahl:
    """Tests fuer die Zaehlung der Suchergebnisse."""

    @pytest.mark.asyncio
    async def test_anzahl_python(self, such_db):
        """Trefferanzahl fuer 'Python' muss groesser 0 sein."""
        anzahl = await search_count("Python")
        assert anzahl >= 1

    @pytest.mark.asyncio
    async def test_anzahl_kein_treffer(self, such_db):
        """Trefferanzahl fuer unbekannten Begriff muss 0 sein."""
        anzahl = await search_count("Quantenphysik")
        assert anzahl == 0

    @pytest.mark.asyncio
    async def test_anzahl_leerer_string(self, such_db):
        """Leerer String muss 0 Treffer ergeben."""
        anzahl = await search_count("")
        assert anzahl == 0

    @pytest.mark.asyncio
    async def test_anzahl_stimmt_mit_suche_ueberein(self, such_db):
        """Trefferanzahl muss mit der Laenge der Suchergebnisse uebereinstimmen."""
        query = "Python"
        ergebnisse = await search_books(query, limit=100)
        anzahl = await search_count(query)
        assert anzahl == len(ergebnisse)


# ---------------------------------------------------------------------------
# Vorschlaege (Autovervollstaendigung)
# ---------------------------------------------------------------------------

class TestVorschlaege:
    """Tests fuer die Autovervollstaendigung."""

    @pytest.mark.asyncio
    async def test_vorschlaege_fuer_python(self, such_db):
        """Vorschlaege fuer 'Pyth' muessen Python-Buecher enthalten."""
        ergebnisse = await suggest("Pyth")
        assert len(ergebnisse) >= 1

    @pytest.mark.asyncio
    async def test_vorschlag_format(self, such_db):
        """Vorschlaege muessen id, titel, autor und typ enthalten."""
        ergebnisse = await suggest("Pyth")
        assert len(ergebnisse) >= 1
        for v in ergebnisse:
            assert "id" in v
            assert "titel" in v
            assert "autor" in v
            assert "typ" in v

    @pytest.mark.asyncio
    async def test_vorschlag_typ_titel(self, such_db):
        """Titel-Treffer muessen den Typ 'titel' haben."""
        ergebnisse = await suggest("Pyth")
        titel_treffer = [v for v in ergebnisse if v["typ"] == "titel"]
        assert len(titel_treffer) >= 1

    @pytest.mark.asyncio
    async def test_vorschlaege_zu_kurzer_string(self, such_db):
        """Zu kurze Eingabe (< 2 Zeichen) muss leere Liste ergeben."""
        ergebnisse = await suggest("P")
        assert ergebnisse == []

    @pytest.mark.asyncio
    async def test_vorschlaege_leerer_string(self, such_db):
        """Leerer String muss leere Liste ergeben."""
        ergebnisse = await suggest("")
        assert ergebnisse == []

    @pytest.mark.asyncio
    async def test_vorschlaege_limit(self, such_db):
        """Das Limit muss die Anzahl der Vorschlaege begrenzen."""
        ergebnisse = await suggest("Pyth", limit=1)
        assert len(ergebnisse) <= 1

    @pytest.mark.asyncio
    async def test_vorschlaege_nach_autor(self, such_db):
        """Vorschlaege muessen auch Autoren-Treffer liefern."""
        ergebnisse = await suggest("Muster")
        # Mustermann sollte gefunden werden
        assert len(ergebnisse) >= 1


# ---------------------------------------------------------------------------
# Index-Verwaltung
# ---------------------------------------------------------------------------

class TestIndexVerwaltung:
    """Tests fuer Neuaufbau und Optimierung des FTS-Index."""

    @pytest.mark.asyncio
    async def test_index_neu_aufbauen(self, such_db):
        """rebuild_index() muss die korrekte Anzahl Buecher zurueckgeben."""
        anzahl = await rebuild_index()
        assert anzahl == 3  # 3 Testbuecher in der Fixture

    @pytest.mark.asyncio
    async def test_suche_nach_neuaufbau(self, such_db):
        """Nach Neuaufbau muss die Suche weiterhin funktionieren."""
        await rebuild_index()
        ergebnisse = await search_books("Python")
        assert len(ergebnisse) >= 1

    @pytest.mark.asyncio
    async def test_index_optimieren(self, such_db):
        """optimize_index() muss ohne Fehler durchlaufen."""
        # Darf keine Exception ausloesen
        await optimize_index()


# ---------------------------------------------------------------------------
# SearchResult Datenklasse
# ---------------------------------------------------------------------------

class TestSearchResultDatenklasse:
    """Tests fuer die SearchResult-Datenklasse."""

    def test_search_result_erstellen(self):
        """Ein SearchResult muss korrekt erstellt werden koennen."""
        ergebnis = SearchResult(
            book_id=1,
            title="Testbuch",
            author="Testautor",
            snippet="Ein <mark>Test</mark>...",
            relevance=0.85,
        )
        assert ergebnis.book_id == 1
        assert ergebnis.title == "Testbuch"
        assert ergebnis.author == "Testautor"
        assert ergebnis.relevance == 0.85

    def test_search_result_felder(self):
        """SearchResult muss alle erwarteten Felder haben."""
        ergebnis = SearchResult(
            book_id=0, title="", author="", snippet="", relevance=0.0
        )
        assert hasattr(ergebnis, "book_id")
        assert hasattr(ergebnis, "title")
        assert hasattr(ergebnis, "author")
        assert hasattr(ergebnis, "snippet")
        assert hasattr(ergebnis, "relevance")
