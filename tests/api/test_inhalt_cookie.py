"""Bilder, Dateien und Ereignisströme kommen mit dem Inhalts-Cookie, nie mit der Anmeldung in der Adresse (BF-5)."""

import pytest
from httpx import AsyncClient

from tests.api.conftest import SITZUNG

DATEI = "/api/books/1/file"


@pytest.mark.asyncio
async def test_ohne_anmeldung_und_mit_schluessel_in_der_adresse_abgewiesen(client_ohne_auth: AsyncClient):
    assert (await client_ohne_auth.get(DATEI)).status_code == 401
    assert (await client_ohne_auth.get(DATEI, params={"token": SITZUNG})).status_code == 401


@pytest.mark.asyncio
async def test_cookie_oeffnet_lesende_wege(client_ohne_auth: AsyncClient):
    antwort = await client_ohne_auth.get(DATEI, headers={"Cookie": f"app_inhalt={SITZUNG}"})
    assert antwort.status_code == 404, "angemeldet, nur das Buch gibt es nicht"


@pytest.mark.asyncio
async def test_cookie_oeffnet_keine_aendernden_wege(client_ohne_auth: AsyncClient):
    antwort = await client_ohne_auth.post("/api/books/bulk", headers={"Cookie": f"app_inhalt={SITZUNG}"}, json={"book_ids": [1], "aktion": "favorit"})
    assert antwort.status_code == 401
