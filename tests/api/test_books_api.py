"""API-Integrationstests fuer Buecher-Endpunkte."""

import pytest
from httpx import AsyncClient

from tests.api.conftest import buch_erstellen, kategorie_erstellen, sammlung_erstellen


# -- Authentifizierung --


@pytest.mark.asyncio
async def test_buecher_liste_ohne_token_gibt_401(client_ohne_auth: AsyncClient):
    """Anfrage ohne Bearer-Token wird mit 401 abgelehnt."""
    response = await client_ohne_auth.get("/api/books")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_buecher_liste_mit_falschem_token(client_ohne_auth: AsyncClient):
    """Anfrage mit falschem Token wird mit 401 abgelehnt."""
    response = await client_ohne_auth.get(
        "/api/books",
        headers={"Authorization": "Bearer falscher-token-xyz"},
    )
    assert response.status_code == 401


# -- Leere Liste --


@pytest.mark.asyncio
async def test_buecher_liste_leer(client: AsyncClient):
    """Leere Datenbank gibt eine leere Buecherliste zurueck."""
    response = await client.get("/api/books")
    assert response.status_code == 200
    data = response.json()
    assert data["buecher"] == []
    assert data["gesamt"] == 0
    assert data["seite"] == 1
    assert data["seiten_gesamt"] == 0


# -- Buch abrufen --


@pytest.mark.asyncio
async def test_buch_details_abrufen(client: AsyncClient, test_db):
    """Einzelnes Buch per ID abrufen."""
    buch_id = await buch_erstellen(test_db, hash="detail01", title="Detailbuch",
                                    author="Max Muster")
    response = await client.get(f"/api/books/{buch_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == buch_id
    assert data["title"] == "Detailbuch"
    assert data["author"] == "Max Muster"
    assert data["file_format"] == "pdf"
    assert data["isbn"] == "978-3-16-148410-0"
    assert isinstance(data["categories"], list)
    assert isinstance(data["authors"], list)


@pytest.mark.asyncio
async def test_buch_nicht_gefunden_gibt_404(client: AsyncClient):
    """Nicht existierende Buch-ID gibt 404 zurueck."""
    response = await client.get("/api/books/99999")
    assert response.status_code == 404
    assert "nicht gefunden" in response.json()["detail"]


# -- Buchliste mit Pagination --


@pytest.mark.asyncio
async def test_buecher_liste_paginiert(client: AsyncClient, test_db):
    """Pagination liefert korrekte Seitenaufteilung."""
    for i in range(5):
        await buch_erstellen(test_db, hash=f"pag{i:03d}",
                              title=f"Buch {i}", author=f"Autor {i}")

    # Erste Seite mit 2 pro Seite
    response = await client.get("/api/books?seite=1&pro_seite=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["buecher"]) == 2
    assert data["gesamt"] == 5
    assert data["seite"] == 1
    assert data["seiten_gesamt"] == 3

    # Letzte Seite
    response = await client.get("/api/books?seite=3&pro_seite=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["buecher"]) == 1


# -- Sortierung --


@pytest.mark.asyncio
async def test_buecher_sortierung_nach_titel(client: AsyncClient, test_db):
    """Buecher werden nach Titel sortiert (Standard: aufsteigend)."""
    await buch_erstellen(test_db, hash="sort_c", title="C-Programmierung")
    await buch_erstellen(test_db, hash="sort_a", title="Algorithmen")
    await buch_erstellen(test_db, hash="sort_b", title="Betriebssysteme")

    response = await client.get("/api/books?sortierung=titel&richtung=asc")
    assert response.status_code == 200
    titel = [b["title"] for b in response.json()["buecher"]]
    assert titel == sorted(titel)


@pytest.mark.asyncio
async def test_buecher_sortierung_absteigend(client: AsyncClient, test_db):
    """Buecher werden absteigend sortiert."""
    await buch_erstellen(test_db, hash="desc_a", title="Alpha")
    await buch_erstellen(test_db, hash="desc_z", title="Zeta")

    response = await client.get("/api/books?sortierung=titel&richtung=desc")
    assert response.status_code == 200
    titel = [b["title"] for b in response.json()["buecher"]]
    assert titel == sorted(titel, reverse=True)


# -- Filter --


@pytest.mark.asyncio
async def test_buecher_filter_nach_format(client: AsyncClient, test_db):
    """Filter nach Dateiformat liefert nur passende Buecher."""
    await buch_erstellen(test_db, hash="fmt_pdf", title="PDF-Buch", file_format="pdf")
    await buch_erstellen(test_db, hash="fmt_epub", title="EPUB-Buch", file_format="epub")

    response = await client.get("/api/books?format=epub")
    assert response.status_code == 200
    data = response.json()
    assert data["gesamt"] == 1
    assert data["buecher"][0]["title"] == "EPUB-Buch"


@pytest.mark.asyncio
async def test_buecher_filter_nach_kategorie(client: AsyncClient, test_db):
    """Filter nach Kategorie-ID liefert nur zugeordnete Buecher."""
    buch_id = await buch_erstellen(test_db, hash="kat_filter01", title="Kategorisiertes Buch")
    kat_id = await kategorie_erstellen(test_db, name="Informatik")
    await test_db.execute(
        "INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)",
        (buch_id, kat_id),
    )
    await test_db.commit()

    # Ohne Kategorie-Filter
    await buch_erstellen(test_db, hash="kat_filter02", title="Anderes Buch")

    response = await client.get(f"/api/books?kategorie={kat_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["gesamt"] == 1
    assert data["buecher"][0]["title"] == "Kategorisiertes Buch"


@pytest.mark.asyncio
async def test_buecher_filter_nach_sammlung(client: AsyncClient, test_db):
    """Filter nach Sammlungs-ID liefert nur zugeordnete Buecher."""
    samml_id = await sammlung_erstellen(test_db, name="Python-Regal")
    buch_id = await buch_erstellen(test_db, hash="samml_filter01", title="Sammlungsbuch")
    await test_db.execute(
        "UPDATE books SET sammlung_id = ? WHERE id = ?",
        (samml_id, buch_id),
    )
    await test_db.commit()

    await buch_erstellen(test_db, hash="samml_filter02", title="Ohne Sammlung")

    response = await client.get(f"/api/books?sammlung={samml_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["gesamt"] == 1
    assert data["buecher"][0]["title"] == "Sammlungsbuch"


# -- Buch aktualisieren --


@pytest.mark.asyncio
async def test_buch_aktualisieren(client: AsyncClient, test_db):
    """PATCH aktualisiert einzelne Felder eines Buches."""
    buch_id = await buch_erstellen(test_db, hash="update01", title="Alter Titel")

    response = await client.patch(
        f"/api/books/{buch_id}",
        json={"title": "Neuer Titel", "author": "Neue Autorin"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Neuer Titel"
    assert data["author"] == "Neue Autorin"


@pytest.mark.asyncio
async def test_buch_aktualisieren_ohne_felder_gibt_400(client: AsyncClient, test_db):
    """PATCH ohne Felder gibt 400 zurueck."""
    buch_id = await buch_erstellen(test_db, hash="update_empty", title="Bleibt gleich")

    response = await client.patch(f"/api/books/{buch_id}", json={})
    assert response.status_code == 400
    assert "Keine Felder" in response.json()["detail"]


@pytest.mark.asyncio
async def test_buch_aktualisieren_nicht_gefunden(client: AsyncClient):
    """PATCH auf nicht existierendes Buch gibt 404 zurueck."""
    response = await client.patch(
        "/api/books/99999",
        json={"title": "Geisterbuch"},
    )
    assert response.status_code == 404


# -- Buch loeschen --


@pytest.mark.asyncio
async def test_buch_loeschen(client: AsyncClient, test_db):
    """DELETE entfernt ein Buch aus der Datenbank."""
    buch_id = await buch_erstellen(test_db, hash="delete01", title="Wird geloescht")

    response = await client.delete(f"/api/books/{buch_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["geloescht"] is True
    assert data["id"] == buch_id

    # Sicherstellen, dass es wirklich weg ist
    response = await client.get(f"/api/books/{buch_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_buch_loeschen_nicht_gefunden(client: AsyncClient):
    """DELETE auf nicht existierendes Buch gibt 404 zurueck."""
    response = await client.delete("/api/books/99999")
    assert response.status_code == 404


# -- Relationen in der Liste --


@pytest.mark.asyncio
async def test_buch_listet_kategorien(client: AsyncClient, test_db):
    """Buecher in der Liste enthalten ihre Kategorien."""
    buch_id = await buch_erstellen(test_db, hash="rel01", title="Relationen-Buch")
    kat_id = await kategorie_erstellen(test_db, name="Wissenschaft")

    await test_db.execute(
        "INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)",
        (buch_id, kat_id),
    )
    await test_db.commit()

    response = await client.get("/api/books")
    assert response.status_code == 200
    buch = response.json()["buecher"][0]
    assert len(buch["categories"]) == 1
    assert buch["categories"][0]["name"] == "Wissenschaft"
