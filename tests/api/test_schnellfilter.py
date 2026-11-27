"""Schnellfilter der Bücherliste: Titel, Autor, ISBN und Etikett, jedes Wort muss passen."""

import pytest
from httpx import AsyncClient

from backend.app.services.schnellfilter import bedingung, muster
from tests.api.conftest import buch_erstellen, sammlung_erstellen, verwaltung


def test_muster_gross_und_klein_auch_mit_umlauten():
    assert muster("über") == "*[üÜ][bB][eE][rR]*"
    assert muster("ß") == "*ß*"


def test_muster_nimmt_globzeichen_woertlich():
    assert muster("C++") == "*[cC]++*"
    assert muster("a*?[]") == "*[aA][*][?][[][]]*"


def test_ohne_woerter_keine_bedingung():
    assert bedingung(None, "p") == ("", [])
    assert bedingung("   ", "p") == ("", [])


async def _bestand(test_db) -> dict[str, int]:
    ids = {
        "pruefen": await buch_erstellen(test_db, hash="sf1", title="Über das Prüfen", author="Max Muster", isbn="978-3-99998-101-7"),
        "zahlenreich": await buch_erstellen(test_db, hash="sf2", title="Zahlenreich", author="HalloWelt42", isbn="9783999991245"),
        "hexagonal": await buch_erstellen(test_db, hash="sf3", title="Hexagonal", author="HalloWelt42", isbn="", file_format="epub"),
        "plus": await buch_erstellen(test_db, hash="sf4", title="C++ [Grundkurs]", author="Ada Muster", isbn=""),
    }
    profil = await verwaltung(test_db)
    await test_db.execute("INSERT INTO book_labels (profil_id, book_id, name) VALUES (?, ?, ?)", (profil, ids["hexagonal"], "Lieblingsstelle"))
    await test_db.execute("INSERT INTO book_highlights (profil_id, book_id, cfi_range, label_name) VALUES (?, ?, ?, ?)",
                          (profil, ids["pruefen"], "epubcfi(/6/2)", "Prüfung"))
    await test_db.commit()
    return ids


async def _gefunden(client: AsyncClient, **params) -> tuple[set[int], dict]:
    antwort = await client.get("/api/books", params=params)
    assert antwort.status_code == 200
    daten = antwort.json()
    return {b["id"] for b in daten["buecher"]}, daten


@pytest.mark.asyncio
async def test_findet_titel_klein_geschrieben_auch_mit_umlaut(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    gefunden, _ = await _gefunden(client, suche="über")
    assert gefunden == {ids["pruefen"]}


@pytest.mark.asyncio
async def test_findet_autor_und_teilwort(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    gefunden, _ = await _gefunden(client, suche="allowel")
    assert gefunden == {ids["zahlenreich"], ids["hexagonal"]}


@pytest.mark.asyncio
async def test_jedes_wort_muss_passen(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    gefunden, _ = await _gefunden(client, suche="hallowelt42 zahlenreich")
    assert gefunden == {ids["zahlenreich"]}


@pytest.mark.asyncio
async def test_findet_isbn_mit_und_ohne_bindestriche(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    assert (await _gefunden(client, suche="3999981017"))[0] == {ids["pruefen"]}
    assert (await _gefunden(client, suche="978-3-99999"))[0] == {ids["zahlenreich"]}


@pytest.mark.asyncio
async def test_kurze_zahl_ist_keine_isbn(client: AsyncClient, test_db):
    await _bestand(test_db)
    band3 = await buch_erstellen(test_db, hash="sf5", title="Zahlenreich, Band 3", author="HalloWelt42", isbn="978-3-99999-124-5")
    assert (await _gefunden(client, suche="zahlenreich 3"))[0] == {band3}


@pytest.mark.asyncio
async def test_findet_etiketten(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    assert (await _gefunden(client, suche="lieblings"))[0] == {ids["hexagonal"]}
    assert (await _gefunden(client, suche="prüfung"))[0] == {ids["pruefen"]}


@pytest.mark.asyncio
async def test_sonderzeichen_gelten_woertlich(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    assert (await _gefunden(client, suche="c++"))[0] == {ids["plus"]}
    assert (await _gefunden(client, suche="[grund"))[0] == {ids["plus"]}
    assert (await _gefunden(client, suche="*"))[0] == set()


@pytest.mark.asyncio
async def test_zaehlt_die_liste_ohne_schnellfilter(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    gefunden, daten = await _gefunden(client, suche="hallowelt42", format="epub")
    assert gefunden == {ids["hexagonal"]}
    assert daten["gesamt"] == 1
    assert daten["gesamt_ohne_suche"] == 1
    _, daten = await _gefunden(client, suche="hallowelt42")
    assert (daten["gesamt"], daten["gesamt_ohne_suche"]) == (2, 4)
    _, daten = await _gefunden(client)
    assert daten["gesamt_ohne_suche"] is None


@pytest.mark.asyncio
async def test_gilt_auch_in_einer_sammlung(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    sammlung = await sammlung_erstellen(test_db, name="Eigene Werke")
    await test_db.execute("UPDATE books SET sammlung_id = ? WHERE id IN (?, ?)", (sammlung, ids["zahlenreich"], ids["hexagonal"]))
    await test_db.commit()
    gefunden, daten = await _gefunden(client, sammlung=sammlung, suche="hexagonal")
    assert gefunden == {ids["hexagonal"]}
    assert daten["gesamt_ohne_suche"] == 2


@pytest.mark.asyncio
async def test_filter_mit_etiketten_kennt_beide_arten_und_ohne(client: AsyncClient, test_db):
    # BF-45: Etiketten des Lesers (book_labels) zählen wie Namen an Markierungen; hat_labels=false heißt "ohne"
    ids = await _bestand(test_db)
    mit, _ = await _gefunden(client, hat_labels="true")
    assert mit == {ids["hexagonal"], ids["pruefen"]}
    ohne, _ = await _gefunden(client, hat_labels="false")
    assert ohne == {ids["zahlenreich"], ids["plus"]}
    zahlen = await client.get("/api/config/stats")
    assert zahlen.status_code == 200 and zahlen.json()["mit_labels"] == 2
