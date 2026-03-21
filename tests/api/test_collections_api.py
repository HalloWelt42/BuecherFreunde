"""API-Integrationstests fuer Sammlungen-Endpunkte."""

import pytest
from httpx import AsyncClient

from tests.api.conftest import buch_erstellen, sammlung_erstellen


# -- Authentifizierung --


@pytest.mark.asyncio
async def test_sammlungen_ohne_token_gibt_fehler(client_ohne_auth: AsyncClient):
    """Anfrage ohne Token wird abgelehnt."""
    response = await client_ohne_auth.get("/api/collections")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sammlungen_mit_falschem_token(client_ohne_auth: AsyncClient):
    """Anfrage mit falschem Token gibt 401 zurueck."""
    response = await client_ohne_auth.get(
        "/api/collections",
        headers={"Authorization": "Bearer komplett-falsch"},
    )
    assert response.status_code == 401


# -- Leere Liste --


@pytest.mark.asyncio
async def test_sammlungen_liste_leer(client: AsyncClient):
    """Leere Datenbank gibt eine leere Sammlungsliste zurueck."""
    response = await client.get("/api/collections")
    assert response.status_code == 200
    assert response.json() == []


# -- Sammlung erstellen --


@pytest.mark.asyncio
async def test_sammlung_erstellen(client: AsyncClient):
    """POST erstellt eine neue Sammlung."""
    response = await client.post(
        "/api/collections",
        json={"name": "Meine Reihe", "description": "Eine Buchreihe", "color": "#ff5733"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Meine Reihe"
    assert data["description"] == "Eine Buchreihe"
    assert data["color"] == "#ff5733"
    assert "id" in data


@pytest.mark.asyncio
async def test_sammlung_erstellen_mit_standardwerten(client: AsyncClient):
    """POST ohne optionale Felder verwendet Standardwerte."""
    response = await client.post(
        "/api/collections",
        json={"name": "Nur Name"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Nur Name"
    assert data["description"] == ""
    assert data["color"] == "#2563eb"


# -- Sammlungen-Liste mit Buchanzahl --


@pytest.mark.asyncio
async def test_sammlungen_mit_buchanzahl(client: AsyncClient, test_db):
    """Sammlungen enthalten die Anzahl zugeordneter Buecher."""
    samml_id = await sammlung_erstellen(test_db, name="Fachbuchreihe")
    buch_id = await buch_erstellen(test_db, hash="samml_count01", title="Fachbuch Nr. 1")
    await test_db.execute(
        "UPDATE books SET sammlung_id = ? WHERE id = ?",
        (samml_id, buch_id),
    )
    await test_db.commit()

    response = await client.get("/api/collections")
    assert response.status_code == 200
    sammlungen = response.json()
    reihe = next(s for s in sammlungen if s["name"] == "Fachbuchreihe")
    assert reihe["buch_anzahl"] == 1


# -- Einzelne Sammlung abrufen --


@pytest.mark.asyncio
async def test_sammlung_details_abrufen(client: AsyncClient, test_db):
    """GET gibt eine einzelne Sammlung mit Buechern zurueck."""
    samml_id = await sammlung_erstellen(test_db, name="Detailreihe")
    buch_id = await buch_erstellen(test_db, hash="samml_detail01", title="Reihenbuch")
    await test_db.execute(
        "UPDATE books SET sammlung_id = ? WHERE id = ?",
        (samml_id, buch_id),
    )
    await test_db.commit()

    response = await client.get(f"/api/collections/{samml_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Detailreihe"
    assert len(data["books"]) == 1
    assert data["books"][0]["title"] == "Reihenbuch"


@pytest.mark.asyncio
async def test_sammlung_nicht_gefunden_gibt_404(client: AsyncClient):
    """GET auf nicht existierende Sammlung gibt 404 zurueck."""
    response = await client.get("/api/collections/99999")
    assert response.status_code == 404


# -- Sammlung aktualisieren --


@pytest.mark.asyncio
async def test_sammlung_aktualisieren_name(client: AsyncClient, test_db):
    """PATCH aendert den Namen einer Sammlung."""
    samml_id = await sammlung_erstellen(test_db, name="Alter Reihenname")

    response = await client.patch(
        f"/api/collections/{samml_id}",
        json={"name": "Neuer Reihenname"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Neuer Reihenname"


@pytest.mark.asyncio
async def test_sammlung_aktualisieren_farbe(client: AsyncClient, test_db):
    """PATCH aendert nur die Farbe einer Sammlung."""
    samml_id = await sammlung_erstellen(test_db, name="Farbreihe")

    response = await client.patch(
        f"/api/collections/{samml_id}",
        json={"color": "#ff0000"},
    )
    assert response.status_code == 200
    assert response.json()["color"] == "#ff0000"
    assert response.json()["name"] == "Farbreihe"


@pytest.mark.asyncio
async def test_sammlung_aktualisieren_ohne_felder(client: AsyncClient, test_db):
    """PATCH ohne Felder gibt 400 zurueck."""
    samml_id = await sammlung_erstellen(test_db, name="Leerupdate")

    response = await client.patch(f"/api/collections/{samml_id}", json={})
    assert response.status_code == 400


# -- Sammlung loeschen --


@pytest.mark.asyncio
async def test_sammlung_loeschen(client: AsyncClient, test_db):
    """DELETE entfernt eine Sammlung und setzt sammlung_id bei Buechern auf NULL."""
    samml_id = await sammlung_erstellen(test_db, name="Wird geloescht")
    buch_id = await buch_erstellen(test_db, hash="samml_del01", title="Loeschbuch")
    await test_db.execute(
        "UPDATE books SET sammlung_id = ? WHERE id = ?",
        (samml_id, buch_id),
    )
    await test_db.commit()

    response = await client.delete(f"/api/collections/{samml_id}")
    assert response.status_code == 200

    # Sammlung nicht mehr abrufbar
    response = await client.get(f"/api/collections/{samml_id}")
    assert response.status_code == 404

    # Buch hat keine Sammlung mehr
    row = await test_db.fetch_one("SELECT sammlung_id FROM books WHERE id = ?", (buch_id,))
    assert row["sammlung_id"] is None


# -- Buch-Zuordnung --


@pytest.mark.asyncio
async def test_buch_sammlung_zuordnen(client: AsyncClient, test_db):
    """POST ordnet ein Buch einer Sammlung zu."""
    samml_id = await sammlung_erstellen(test_db, name="Zuordnungsreihe")
    buch_id = await buch_erstellen(test_db, hash="samml_zuord01", title="Zuordnungsbuch")

    response = await client.post(f"/api/collections/{samml_id}/buch/{buch_id}")
    assert response.status_code == 200

    # Buch ist jetzt in der Sammlung
    row = await test_db.fetch_one("SELECT sammlung_id FROM books WHERE id = ?", (buch_id,))
    assert row["sammlung_id"] == samml_id


@pytest.mark.asyncio
async def test_buch_aus_sammlung_entfernen(client: AsyncClient, test_db):
    """DELETE entfernt ein Buch aus einer Sammlung."""
    samml_id = await sammlung_erstellen(test_db, name="Entfernungsreihe")
    buch_id = await buch_erstellen(test_db, hash="samml_entf01", title="Entfernungsbuch")
    await test_db.execute(
        "UPDATE books SET sammlung_id = ? WHERE id = ?",
        (samml_id, buch_id),
    )
    await test_db.commit()

    response = await client.delete(f"/api/collections/{samml_id}/buch/{buch_id}")
    assert response.status_code == 200

    row = await test_db.fetch_one("SELECT sammlung_id FROM books WHERE id = ?", (buch_id,))
    assert row["sammlung_id"] is None


@pytest.mark.asyncio
async def test_buch_sammlung_zuordnen_sammlung_nicht_gefunden(client: AsyncClient, test_db):
    """Zuordnung auf nicht existierende Sammlung gibt 404 zurueck."""
    buch_id = await buch_erstellen(test_db, hash="samml_nf01", title="Geisterbuch")

    response = await client.post(f"/api/collections/99999/buch/{buch_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_buch_sammlung_zuordnen_buch_nicht_gefunden(client: AsyncClient, test_db):
    """Zuordnung auf nicht existierendes Buch gibt 404 zurueck."""
    samml_id = await sammlung_erstellen(test_db, name="Geisterreihe")

    response = await client.post(f"/api/collections/{samml_id}/buch/99999")
    assert response.status_code == 404


# -- Systemtypen --


@pytest.mark.asyncio
async def test_systemtypen_abrufen(client: AsyncClient):
    """GET gibt die verfuegbaren Systemtypen zurueck."""
    response = await client.get("/api/collections/typen")
    assert response.status_code == 200
    typen = response.json()
    assert len(typen) == 3
    ids = [t["id"] for t in typen]
    assert "heft" in ids
    assert "katalog" in ids
    assert "broschuere" in ids
