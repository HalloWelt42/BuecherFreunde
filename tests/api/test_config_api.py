"""API-Integrationstests fuer Config- und Health-Endpunkte."""

import pytest
from httpx import AsyncClient


# -- Health-Check --


@pytest.mark.asyncio
async def test_health_check_ohne_auth(client_ohne_auth: AsyncClient):
    """Health-Endpunkt ist ohne Authentifizierung erreichbar."""
    response = await client_ohne_auth.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_check_mit_auth(client: AsyncClient):
    """Health-Endpunkt funktioniert auch mit Authentifizierung."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# -- Konfiguration --


@pytest.mark.asyncio
async def test_config_mit_auth(client: AsyncClient):
    """Config-Endpunkt gibt oeffentliche Konfiguration zurueck."""
    response = await client.get("/api/config")
    assert response.status_code == 200
    data = response.json()

    # Struktur pruefen
    assert "version" in data
    assert "external_port" in data
    assert "openlibrary" in data
    assert "lm_studio" in data
    assert "pfade" in data

    # Open Library Konfiguration
    assert "aktiviert" in data["openlibrary"]
    assert "rate_limit" in data["openlibrary"]

    # LM Studio Konfiguration
    assert "aktiviert" in data["lm_studio"]
    assert "url" in data["lm_studio"]
    assert "modell" in data["lm_studio"]

    # Pfade
    assert "speicher" in data["pfade"]
    assert "extern" in data["pfade"]
    assert "import" in data["pfade"]
    assert "datenbank" in data["pfade"]


@pytest.mark.asyncio
async def test_config_enthaelt_keinen_token(client: AsyncClient):
    """Config-Endpunkt gibt KEINEN API-Token zurueck."""
    response = await client.get("/api/config")
    assert response.status_code == 200
    data = response.json()

    # Sicherstellen, dass kein Token in der Antwort ist
    data_str = str(data)
    assert "api_token" not in data_str
    assert "token" not in data.keys()


@pytest.mark.asyncio
async def test_config_ohne_auth_gibt_fehler(client_ohne_auth: AsyncClient):
    """Config-Endpunkt erfordert Authentifizierung."""
    response = await client_ohne_auth.get("/api/config")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_config_mit_falschem_token(client_ohne_auth: AsyncClient):
    """Config-Endpunkt mit falschem Token gibt 401 zurueck."""
    response = await client_ohne_auth.get(
        "/api/config",
        headers={"Authorization": "Bearer voellig-falscher-token"},
    )
    assert response.status_code == 401


# -- Version --


@pytest.mark.asyncio
async def test_version_ohne_auth(client_ohne_auth: AsyncClient):
    """Version-Endpunkt ist ohne Authentifizierung erreichbar."""
    response = await client_ohne_auth.get("/api/config/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert isinstance(data["version"], str)


@pytest.mark.asyncio
async def test_version_format(client: AsyncClient):
    """Version hat das erwartete Format (Semantic Versioning)."""
    response = await client.get("/api/config/version")
    assert response.status_code == 200
    version = response.json()["version"]
    # Mindestens x.y.z Format
    teile = version.split(".")
    assert len(teile) >= 2, f"Version '{version}' hat kein gueltiges Format"
