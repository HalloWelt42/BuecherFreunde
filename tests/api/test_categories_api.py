"""API-Integrationstests fuer Kategorien-Endpunkte."""

import pytest
from httpx import AsyncClient

from tests.api.conftest import buch_erstellen, kategorie_erstellen


# -- Authentifizierung --


@pytest.mark.asyncio
async def test_kategorien_ohne_token_gibt_fehler(client_ohne_auth: AsyncClient):
    """Anfrage ohne Token wird abgelehnt."""
    response = await client_ohne_auth.get("/api/categories")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_kategorien_mit_falschem_token(client_ohne_auth: AsyncClient):
    """Anfrage mit falschem Token gibt 401 zurueck."""
    response = await client_ohne_auth.get(
        "/api/categories",
        headers={"Authorization": "Bearer ungueltig"},
    )
    assert response.status_code == 401


# -- Leere Liste --


@pytest.mark.asyncio
async def test_kategorien_liste_leer(client: AsyncClient):
    """Leere Datenbank gibt eine leere Kategorienliste zurueck."""
    response = await client.get("/api/categories")
    assert response.status_code == 200
    assert response.json() == []


# -- Kategorie erstellen --


@pytest.mark.asyncio
async def test_kategorie_erstellen(client: AsyncClient):
    """POST erstellt eine neue Kategorie."""
    response = await client.post(
        "/api/categories",
        json={"name": "Belletristik"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Belletristik"
    assert data["slug"] == "belletristik"
    assert data["parent_id"] is None
    assert "id" in data


@pytest.mark.asyncio
async def test_kategorie_mit_elternkategorie_erstellen(client: AsyncClient):
    """POST erstellt eine Unterkategorie mit parent_id."""
    # Elternkategorie erstellen
    response = await client.post(
        "/api/categories",
        json={"name": "Sachbuch"},
    )
    parent_id = response.json()["id"]

    # Unterkategorie erstellen
    response = await client.post(
        "/api/categories",
        json={"name": "Wissenschaft", "parent_id": parent_id},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["parent_id"] == parent_id
    assert data["name"] == "Wissenschaft"


@pytest.mark.asyncio
async def test_kategorie_mit_ungueltiger_elternkategorie(client: AsyncClient):
    """POST mit nicht existierender parent_id gibt 404 zurueck."""
    response = await client.post(
        "/api/categories",
        json={"name": "Waise", "parent_id": 99999},
    )
    assert response.status_code == 404
    assert "Elternkategorie" in response.json()["detail"]


@pytest.mark.asyncio
async def test_kategorie_slug_eindeutigkeit(client: AsyncClient):
    """Doppelte Slug-Namen werden automatisch nummeriert."""
    await client.post("/api/categories", json={"name": "Roman"})
    response = await client.post("/api/categories", json={"name": "Roman"})
    assert response.status_code == 201
    data = response.json()
    # Der zweite Slug bekommt eine Nummer angehaengt
    assert data["slug"].startswith("roman")
    assert data["slug"] != "roman"


# -- Baumstruktur --


@pytest.mark.asyncio
async def test_kategorien_baumstruktur(client: AsyncClient):
    """GET gibt Kategorien als verschachtelte Baumstruktur zurueck."""
    # Elternkategorie
    response = await client.post(
        "/api/categories",
        json={"name": "Literatur"},
    )
    parent_id = response.json()["id"]

    # Kindkategorien
    await client.post(
        "/api/categories",
        json={"name": "Lyrik", "parent_id": parent_id},
    )
    await client.post(
        "/api/categories",
        json={"name": "Prosa", "parent_id": parent_id},
    )

    response = await client.get("/api/categories")
    assert response.status_code == 200
    tree = response.json()

    # Es sollte nur ein Root-Element geben
    assert len(tree) == 1
    assert tree[0]["name"] == "Literatur"
    assert len(tree[0]["kinder"]) == 2
    kindernamen = [k["name"] for k in tree[0]["kinder"]]
    assert "Lyrik" in kindernamen
    assert "Prosa" in kindernamen


@pytest.mark.asyncio
async def test_kategorien_mit_buchanzahl(client: AsyncClient, test_db):
    """Kategorien enthalten die Anzahl zugeordneter Buecher."""
    kat_id = await kategorie_erstellen(test_db, name="Technik")
    buch_id = await buch_erstellen(test_db, hash="kat_count01", title="Technikbuch")
    await test_db.execute(
        "INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)",
        (buch_id, kat_id),
    )
    await test_db.commit()

    response = await client.get("/api/categories")
    assert response.status_code == 200
    kategorien = response.json()
    technik = next(k for k in kategorien if k["name"] == "Technik")
    assert technik["buch_anzahl"] == 1


# -- Kategorie aktualisieren --


@pytest.mark.asyncio
async def test_kategorie_aktualisieren(client: AsyncClient):
    """PATCH aendert den Namen und Slug einer Kategorie."""
    response = await client.post(
        "/api/categories",
        json={"name": "Alter Name"},
    )
    kat_id = response.json()["id"]

    response = await client.patch(
        f"/api/categories/{kat_id}",
        json={"name": "Neuer Name"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Neuer Name"
    assert data["slug"] == "neuer-name"


@pytest.mark.asyncio
async def test_kategorie_aktualisieren_ohne_felder(client: AsyncClient):
    """PATCH ohne Felder gibt 400 zurueck."""
    response = await client.post(
        "/api/categories",
        json={"name": "Unveraendert"},
    )
    kat_id = response.json()["id"]

    response = await client.patch(f"/api/categories/{kat_id}", json={})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_kategorie_aktualisieren_nicht_gefunden(client: AsyncClient):
    """PATCH auf nicht existierende Kategorie gibt 404 zurueck."""
    response = await client.patch(
        "/api/categories/99999",
        json={"name": "Geisterkategorie"},
    )
    assert response.status_code == 404


# -- Kategorie loeschen --


@pytest.mark.asyncio
async def test_kategorie_loeschen(client: AsyncClient):
    """DELETE entfernt eine Kategorie."""
    response = await client.post(
        "/api/categories",
        json={"name": "Wird geloescht"},
    )
    kat_id = response.json()["id"]

    response = await client.delete(f"/api/categories/{kat_id}")
    assert response.status_code == 200
    assert response.json()["geloescht"] is True

    # Liste muss jetzt leer sein
    response = await client.get("/api/categories")
    assert response.json() == []


@pytest.mark.asyncio
async def test_kategorie_loeschen_verschiebt_kinder(client: AsyncClient):
    """Beim Loeschen einer Kategorie werden Kinder auf Root-Ebene verschoben."""
    # Elternkategorie
    response = await client.post(
        "/api/categories",
        json={"name": "Eltern"},
    )
    parent_id = response.json()["id"]

    # Kindkategorie
    response = await client.post(
        "/api/categories",
        json={"name": "Kind", "parent_id": parent_id},
    )
    child_id = response.json()["id"]

    # Elternkategorie loeschen
    await client.delete(f"/api/categories/{parent_id}")

    # Kind sollte jetzt auf Root-Ebene sein
    response = await client.get("/api/categories")
    tree = response.json()
    assert len(tree) == 1
    assert tree[0]["name"] == "Kind"
    assert tree[0]["parent_id"] is None


@pytest.mark.asyncio
async def test_kategorie_loeschen_nicht_gefunden(client: AsyncClient):
    """DELETE auf nicht existierende Kategorie gibt 404 zurueck."""
    response = await client.delete("/api/categories/99999")
    assert response.status_code == 404


# -- Buch-Zuordnung --


@pytest.mark.asyncio
async def test_buch_kategorien_zuordnen(client: AsyncClient, test_db):
    """POST ordnet einem Buch Kategorien zu."""
    buch_id = await buch_erstellen(test_db, hash="zuordnung01", title="Zuordnungsbuch")
    kat1_id = await kategorie_erstellen(test_db, name="Kategorie A")
    kat2_id = await kategorie_erstellen(test_db, name="Kategorie B")

    response = await client.post(
        f"/api/categories/{buch_id}/zuordnen",
        json=[kat1_id, kat2_id],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["book_id"] == buch_id
    assert set(data["kategorien"]) == {kat1_id, kat2_id}


@pytest.mark.asyncio
async def test_buch_kategorien_zuordnen_ersetzt_bestehende(client: AsyncClient, test_db):
    """Neue Zuordnung ersetzt die bestehenden Kategorien."""
    buch_id = await buch_erstellen(test_db, hash="zuordnung02", title="Umzuordnen")
    kat1_id = await kategorie_erstellen(test_db, name="Erste Kat")
    kat2_id = await kategorie_erstellen(test_db, name="Zweite Kat")

    # Erste Zuordnung
    await client.post(f"/api/categories/{buch_id}/zuordnen", json=[kat1_id])

    # Neue Zuordnung (ersetzt)
    response = await client.post(
        f"/api/categories/{buch_id}/zuordnen",
        json=[kat2_id],
    )
    assert response.status_code == 200
    assert response.json()["kategorien"] == [kat2_id]


@pytest.mark.asyncio
async def test_buch_kategorien_zuordnen_buch_nicht_gefunden(client: AsyncClient):
    """Zuordnung auf nicht existierendes Buch gibt 404 zurueck."""
    response = await client.post(
        "/api/categories/99999/zuordnen",
        json=[1],
    )
    assert response.status_code == 404
