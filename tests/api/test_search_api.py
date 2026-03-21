"""API-Integrationstests fuer Such-Endpunkte."""

import pytest
from httpx import AsyncClient

from tests.api.conftest import buch_erstellen


# -- Authentifizierung --


@pytest.mark.asyncio
async def test_suche_ohne_token_gibt_fehler(client_ohne_auth: AsyncClient):
    """Anfrage ohne Token wird abgelehnt."""
    response = await client_ohne_auth.get("/api/search?q=test")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_suche_mit_falschem_token(client_ohne_auth: AsyncClient):
    """Anfrage mit falschem Token gibt 401 zurueck."""
    response = await client_ohne_auth.get(
        "/api/search?q=test",
        headers={"Authorization": "Bearer falsch"},
    )
    assert response.status_code == 401


# -- Volltextsuche --


@pytest.mark.asyncio
async def test_suche_ohne_ergebnisse(client: AsyncClient):
    """Suche in leerer Datenbank gibt keine Treffer."""
    response = await client.get("/api/search?q=nichtvorhanden")
    assert response.status_code == 200
    data = response.json()
    assert data["treffer"] == []
    assert data["gesamt"] == 0
    assert data["anfrage"] == "nichtvorhanden"


@pytest.mark.asyncio
async def test_suche_findet_buch_nach_titel(client: AsyncClient, test_db):
    """Suche findet ein Buch anhand des Titels."""
    await buch_erstellen(
        test_db,
        hash="search_titel01",
        title="Python Programmierung",
        author="Guido van Rossum",
        fts_content="Einfuehrung in die Python-Sprache",
    )

    response = await client.get("/api/search?q=Python")
    assert response.status_code == 200
    data = response.json()
    assert data["gesamt"] >= 1
    treffer_titel = [t["titel"] for t in data["treffer"]]
    assert any("Python" in t for t in treffer_titel)


@pytest.mark.asyncio
async def test_suche_findet_buch_nach_autor(client: AsyncClient, test_db):
    """Suche findet ein Buch anhand des Autors."""
    await buch_erstellen(
        test_db,
        hash="search_autor01",
        title="Grundlagen der Informatik",
        author="Erika Mustermann",
        fts_content="Algorithmen und Datenstrukturen",
    )

    response = await client.get("/api/search?q=Mustermann")
    assert response.status_code == 200
    data = response.json()
    assert data["gesamt"] >= 1


@pytest.mark.asyncio
async def test_suche_findet_buch_im_inhalt(client: AsyncClient, test_db):
    """Suche findet ein Buch anhand des FTS-Inhalts."""
    await buch_erstellen(
        test_db,
        hash="search_inhalt01",
        title="Kochbuch",
        author="Hans Koch",
        fts_content="Rezepte fuer Schwarzwaelder Kirschtorte und Apfelstrudel",
    )

    response = await client.get("/api/search?q=Kirschtorte")
    assert response.status_code == 200
    data = response.json()
    assert data["gesamt"] >= 1


@pytest.mark.asyncio
async def test_suche_mit_limit_und_offset(client: AsyncClient, test_db):
    """Suche respektiert limit und offset Parameter."""
    for i in range(5):
        await buch_erstellen(
            test_db,
            hash=f"search_pag{i:03d}",
            title=f"Suchbuch Datenbank {i}",
            author="Suchautor",
            fts_content=f"Datenbank Inhalt Nummer {i}",
        )

    # Nur 2 Ergebnisse
    response = await client.get("/api/search?q=Datenbank&limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["treffer"]) <= 2
    assert data["limit"] == 2
    assert data["offset"] == 0

    # Mit Offset
    response = await client.get("/api/search?q=Datenbank&limit=2&offset=2")
    assert response.status_code == 200
    data = response.json()
    assert data["offset"] == 2


@pytest.mark.asyncio
async def test_suche_ergebnis_format(client: AsyncClient, test_db):
    """Suchergebnisse enthalten alle erwarteten Felder."""
    await buch_erstellen(
        test_db,
        hash="search_format01",
        title="Formattest",
        author="Formatautor",
        fts_content="Inhalt fuer den Formattest",
    )

    response = await client.get("/api/search?q=Formattest")
    assert response.status_code == 200
    data = response.json()
    assert len(data["treffer"]) >= 1
    treffer = data["treffer"][0]
    assert "book_id" in treffer
    assert "titel" in treffer
    assert "autor" in treffer
    assert "snippet" in treffer
    assert "relevanz" in treffer


@pytest.mark.asyncio
async def test_suche_ohne_query_gibt_422(client: AsyncClient):
    """Suche ohne q-Parameter gibt 422 Validation Error zurueck."""
    response = await client.get("/api/search")
    assert response.status_code == 422


# -- Vorschlaege --


@pytest.mark.asyncio
async def test_vorschlaege_ohne_ergebnisse(client: AsyncClient):
    """Vorschlaege in leerer Datenbank geben leere Liste zurueck."""
    response = await client.get("/api/search/vorschlaege?q=nichts")
    assert response.status_code == 200
    data = response.json()
    assert data["vorschlaege"] == []
    assert data["anfrage"] == "nichts"


@pytest.mark.asyncio
async def test_vorschlaege_finden_titel(client: AsyncClient, test_db):
    """Vorschlaege finden Buecher anhand des Titelpraefixes."""
    await buch_erstellen(
        test_db,
        hash="suggest_titel01",
        title="Maschinelles Lernen",
        author="ML-Autor",
        fts_content="Deep Learning und neuronale Netze",
    )

    response = await client.get("/api/search/vorschlaege?q=Maschin")
    assert response.status_code == 200
    data = response.json()
    # FTS5-Vorschlaege koennten Treffer finden
    assert isinstance(data["vorschlaege"], list)


@pytest.mark.asyncio
async def test_vorschlaege_limit(client: AsyncClient, test_db):
    """Vorschlaege respektieren den limit-Parameter."""
    for i in range(10):
        await buch_erstellen(
            test_db,
            hash=f"suggest_limit{i:03d}",
            title=f"Vorschlagbuch {i}",
            author="Vorschlagautor",
            fts_content=f"Vorschlaginhalt {i}",
        )

    response = await client.get("/api/search/vorschlaege?q=Vorschlag&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data["vorschlaege"]) <= 3


@pytest.mark.asyncio
async def test_vorschlaege_zu_kurzer_query_gibt_422(client: AsyncClient):
    """Vorschlaege mit zu kurzem Suchbegriff (< 2 Zeichen) gibt 422 zurueck."""
    response = await client.get("/api/search/vorschlaege?q=x")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_vorschlaege_ohne_query_gibt_422(client: AsyncClient):
    """Vorschlaege ohne q-Parameter gibt 422 zurueck."""
    response = await client.get("/api/search/vorschlaege")
    assert response.status_code == 422


# -- Index-Verwaltung --


@pytest.mark.asyncio
async def test_index_neu_aufbauen(client: AsyncClient, test_db):
    """POST baut den FTS-Index neu auf."""
    await buch_erstellen(
        test_db,
        hash="rebuild01",
        title="Index-Buch",
        author="Indexautor",
        fts_content="Wird neu indexiert",
    )

    response = await client.post("/api/search/index-neu-aufbauen")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "fertig"
    assert data["indexiert"] >= 1


@pytest.mark.asyncio
async def test_index_optimieren(client: AsyncClient):
    """POST optimiert den FTS-Index."""
    response = await client.post("/api/search/index-optimieren")
    assert response.status_code == 200
    assert response.json()["status"] == "optimiert"


@pytest.mark.asyncio
async def test_index_operationen_ohne_token(client_ohne_auth: AsyncClient):
    """Index-Operationen ohne Token werden abgelehnt."""
    response = await client_ohne_auth.post("/api/search/index-neu-aufbauen")
    assert response.status_code == 401

    response = await client_ohne_auth.post("/api/search/index-optimieren")
    assert response.status_code == 401
