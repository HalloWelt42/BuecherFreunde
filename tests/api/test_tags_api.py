"""API-Integrationstests fuer Tags-Endpunkte."""

import pytest
from httpx import AsyncClient

from tests.api.conftest import buch_erstellen, tag_erstellen


# -- Authentifizierung --


@pytest.mark.asyncio
async def test_tags_ohne_token_gibt_fehler(client_ohne_auth: AsyncClient):
    """Anfrage ohne Token wird abgelehnt."""
    response = await client_ohne_auth.get("/api/tags")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tags_mit_falschem_token(client_ohne_auth: AsyncClient):
    """Anfrage mit falschem Token gibt 401 zurueck."""
    response = await client_ohne_auth.get(
        "/api/tags",
        headers={"Authorization": "Bearer komplett-falsch"},
    )
    assert response.status_code == 401


# -- Leere Liste --


@pytest.mark.asyncio
async def test_tags_liste_leer(client: AsyncClient):
    """Leere Datenbank gibt eine leere Tag-Liste zurueck."""
    response = await client.get("/api/tags")
    assert response.status_code == 200
    assert response.json() == []


# -- Tag erstellen --


@pytest.mark.asyncio
async def test_tag_erstellen(client: AsyncClient):
    """POST erstellt einen neuen Tag."""
    response = await client.post(
        "/api/tags",
        json={"name": "Python", "color": "#3572A5"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Python"
    assert data["slug"] == "python"
    assert data["color"] == "#3572A5"
    assert "id" in data


@pytest.mark.asyncio
async def test_tag_erstellen_mit_standardfarbe(client: AsyncClient):
    """POST ohne Farbe verwendet die Standardfarbe."""
    response = await client.post(
        "/api/tags",
        json={"name": "Wichtig"},
    )
    assert response.status_code == 201
    assert response.json()["color"] == "#6b7280"


@pytest.mark.asyncio
async def test_tag_erstellen_duplikat_gibt_409(client: AsyncClient):
    """POST mit doppeltem Tag-Namen gibt 409 Conflict zurueck."""
    await client.post("/api/tags", json={"name": "Duplikat"})
    response = await client.post("/api/tags", json={"name": "Duplikat"})
    assert response.status_code == 409
    assert "existiert bereits" in response.json()["detail"]


# -- Tag-Liste mit Buchanzahl --


@pytest.mark.asyncio
async def test_tags_mit_buchanzahl(client: AsyncClient, test_db):
    """Tags enthalten die Anzahl zugeordneter Buecher."""
    tag_id = await tag_erstellen(test_db, name="Fachbuch")
    buch_id = await buch_erstellen(test_db, hash="tag_count01", title="Fachbuch Nr. 1")
    await test_db.execute(
        "INSERT INTO book_tags (book_id, tag_id) VALUES (?, ?)",
        (buch_id, tag_id),
    )
    await test_db.commit()

    response = await client.get("/api/tags")
    assert response.status_code == 200
    tags = response.json()
    fachbuch = next(t for t in tags if t["name"] == "Fachbuch")
    assert fachbuch["buch_anzahl"] == 1


@pytest.mark.asyncio
async def test_tags_sortiert_nach_name(client: AsyncClient):
    """Tags werden alphabetisch nach Name sortiert."""
    await client.post("/api/tags", json={"name": "Zebra"})
    await client.post("/api/tags", json={"name": "Alpha"})
    await client.post("/api/tags", json={"name": "Mitte"})

    response = await client.get("/api/tags")
    namen = [t["name"] for t in response.json()]
    assert namen == sorted(namen)


# -- Tag aktualisieren --


@pytest.mark.asyncio
async def test_tag_aktualisieren_name(client: AsyncClient):
    """PATCH aendert den Namen eines Tags."""
    response = await client.post("/api/tags", json={"name": "Alt"})
    tag_id = response.json()["id"]

    response = await client.patch(
        f"/api/tags/{tag_id}",
        json={"name": "Neu"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Neu"
    assert data["slug"] == "neu"


@pytest.mark.asyncio
async def test_tag_aktualisieren_farbe(client: AsyncClient):
    """PATCH aendert nur die Farbe eines Tags."""
    response = await client.post("/api/tags", json={"name": "Farbtag"})
    tag_id = response.json()["id"]

    response = await client.patch(
        f"/api/tags/{tag_id}",
        json={"color": "#ff0000"},
    )
    assert response.status_code == 200
    assert response.json()["color"] == "#ff0000"
    assert response.json()["name"] == "Farbtag"  # Name unveraendert


@pytest.mark.asyncio
async def test_tag_aktualisieren_ohne_felder(client: AsyncClient):
    """PATCH ohne Felder gibt 400 zurueck."""
    response = await client.post("/api/tags", json={"name": "Leer"})
    tag_id = response.json()["id"]

    response = await client.patch(f"/api/tags/{tag_id}", json={})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_tag_aktualisieren_nicht_gefunden(client: AsyncClient):
    """PATCH auf nicht existierenden Tag gibt 404 zurueck."""
    response = await client.patch(
        "/api/tags/99999",
        json={"name": "Geistertag"},
    )
    assert response.status_code == 404


# -- Tag loeschen --


@pytest.mark.asyncio
async def test_tag_loeschen(client: AsyncClient):
    """DELETE entfernt einen Tag."""
    response = await client.post("/api/tags", json={"name": "Loesch-Tag"})
    tag_id = response.json()["id"]

    response = await client.delete(f"/api/tags/{tag_id}")
    assert response.status_code == 200
    assert response.json()["geloescht"] is True

    # Tag nicht mehr in der Liste
    response = await client.get("/api/tags")
    assert all(t["id"] != tag_id for t in response.json())


@pytest.mark.asyncio
async def test_tag_loeschen_nicht_gefunden(client: AsyncClient):
    """DELETE auf nicht existierenden Tag gibt 404 zurueck."""
    response = await client.delete("/api/tags/99999")
    assert response.status_code == 404


# -- Buch-Zuordnung --


@pytest.mark.asyncio
async def test_buch_tags_zuordnen(client: AsyncClient, test_db):
    """POST ordnet einem Buch Tags zu."""
    buch_id = await buch_erstellen(test_db, hash="tag_zuord01", title="Tag-Buch")
    tag1_id = await tag_erstellen(test_db, name="Tag Eins")
    tag2_id = await tag_erstellen(test_db, name="Tag Zwei")

    response = await client.post(
        f"/api/tags/{buch_id}/zuordnen",
        json=[tag1_id, tag2_id],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["book_id"] == buch_id
    assert set(data["tags"]) == {tag1_id, tag2_id}


@pytest.mark.asyncio
async def test_buch_tags_zuordnen_ersetzt_bestehende(client: AsyncClient, test_db):
    """Neue Tag-Zuordnung ersetzt bestehende Tags."""
    buch_id = await buch_erstellen(test_db, hash="tag_zuord02", title="Umtaggen")
    tag1_id = await tag_erstellen(test_db, name="Erster Tag")
    tag2_id = await tag_erstellen(test_db, name="Zweiter Tag")

    await client.post(f"/api/tags/{buch_id}/zuordnen", json=[tag1_id])
    response = await client.post(f"/api/tags/{buch_id}/zuordnen", json=[tag2_id])
    assert response.status_code == 200
    assert response.json()["tags"] == [tag2_id]


@pytest.mark.asyncio
async def test_buch_tags_zuordnen_buch_nicht_gefunden(client: AsyncClient):
    """Zuordnung auf nicht existierendes Buch gibt 404 zurueck."""
    response = await client.post(
        "/api/tags/99999/zuordnen",
        json=[1],
    )
    assert response.status_code == 404
