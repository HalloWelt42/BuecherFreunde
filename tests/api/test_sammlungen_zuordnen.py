"""Zuordnen in zwei Spalten (BF-67): Sammelaktionen für Sammlung und Regal, neue Bände hinten an, die Reihenfolge der Bände.
Titel und Reihen sind erfunden."""

from tests.api.conftest import kategorie_erstellen, sammlung_erstellen
from tests.api.test_sammlungen_liste import buch


async def baende(test_db, sammlung: int) -> dict[str, str]:
    zeilen = await test_db.fetch_all("SELECT title, band_nummer FROM books WHERE sammlung_id = ?", (sammlung,))
    return {z["title"]: z["band_nummer"] for z in zeilen}


async def sammelaktion(client, aktion: str, book_ids: list[int], wert=None):
    return await client.post("/api/books/bulk", json={"book_ids": book_ids, "aktion": aktion, "wert": wert})


async def test_zuweisen_haengt_hinten_an(client, test_db):
    sterne = await sammlung_erstellen(test_db, name="Sternenfahrer")
    mond = await sammlung_erstellen(test_db, name="Mondgarten")
    await buch(test_db, "Eins", sammlung=sterne, band="1")
    await buch(test_db, "Zwei", sammlung=sterne, band="2")
    ohne_nummer = await buch(test_db, "Ohne Nummer", sammlung=sterne)
    neu_a, neu_b = await buch(test_db, "Neu A"), await buch(test_db, "Neu B")
    umzug = await buch(test_db, "Umzug", sammlung=mond, band="7")

    r = await sammelaktion(client, "sammlung_zuweisen", [neu_b, neu_a, neu_b], sterne)
    assert r.json() == {"betroffen": 2, "aktion": "sammlung_zuweisen"}
    assert await baende(test_db, sterne) == {"Eins": "1", "Zwei": "2", "Ohne Nummer": "", "Neu B": "3", "Neu A": "4"}

    r = await sammelaktion(client, "sammlung_zuweisen", [neu_a, ohne_nummer, umzug], sterne)    # wer eine Nummer hat, bleibt
    assert r.json()["betroffen"] == 2
    assert await baende(test_db, sterne) == {"Eins": "1", "Zwei": "2", "Ohne Nummer": "5", "Neu B": "3", "Neu A": "4", "Umzug": "6"}
    assert await baende(test_db, mond) == {}
    assert (await sammelaktion(client, "sammlung_zuweisen", [neu_a], 99999)).status_code == 404


async def test_aus_der_sammlung_entfernen(client, test_db):
    sterne = await sammlung_erstellen(test_db, name="Sternenfahrer")
    eins, zwei = await buch(test_db, "Eins", sammlung=sterne, band="1"), await buch(test_db, "Zwei", sammlung=sterne, band="2")
    frei = await buch(test_db, "Frei")

    r = await sammelaktion(client, "sammlung_entfernen", [eins, frei])
    assert r.json() == {"betroffen": 1, "aktion": "sammlung_entfernen"}
    z = await test_db.fetch_one("SELECT sammlung_id, band_nummer FROM books WHERE id = ?", (eins,))
    assert (z["sammlung_id"], z["band_nummer"]) == (None, "")
    assert await baende(test_db, sterne) == {"Zwei": "2"}
    assert (await test_db.fetch_one("SELECT sammlung_id FROM books WHERE id = ?", (zwei,)))["sammlung_id"] == sterne


async def test_aus_dem_regal_entfernen(client, test_db):
    abenteuer = await kategorie_erstellen(test_db, name="Abenteuer")
    reisen = await kategorie_erstellen(test_db, name="Reisen")
    a, b = await buch(test_db, "Erstes"), await buch(test_db, "Zweites")
    for buch_id, regal in ((a, abenteuer), (a, reisen), (b, abenteuer)):
        await test_db.execute("INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)", (buch_id, regal))
    await test_db.commit()

    r = await sammelaktion(client, "kategorie_entfernen", [a, b], abenteuer)
    assert r.json() == {"betroffen": 2, "aktion": "kategorie_entfernen"}
    zeilen = await test_db.fetch_all("SELECT book_id, category_id FROM book_categories ORDER BY book_id")
    assert [(z["book_id"], z["category_id"]) for z in zeilen] == [(a, reisen)]
    assert (await sammelaktion(client, "kategorie_entfernen", [a], 99999)).status_code == 404
    assert (await sammelaktion(client, "kategorie_entfernen", [a])).status_code == 400


async def test_reihenfolge_setzen(client, test_db):
    sterne = await sammlung_erstellen(test_db, name="Sternenfahrer")
    a = await buch(test_db, "Anfang", sammlung=sterne, band="1")
    b = await buch(test_db, "Mitte", sammlung=sterne, band="2")
    c = await buch(test_db, "Schluss", sammlung=sterne, band="3")
    fremd = await buch(test_db, "Fremd")

    r = await client.put(f"/api/collections/{sterne}/reihenfolge", json={"book_ids": [c, a, b]})
    assert r.status_code == 200 and [x["title"] for x in r.json()["books"]] == ["Schluss", "Anfang", "Mitte"]
    assert await baende(test_db, sterne) == {"Schluss": "1", "Anfang": "2", "Mitte": "3"}

    r = await client.put(f"/api/collections/{sterne}/reihenfolge", json={"book_ids": [b]})      # die übrigen folgen wie bisher
    assert await baende(test_db, sterne) == {"Mitte": "1", "Schluss": "2", "Anfang": "3"}

    r = await client.put(f"/api/collections/{sterne}/reihenfolge", json={"book_ids": [a, fremd]})
    assert r.status_code == 400 and r.json()["detail"] == f"Das Buch {fremd} gehört nicht zu dieser Sammlung"
    r = await client.put(f"/api/collections/{sterne}/reihenfolge", json={"book_ids": [a, a]})
    assert r.status_code == 400 and r.json()["detail"] == "Ein Buch steht mehr als einmal in der Reihenfolge"
    assert await baende(test_db, sterne) == {"Mitte": "1", "Schluss": "2", "Anfang": "3"}                  # nichts geändert
    assert (await client.put("/api/collections/99999/reihenfolge", json={"book_ids": [a]})).status_code == 404
