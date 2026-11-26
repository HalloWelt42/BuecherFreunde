"""Große Sammlungen als ein Eintrag der Bücherliste (BF-66), die Bandfolge und die Filter der rechten Spalte beim Zuordnen
(BF-67). Titel, Autoren und Reihen sind erfunden."""

import itertools

from tests.api.conftest import buch_erstellen, kategorie_erstellen, sammlung_erstellen

_nummern = itertools.count(1)


async def buch(test_db, titel: str, autor: str = "Erna Beispiel", sammlung: int | None = None, band: str = "", **spalten) -> int:
    """Ein Buch; weitere Spalten (etwa created_at, year, file_format) direkt."""
    b = await buch_erstellen(test_db, hash=f"liste-{next(_nummern)}", title=titel, author=autor)
    spalten |= {"sammlung_id": sammlung, "band_nummer": band}
    await test_db.execute(f"UPDATE books SET {', '.join(f'{k} = ?' for k in spalten)} WHERE id = ?", (*spalten.values(), b))
    await test_db.commit()
    return b


async def grenze(client, ab: int) -> None:
    r = await client.put("/api/collections/einstellungen", json={"als_eintrag_ab": ab})
    assert r.status_code == 200 and r.json() == {"als_eintrag_ab": ab}


async def liste(client, **angaben) -> dict:
    r = await client.get("/api/books", params={"zusammenfassen": "true", "pro_seite": 100, **angaben})
    assert r.status_code == 200, r.text
    return r.json()


def folge(daten: dict) -> list[str]:
    """Die Einträge der Seite als Titel, Sammlungen in eckigen Klammern."""
    return [e["buch"]["title"] if e["art"] == "buch" else f"[{e['sammlung']['name']}]" for e in daten["eintraege"]]


# -- Einstellung ------------------------------------------------------------------------------------------------------------

async def test_einstellung_mit_vorgabe_und_grenzen(client):
    assert (await client.get("/api/collections/einstellungen")).json() == {"als_eintrag_ab": 8}
    for falsch in (1, 1001, "viele"):
        r = await client.put("/api/collections/einstellungen", json={"als_eintrag_ab": falsch})
        assert r.status_code == 422 and "als_eintrag_ab" in r.json()["detail"]
    await grenze(client, 2)
    await grenze(client, 1000)
    assert (await client.get("/api/collections/einstellungen")).json() == {"als_eintrag_ab": 1000}


# -- Zusammenfassen ---------------------------------------------------------------------------------------------------------

async def test_ab_der_grenze_ein_eintrag(client, test_db):
    sterne = await sammlung_erstellen(test_db, name="Sternenfahrer")
    mond = await sammlung_erstellen(test_db, name="Mondgarten")
    for band, titel in (("2", "Der Turm"), ("1", "Der Aufbruch"), ("3", "Das Tor")):
        await buch(test_db, titel, sammlung=sterne, band=band)
    for band, titel in (("1", "Kleiner Garten"), ("2", "Großer Garten")):
        await buch(test_db, titel, sammlung=mond, band=band)
    await buch(test_db, "Apfelbaum")
    await buch(test_db, "Zugvogel")

    d = await liste(client)                                                       # Vorgabe 8: nichts zusammengefasst
    assert len(d["eintraege"]) == 7 and d["sammlungen_zusammengefasst"] == 0 and d["in_sammlungen"] == 0

    await grenze(client, 3)
    d = await liste(client)
    assert folge(d) == ["Apfelbaum", "Großer Garten", "Kleiner Garten", "[Sternenfahrer]", "Zugvogel"]
    assert (d["gesamt"], d["gesamt_eintraege"], d["in_sammlungen"], d["sammlungen_zusammengefasst"]) == (7, 5, 3, 1)
    assert [b["title"] for b in d["buecher"]] == ["Apfelbaum", "Großer Garten", "Kleiner Garten", "Zugvogel"]
    stapel = d["eintraege"][3]["sammlung"]
    assert (stapel["id"], stapel["name"], stapel["anzahl"], stapel["autor"]) == (sterne, "Sternenfahrer", 3, "Erna Beispiel")
    assert [b["title"] for b in stapel["umschlaege"]] == ["Der Aufbruch", "Der Turm", "Das Tor"]          # nach Band
    assert stapel["umschlaege"][0]["sammlung"]["band_nummer"] == "1" and "cover_stand" in stapel["umschlaege"][0]

    ohne = (await client.get("/api/books", params={"pro_seite": 100})).json()     # ohne zusammenfassen wie bisher
    assert len(ohne["buecher"]) == 7 and ohne["gesamt"] == 7 and ohne["seiten_gesamt"] == 1
    assert all(ohne[f] is None for f in ("eintraege", "gesamt_eintraege", "in_sammlungen", "sammlungen_zusammengefasst"))


async def test_gezaehlt_wird_unter_dem_filter(client, test_db):
    sterne = await sammlung_erstellen(test_db, name="Sternenfahrer")
    for i, (autor, form) in enumerate((("Otto Muster", "pdf"), ("Erna Beispiel", "pdf"), ("Erna Beispiel", "pdf"),
                                       ("Erna Beispiel", "epub")), 1):
        await buch(test_db, f"Sternenfahrer {i}", autor=autor, sammlung=sterne, band=str(i), file_format=form)
    await buch(test_db, "Einzelstück", file_format="epub")
    await grenze(client, 3)

    d = await liste(client, format="epub")                                        # nur ein Band unter dem Filter
    assert folge(d) == ["Einzelstück", "Sternenfahrer 4"] and d["sammlungen_zusammengefasst"] == 0
    d = await liste(client, format="pdf")
    assert folge(d) == ["[Sternenfahrer]"] and d["eintraege"][0]["sammlung"]["anzahl"] == 3
    assert d["eintraege"][0]["sammlung"]["autor"] == "Erna Beispiel"              # der häufigste Autor
    d = await liste(client, sammlung=sterne)                                      # auch mit dem Filter der Sammlung selbst
    assert folge(d) == ["[Sternenfahrer]"] and d["eintraege"][0]["sammlung"]["anzahl"] == 4
    d = await liste(client, suche="Sternenfahrer", autor="Erna")
    assert folge(d) == ["[Sternenfahrer]"] and d["gesamt"] == 3 and d["gesamt_ohne_suche"] == 4


async def test_sortierung_der_sammlungseintraege(client, test_db):
    mond = await sammlung_erstellen(test_db, name="Mondgarten")
    for band, titel, autor, datum, jahr in (("1", "Zinnober", "Otto Muster", "2026-01-05 10:00:00", 1990),
                                            ("2", "Yselgrün", "Otto Muster", "2026-03-01 10:00:00", 2005),
                                            ("3", "Xanthippe", "Berta Probe", "2026-02-01 10:00:00", 2010)):
        await buch(test_db, titel, autor=autor, sammlung=mond, band=band, created_at=datum, year=jahr)
    await buch(test_db, "Apfelbaum", autor="Paul Zeder", created_at="2026-02-15 10:00:00", year=2000)
    await buch(test_db, "Nordlicht", autor="Anna Ahorn", created_at="2026-04-01 10:00:00", year=2020)
    await grenze(client, 2)

    assert folge(await liste(client)) == ["Apfelbaum", "[Mondgarten]", "Nordlicht"]                       # unter ihrem Namen
    assert folge(await liste(client, richtung="desc")) == ["Nordlicht", "[Mondgarten]", "Apfelbaum"]
    assert folge(await liste(client, sortierung="datum")) == ["Apfelbaum", "[Mondgarten]", "Nordlicht"]   # ihr neuestes Buch
    assert folge(await liste(client, sortierung="autor")) == ["Nordlicht", "[Mondgarten]", "Apfelbaum"]   # Otto Muster
    assert folge(await liste(client, sortierung="jahr")) == ["[Mondgarten]", "Apfelbaum", "Nordlicht"]    # ihr erstes Buch: 1990
    assert folge(await liste(client, sortierung="jahr", richtung="desc")) == ["Nordlicht", "[Mondgarten]", "Apfelbaum"]   # 2010


async def test_jede_sortierung_fasst_zusammen(client, test_db):
    sterne = await sammlung_erstellen(test_db, name="Sternenfahrer")
    for i in range(1, 4):
        await buch(test_db, f"Sternenfahrer {i}", sammlung=sterne, band=str(i))
    await buch(test_db, "Ahorn")
    await grenze(client, 2)
    for sortierung in ("titel", "autor", "datum", "groesse", "jahr", "verlag", "bewertung", "band", "unbekannt"):
        for richtung in ("asc", "desc"):
            assert sorted(folge(await liste(client, sortierung=sortierung, richtung=richtung))) == ["Ahorn", "[Sternenfahrer]"]


async def test_blaettern_ueber_eintraege(client, test_db):
    sterne = await sammlung_erstellen(test_db, name="Sternenfahrer")
    for i in range(1, 4):
        await buch(test_db, f"Sternenfahrer {i}", sammlung=sterne, band=str(i))
    for titel in ("Ahorn", "Birke", "Eiche", "Linde", "Ulme"):
        await buch(test_db, titel)
    await grenze(client, 2)

    seiten = [await liste(client, pro_seite=4, seite=n) for n in (1, 2, 3)]
    assert [folge(s) for s in seiten] == [["Ahorn", "Birke", "Eiche", "Linde"], ["[Sternenfahrer]", "Ulme"], []]
    for s in seiten:
        assert (s["gesamt"], s["gesamt_eintraege"], s["seiten_gesamt"], s["in_sammlungen"]) == (8, 6, 2, 3)
    assert [b["title"] for b in seiten[1]["buecher"]] == ["Ulme"]


async def test_umschlaege_sind_die_ersten_nach_band(client, test_db):
    sterne = await sammlung_erstellen(test_db, name="Sternenfahrer")
    for band, titel in (("10", "Zehn"), ("", "Ohne"), ("2", "Zwei"), ("1", "Eins"), ("3", "Drei")):
        await buch(test_db, titel, sammlung=sterne, band=band)
    await grenze(client, 2)
    stapel = (await liste(client))["eintraege"][0]["sammlung"]
    assert stapel["anzahl"] == 5 and [b["title"] for b in stapel["umschlaege"]] == ["Eins", "Zwei", "Drei"]


# -- Bandfolge und Filter der rechten Spalte --------------------------------------------------------------------------------

async def test_sortierung_nach_band(client, test_db):
    sterne = await sammlung_erstellen(test_db, name="Sternenfahrer")
    for band, titel in (("10", "Zehn"), ("", "Ohne"), ("2", "Zwei"), ("Sonderband", "Sonder"), ("1", "Eins"), ("2", "Auch zwei")):
        await buch(test_db, titel, sammlung=sterne, band=band)

    async def titel(**angaben) -> list[str]:
        r = await client.get("/api/books", params={"sammlung": sterne, "sortierung": "band", **angaben})
        return [b["title"] for b in r.json()["buecher"]]

    assert await titel() == ["Eins", "Auch zwei", "Zwei", "Zehn", "Sonder", "Ohne"]           # natürlich, leere hinten
    assert await titel(richtung="desc") == ["Zehn", "Auch zwei", "Zwei", "Eins", "Sonder", "Ohne"]           # Titel bleibt aufsteigend
    sammlung = (await client.get(f"/api/collections/{sterne}")).json()
    assert [b["title"] for b in sammlung["books"]] == ["Eins", "Auch zwei", "Zwei", "Zehn", "Sonder", "Ohne"]


async def test_filter_ohne_sammlung_und_nicht_im_regal(client, test_db):
    sterne = await sammlung_erstellen(test_db, name="Sternenfahrer")
    regal = await kategorie_erstellen(test_db, name="Abenteuer")
    drin = await buch(test_db, "In der Sammlung", sammlung=sterne, band="1")
    frei = await buch(test_db, "Frei")
    im_regal = await buch(test_db, "Im Regal")
    for b in (drin, im_regal):
        await test_db.execute("INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)", (b, regal))
    await test_db.commit()

    async def titel(**angaben) -> list[str]:
        return [b["title"] for b in (await client.get("/api/books", params=angaben)).json()["buecher"]]

    assert await titel(ohne_sammlung="true") == ["Frei", "Im Regal"]
    assert await titel(ohne_sammlung="false") == ["In der Sammlung"]
    assert await titel(nicht_kategorie=regal) == ["Frei"]
    assert await titel(nicht_kategorie=regal, ohne_sammlung="true", suche="frei") == ["Frei"]
    assert (await client.get("/api/books", params={"nicht_kategorie": 0})).status_code == 422
