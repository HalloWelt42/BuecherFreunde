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
        "freiheit": await buch_erstellen(test_db, hash="sf1", title="Über die Freiheit", author="John Stuart Mill", isbn="978-3-15-003491-1"),
        "hobbit": await buch_erstellen(test_db, hash="sf2", title="Der kleine Hobbit", author="J. R. R. Tolkien", isbn="9783423715669"),
        "ringe": await buch_erstellen(test_db, hash="sf3", title="Der Herr der Ringe", author="J. R. R. Tolkien", isbn="", file_format="epub"),
        "plus": await buch_erstellen(test_db, hash="sf4", title="C++ [Grundkurs]", author="Ada Muster", isbn=""),
    }
    profil = await verwaltung(test_db)
    await test_db.execute("INSERT INTO book_labels (profil_id, book_id, name) VALUES (?, ?, ?)", (profil, ids["ringe"], "Lieblingsstelle"))
    await test_db.execute("INSERT INTO book_highlights (profil_id, book_id, cfi_range, label_name) VALUES (?, ?, ?, ?)",
                          (profil, ids["freiheit"], "epubcfi(/6/2)", "Prüfung"))
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
    assert gefunden == {ids["freiheit"]}


@pytest.mark.asyncio
async def test_findet_autor_und_teilwort(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    gefunden, _ = await _gefunden(client, suche="olkie")
    assert gefunden == {ids["hobbit"], ids["ringe"]}


@pytest.mark.asyncio
async def test_jedes_wort_muss_passen(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    gefunden, _ = await _gefunden(client, suche="tolkien hobbit")
    assert gefunden == {ids["hobbit"]}


@pytest.mark.asyncio
async def test_findet_isbn_mit_und_ohne_bindestriche(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    assert (await _gefunden(client, suche="3150034911"))[0] == {ids["freiheit"]}
    assert (await _gefunden(client, suche="978-3-423"))[0] == {ids["hobbit"]}


@pytest.mark.asyncio
async def test_kurze_zahl_ist_keine_isbn(client: AsyncClient, test_db):
    await _bestand(test_db)
    band2 = await buch_erstellen(test_db, hash="sf5", title="Der kleine Hobbit, Band 2", author="J. R. R. Tolkien", isbn="978-3-423-71566-9")
    assert (await _gefunden(client, suche="hobbit 2"))[0] == {band2}


@pytest.mark.asyncio
async def test_findet_etiketten(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    assert (await _gefunden(client, suche="lieblings"))[0] == {ids["ringe"]}
    assert (await _gefunden(client, suche="prüfung"))[0] == {ids["freiheit"]}


@pytest.mark.asyncio
async def test_sonderzeichen_gelten_woertlich(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    assert (await _gefunden(client, suche="c++"))[0] == {ids["plus"]}
    assert (await _gefunden(client, suche="[grund"))[0] == {ids["plus"]}
    assert (await _gefunden(client, suche="*"))[0] == set()


@pytest.mark.asyncio
async def test_zaehlt_die_liste_ohne_schnellfilter(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    gefunden, daten = await _gefunden(client, suche="tolkien", format="epub")
    assert gefunden == {ids["ringe"]}
    assert daten["gesamt"] == 1
    assert daten["gesamt_ohne_suche"] == 1
    _, daten = await _gefunden(client, suche="tolkien")
    assert (daten["gesamt"], daten["gesamt_ohne_suche"]) == (2, 4)
    _, daten = await _gefunden(client)
    assert daten["gesamt_ohne_suche"] is None


@pytest.mark.asyncio
async def test_gilt_auch_in_einer_sammlung(client: AsyncClient, test_db):
    ids = await _bestand(test_db)
    sammlung = await sammlung_erstellen(test_db, name="Mittelerde")
    await test_db.execute("UPDATE books SET sammlung_id = ? WHERE id IN (?, ?)", (sammlung, ids["hobbit"], ids["ringe"]))
    await test_db.commit()
    gefunden, daten = await _gefunden(client, sammlung=sammlung, suche="ringe")
    assert gefunden == {ids["ringe"]}
    assert daten["gesamt_ohne_suche"] == 2


@pytest.mark.asyncio
async def test_filter_mit_etiketten_kennt_beide_arten_und_ohne(client: AsyncClient, test_db):
    # BF-45: Etiketten des Lesers (book_labels) zählen wie Namen an Markierungen; hat_labels=false heißt "ohne"
    ids = await _bestand(test_db)
    mit, _ = await _gefunden(client, hat_labels="true")
    assert mit == {ids["ringe"], ids["freiheit"]}
    ohne, _ = await _gefunden(client, hat_labels="false")
    assert ohne == {ids["hobbit"], ids["plus"]}
    zahlen = await client.get("/api/config/stats")
    assert zahlen.status_code == 200 and zahlen.json()["mit_labels"] == 2
