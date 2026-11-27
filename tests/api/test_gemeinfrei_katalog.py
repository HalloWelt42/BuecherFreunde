"""Gemeinfreie Bücher mit eigenem Katalog (BF-98): bauen nur aus Text, Vorschläge ohne Netz, Holen vom Spiegel mit Fortschritt,
Fortsetzen und Rückfrage beim Erneuern, Rückfall von Gutendex auf den Katalog mit Hinweis in Klartext, der Abgleich fehlender
Bände, In die Lücke holen über eine Vorschau und die nächtliche Pflege. Alle Titel und Namen sind erfunden."""

import re
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from backend.app.annahme import gemeinfrei
from backend.app.api import gutenberg as gutenberg_api
from backend.app.core.config import settings
from backend.app.luecken import speicher
from backend.app.luecken.modelle import Quellband, Quellergebnis
from backend.app.quellen import gutenberg_katalog
from backend.app.quellen.gutenberg_katalog import Katalogfehler, bauen, katalog, ort
from backend.app.quellen.modelle import Buchfrage
from backend.app.quellen.versand import in_datei
from backend.app.services import pflege
from tests.api.conftest import sammlung_erstellen
from tests.api.test_annahme_api import warten
from tests.api.test_luecken import epub
from tests.api.test_sammlungen_liste import buch
from tests.quellen_netz import AUSFALL, antwort

SPIEGEL_1, SPIEGEL_2, GUTENDEX = "gutenberg.pglaf.org", "aleph.pglaf.org", "gutendex.com"
KATALOG = """Text#,Type,Issued,Title,Language,Authors,Subjects,LoCC,Bookshelves
101,Text,1999-01-01,"Der Mühlenkai
Eine Erzählung vom Wasser",de,"Lindqvist, Ebba, 1801-1870; Feldhain, Oswin, 1820-1890 [Translator]",Mills -- Fiction,PT,Category: Novels
102,Text,1999-01-02,Kaiwind: Erster Teil,de,"Marks, Jonte, 1790-1850",Wind -- Fiction,PT,Category: Novels
103,Text,1999-01-03,Kaiwind: Zweiter Teil,de,"Marks, Jonte, 1790-1850",Wind -- Fiction,PT,Category: Novels
104,Text,1999-01-04,The Quiet Quay,en; de,"Marks, Jonte, 1790-1850",Harbours,PR,
105,Sound,1999-01-05,Kaiwind gelesen,de,"Marks, Jonte, 1790-1850",,,
106,Text,1999-01-06,Über Ölmühlen und Straßen,de,"Größer, Ännchen",Mills,TJ,Category: Technology
"""
INHALT = KATALOG.encode()
GEMEINFREI_ERSTER = {"id": 102, "title": "Kaiwind: Erster Teil", "authors": [{"name": "Marks, Jonte"}], "languages": ["de"],
                     "formats": {"application/epub+zip": "https://www.gutenberg.org/ebooks/102.epub3.images"}, "download_count": 12}


def ids(liste) -> list[int]:
    return [b.gutenberg_id for b in liste.buecher]


@pytest.fixture
async def frisch():
    """Der Auftrag ist eine Einheit für die ganze App: je Test ohne alten Grund, danach angehalten."""
    katalog.grund = ""
    yield katalog
    await katalog.stoppen()


@pytest.fixture
def gebaut(test_db, tmp_path, frisch):
    quelle = tmp_path / "katalog.csv"
    quelle.write_bytes(INHALT)
    bauen(quelle, ort(), {"stand": "2026-11-08", "geholt_am": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "etag": '"v1"'})
    return ort()


def alt_machen(pfad, tage: int = 10) -> None:
    with sqlite3.connect(pfad) as v:
        v.execute("UPDATE kopf SET wert = ? WHERE schluessel = 'geholt_am'", ((datetime.now(UTC) - timedelta(days=tage)).strftime("%Y-%m-%dT%H:%M:%SZ"),))
    v.close()


# -- Bauen und Vorschläge ---------------------------------------------------------------------------------------------------

async def test_katalog_nur_aus_text_mit_titel_autor_und_spiegeladressen(gebaut):
    s = await katalog.stand()
    assert (s.da, s.anzahl, s.stand, s.faellig, s.erneuern_tage, s.suche_geduld_s) == (True, 5, "2026-11-08", False, 7, 120)
    liste = await katalog.vorschlaege("mühl")
    assert ids(liste) == [101] and liste.herkunft == "katalog"
    b = liste.buecher[0]
    assert (b.titel, b.autor, b.sprachen, b.download_format) == ("Der Mühlenkai: Eine Erzählung vom Wasser", "Lindqvist, Ebba", ["de"], "epub")
    assert b.download_url == "https://gutenberg.pglaf.org/cache/epub/101/pg101-images-3.epub"
    assert b.cover_url == "https://gutenberg.pglaf.org/cache/epub/101/pg101.cover.medium.jpg"
    assert sorted(ids(await katalog.vorschlaege("KAIWIND"))) == [102, 103]                 # das Hörbuch nicht
    assert ids(await katalog.vorschlaege("kaiwind, zweit")) == [103]
    for umlaute in ("Ölmühlen straßen", "oelmuehlen STRASSEN", "Groesser"):
        assert ids(await katalog.vorschlaege(umlaute)) == [106]
    assert ids(await katalog.vorschlaege("marks", "en")) == [104]
    assert (await katalog.vorschlaege("marks", " DE, en ")).gesamt == 3
    assert (await katalog.vorschlaege("  ,;  ")).buecher == [] and (await katalog.vorschlaege("")).gesamt == 0


async def test_katalog_auch_gepackt_mit_fortschritt_in_gepackten_byte(tmp_path):
    """Der Spiegel bietet den Katalog gepackt an; erkannt wird das am Inhalt, nicht an der Endung."""
    import gzip

    roh = tmp_path / "geholt.teil"
    roh.write_bytes(gzip.compress(INHALT if isinstance(INHALT, bytes) else INHALT.encode()))
    stand: list[tuple[int, int]] = []
    assert bauen(roh, tmp_path / "gepackt.db", {}, lambda a, b: stand.append((a, b))) == 5
    assert stand[-1] == (roh.stat().st_size, roh.stat().st_size)


async def test_ein_kaputter_katalog_ersetzt_den_alten_nie(gebaut, tmp_path):
    kaputt = tmp_path / "wartung.csv"
    kaputt.write_text("<html>Wartung</html>\n", encoding="utf-8")
    with pytest.raises(Katalogfehler, match="kein Katalog"):
        bauen(kaputt, ort(), {})
    leer = tmp_path / "leer.csv"
    leer.write_text(KATALOG.splitlines()[0] + "\n7,Sound,1999-01-01,Nur Ton,de,,,,\n", encoding="utf-8")
    with pytest.raises(Katalogfehler, match="kein Buch"):
        bauen(leer, ort(), {})
    assert (await katalog.stand()).anzahl == 5 and not [p for p in ort().parent.iterdir() if p.name.endswith(".neu")]


async def test_seiten_der_vorschlaege(client, gebaut, monkeypatch, netz):
    monkeypatch.setattr(gutenberg_katalog, "SEITE", 2)
    monkeypatch.setattr(gutenberg_api, "SEITE", 2)
    r = (await client.get("/api/gutenberg/vorschlaege", params={"q": "marks", "sprache": "de", "seite": 1})).json()
    assert (r["gesamt"], len(r["buecher"]), r["vorherige"]) == (3, 2, None) and "seite=2" in r["naechste"] and "q=marks" in r["naechste"]
    r = (await client.get("/api/gutenberg/vorschlaege", params={"q": "marks", "sprache": "de", "seite": 2})).json()
    assert len(r["buecher"]) == 1 and r["naechste"] is None and "seite=1" in r["vorherige"]
    assert netz.zahl() == 0


# -- Holen vom Spiegel ------------------------------------------------------------------------------------------------------

async def test_holen_vom_zweiten_spiegel_mit_fortschritt_in_byte(test_db, netz, frisch, monkeypatch):
    gesehen: list[tuple[int, int | None]] = []
    monkeypatch.setattr(katalog, "_geholt", lambda erledigt, gesamt: gesehen.append((erledigt, gesamt)))
    netz.setze(SPIEGEL_1, AUSFALL)
    netz.setze(SPIEGEL_2, antwort(INHALT, etag='"v1"', last_modified="Sun, 08 Nov 2026 22:43:51 GMT", content_length=str(len(INHALT))))
    assert katalog.starten() and not katalog.starten()                                     # ein Lauf zugleich
    assert (await katalog.stand()).laeuft
    await katalog.warten()
    s = await katalog.stand()
    assert (s.da, s.anzahl, s.stand, s.grund, s.laeuft) == (True, 5, "2026-11-08", "", False)
    assert gesehen[-1] == (len(INHALT), len(INHALT))
    pfad = settings.gutenberg_katalog_pfad
    assert pfad == "/cache/epub/feeds/pg_catalog.csv.gz"                                       # gepackt: 5,6 statt 21 MB
    assert [a.adresse for a in netz.anfragen] == [f"https://{SPIEGEL_1}{pfad}", f"https://{SPIEGEL_2}{pfad}"]
    assert sorted(p.name for p in ort().parent.iterdir() if p.name.startswith("gutenberg_katalog")) == ["gutenberg_katalog.db"]


async def test_abbruch_setzt_am_stand_fort_und_unveraendert_gilt_als_frisch(test_db, netz, frisch):
    halb = len(INHALT) // 2

    def bricht_ab(a):
        in_datei(a.ziel, 200, {"etag": '"v1"', "content-length": str(len(INHALT))}, [INHALT[:halb]], a.hoechstens)
        raise AUSFALL

    def setzt_fort(a):
        assert (a.ziel.versatz, a.kopf.get("If-Range")) == (halb, '"v1"')
        return antwort(INHALT[halb:], status=206, content_range=f"bytes {halb}-{len(INHALT) - 1}/{len(INHALT)}")

    netz.setze(SPIEGEL_1, bricht_ab, setzt_fort)
    netz.setze(SPIEGEL_2, AUSFALL)
    katalog.starten()
    await katalog.warten()
    s = await katalog.stand()
    assert not s.da and s.grund == "Der Spiegel des Project Gutenberg antwortet gerade nicht, der Dienst ist überlastet"
    katalog.starten()
    await katalog.warten()
    s = await katalog.stand()
    assert (s.da, s.anzahl, s.grund) == (True, 5, "")

    def unveraendert(a):
        assert (a.ziel.versatz, a.kopf.get("If-None-Match")) == (0, '"v1"')
        return antwort(status=304)

    netz.setze(SPIEGEL_1, unveraendert)
    alt_machen(ort())
    assert (await katalog.stand()).faellig
    katalog.starten()
    await katalog.warten()
    s = await katalog.stand()
    assert (s.faellig, s.anzahl, s.grund) == (False, 5, "") and s.alter_tage < 1


async def test_eine_fehlerseite_statt_des_katalogs_endet_mit_grund(test_db, netz, frisch):
    netz.setze(SPIEGEL_1, antwort("<html>Wartung</html>"))
    katalog.starten()
    await katalog.warten()
    s = await katalog.stand()
    assert not s.da and s.grund == "Die Datei vom Spiegel ist kein Katalog des Project Gutenberg"
    assert not (ort().parent / gutenberg_katalog.TEIL).exists()                         # das nächste Mal von vorn


async def test_katalog_ueber_die_schnittstelle(client, netz, frisch):
    netz.setze(SPIEGEL_1, antwort(INHALT, etag='"v1"'))
    s = (await client.post("/api/gutenberg/katalog")).json()
    assert s["laeuft"] and s["schritt"] == "holen"
    await katalog.warten()
    s = (await client.get("/api/gutenberg/katalog")).json()
    assert (s["da"], s["anzahl"], s["laeuft"], s["erneuern_tage"]) == (True, 5, False, 7)


# -- Gutendex mit Rückfall ----------------------------------------------------------------------------------------------------

async def test_gutendex_zuerst_bei_stoerung_der_eigene_katalog_mit_klartext(client, netz, gebaut):
    netz.setze(GUTENDEX, antwort({"count": 1, "next": None, "previous": None, "results": [GEMEINFREI_ERSTER]}), AUSFALL)
    r = (await client.get("/api/gutenberg/suche", params={"q": "kaiwind", "sprache": "de"})).json()
    assert (r["herkunft"], r["hinweis"], r["buecher"][0]["gutenberg_id"]) == ("gutendex", "", 102)
    r = await client.get("/api/gutenberg/suche", params={"q": "kaiwind zweiter", "sprache": "de"})
    assert r.status_code == 200
    j = r.json()
    assert j["herkunft"] == "katalog" and [b["gutenberg_id"] for b in j["buecher"]] == [103]
    assert j["hinweis"] == "Gutendex antwortet gerade nicht, der Dienst ist überlastet. Die Treffer kommen aus dem eigenen Katalog; später erneut versuchen."
    gebaut.unlink()
    r = await client.get("/api/gutenberg/suche", params={"q": "nebelhorn"})
    assert r.status_code == 502 and r.json()["detail"] == "Gutendex antwortet gerade nicht, der Dienst ist überlastet. Später erneut versuchen."
    assert not re.search(r"\d", r.json()["detail"])


async def test_gutendex_wartet_so_lange_wie_eingestellt(client, netz, monkeypatch):
    monkeypatch.setattr(settings, "gutenberg_suche_geduld_s", 95)
    netz.setze(GUTENDEX, antwort({"count": 0, "next": None, "previous": None, "results": []}))
    await client.get("/api/gutenberg/suche", params={"q": "nebelhorn"})
    assert netz.anfragen[0].zeit_s == 95


# -- Lücken -------------------------------------------------------------------------------------------------------------------

async def test_fehlender_band_gemeinfrei_nur_wenn_titel_und_autor_passen(gebaut):
    funde = await katalog.abgleichen([
        Buchfrage(titel="Kaiwind. Zweiter Teil", autoren=["Jonte Marks"], sprache="de"),
        Buchfrage(titel="KAIWIND - ERSTER TEIL", autoren=[], sprache="de"),
        Buchfrage(titel="Ueber Oelmuehlen und Strassen", autoren=["Aennchen Groesser"], sprache="de"),
        Buchfrage(titel="Kaiwind: Zweiter Teil", autoren=["Ebba Lindqvist"], sprache="de"),        # anderer Autor
        Buchfrage(titel="The Quiet Quay", autoren=["Jonte Marks"], sprache="fr"),                 # nicht in dieser Sprache
        Buchfrage(titel="Kaiwind: Dritter Teil", autoren=["Jonte Marks"], sprache="de"),           # gleicher Haupttitel, anderer Band
        Buchfrage(titel="Der Mühlenkai", autoren=["Ebba Lindqvist"]),                              # ohne Untertitel
        Buchfrage(titel="", autoren=["Jonte Marks"], sprache="de"),
    ])
    assert [f.gutenberg_id if f else None for f in funde] == [103, 102, 106, None, None, None, 101, None]


async def test_luecke_nennt_das_gemeinfreie_buch_und_holt_es_ueber_die_vorschau(annahme_dienst, auth_headers, test_db, gebaut, monkeypatch, tmp_path):
    s = await sammlung_erstellen(test_db, name="Kaiwind")
    for band in ("1", "3"):
        await buch(test_db, f"Kaiwind {band}", autor="Jonte Marks", sammlung=s, band=band, language="de")
    await speicher.an_setzen(s, True)
    await speicher.nachgeschlagen(s, "de", "dnb", "Kaiwind", Quellergebnis(gesamt=3, baende=[Quellband(nummer=2, titel="Kaiwind. Zweiter Teil", autor="Jonte Marks", quelle="dnb")]))
    await test_db.commit()
    a = (await annahme_dienst.get(f"/api/collections/{s}/luecken", headers=auth_headers)).json()
    luecke = next(e["luecke"] for r in a["reihen"] for e in r["eintraege"] if e["luecke"])
    fund = luecke["gemeinfrei"]
    assert (luecke["nummer"], fund["gutenberg_id"], fund["download_format"], fund["sprachen"]) == (2, 103, "epub", ["de"])

    async def holen(nummer, adresse):
        assert (nummer, adresse) == (103, fund["download_url"])
        datei = tmp_path / "geholt.epub"
        datei.write_bytes(epub("Kaiwind: Zweiter Teil", "Jonte Marks", "de"))
        return datei

    async def kein_umschlag(_adresse):
        return None

    monkeypatch.setattr(gemeinfrei, "download_buch", holen)
    monkeypatch.setattr(gemeinfrei, "download_cover", kein_umschlag)
    angaben = {k: fund[k] for k in ("gutenberg_id", "titel", "autor", "download_url", "download_format", "cover_url")}
    r = await annahme_dienst.post("/api/gutenberg/luecke", headers=auth_headers, json={"buch": angaben, "sammlung_id": s, "band": "2", "sprache": "de"})
    assert r.status_code == 200, r.text
    vid = r.json()["vorschau"]
    eintrag = next(e for e in (await annahme_dienst.get("/api/annahme", headers=auth_headers)).json()["eintraege"] if e["vorschau"] == vid)
    z = await warten(annahme_dienst, auth_headers, eintrag["id"], bestaetigen=False)
    assert (z["stand"], z["quelle"]) == ("bestaetigen", "gemeinfrei")
    ansicht = (await annahme_dienst.get(f"/api/annahme/vorschau/{vid}", headers=auth_headers)).json()
    felder = ansicht["zeilen"][0]["felder"]
    assert (felder["sammlung"]["wert"], felder["sammlung"]["herkunft"], felder["band"]["wert"], felder["band"]["herkunft"]) == (s, "luecke", "2", "luecke")
    assert (await annahme_dienst.post(f"/api/annahme/vorschau/{vid}/uebernehmen", headers=auth_headers, json={})).status_code == 200
    fertig = await warten(annahme_dienst, auth_headers, eintrag["id"])
    neu = await test_db.fetch_one("SELECT sammlung_id, band_nummer, gutenberg_id FROM books WHERE id = ?", (fertig["buch_id"],))
    assert (neu["sammlung_id"], neu["band_nummer"], neu["gutenberg_id"]) == (s, "2", 103)
    a = (await annahme_dienst.get(f"/api/collections/{s}/luecken", headers=auth_headers)).json()
    assert a["reihen"][0]["fehlen"] == []
    r = await annahme_dienst.post("/api/gutenberg/luecke", headers=auth_headers, json={"buch": angaben, "sammlung_id": 99999, "band": "2"})
    assert r.status_code == 422 and r.json()["detail"] == "Sammlung: diese Sammlung gibt es nicht"


# -- Nächtliche Pflege --------------------------------------------------------------------------------------------------------

async def test_pflege_erneuert_nur_einen_alten_katalog(gebaut, netz):
    assert not await pflege.gemeinfreie_erneuern()                                          # frisch
    alt_machen(gebaut)
    netz.setze(SPIEGEL_1, antwort(status=304))
    assert await pflege.gemeinfreie_erneuern()
    await katalog.warten()
    assert not (await katalog.stand()).faellig and netz.anfragen[0].kopf.get("If-None-Match") == '"v1"'
    gebaut.unlink()
    assert not await pflege.gemeinfreie_erneuern()                                          # keinen holt erst das Öffnen
