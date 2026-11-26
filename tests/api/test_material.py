"""Begleitmaterial je Buch (BF-81): hinzufügen über die Annahme, Liste, Öffnen und Herunterladen, Umbenennen, Entfernen nach der
Folgenvorschau, Suche im Material; mit beiden Ablagen (Gerät und nachgebaute Kellerwolke), Erkennen neben dem Original, Folgen
für das Buch (privat, Freigaben, Löschen). Alle Bücher, Dateien und Namen sind erfunden."""

from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from backend.app.core.database import db
from backend.app.material import ablage
from backend.app.material.erkennen import abgleich
from backend.app.material.textlauf import textlauf
from backend.app.services.storage import get_storage_path
from tests.api.conftest import buch_erstellen
from tests.api.familie_hilfen import familie_anlegen
from tests.api.kellerwolke_attrappe import Kellerwolke
from tests.api.test_annahme_api import warten
from tests.api.test_vorschau import pdf


async def material_hochladen(client, kopf, buch: int, name: str, inhalt: bytes, entpacken: bool = False) -> dict:
    r = await client.post(f"/api/books/{buch}/material", headers=kopf,
                          json={"name": name, "groesse": len(inhalt), "sha256": hashlib.sha256(inhalt).hexdigest(), "entpacken": entpacken})
    assert r.status_code == 200, r.text
    z = r.json()
    while z["stand"] in ("wartet", "laedt") and z["empfangen"] < len(inhalt):
        r = await client.patch(f"/api/annahme/{z['id']}", headers={**kopf, "Upload-Offset": str(z["empfangen"])},
                               content=inhalt[z["empfangen"]:z["empfangen"] + z["teil_groesse"]])
        z = r.json()
    return await warten(client, kopf, z["id"])


async def liste(client, kopf, buch: int) -> dict:
    r = await client.get(f"/api/books/{buch}/material", headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()


# -- auf dem Gerät -------------------------------------------------------------------------------------------------------

async def test_material_auf_dem_geraet_von_hinzufuegen_bis_entfernen(annahme_dienst, auth_headers, test_db):
    buch = await buch_erstellen(test_db, hash="mat-geraet", title="Sensoren zum Selbstbauen", author="Lutz Probe")
    z = await material_hochladen(annahme_dienst, auth_headers, buch, "Lösungen.pdf", pdf("Spannungsteiler am Eingang", 2))
    assert z["stand"] == "fertig" and z["buch_id"] == buch and "Begleitmaterial" in z["text"], z
    [m] = (l := await liste(annahme_dienst, auth_headers, buch))["material"]
    assert (m["name"], m["art"], m["art_name"], m["ort"], m["oeffnen"], m["lesbar"], m["text_stand"]) == \
        ("Lösungen.pdf", "pdf", "PDF", "geraet", True, True, "offen")
    assert l["ort"] == "geraet" and m["pfad"] == str(get_storage_path("mat-geraet") / ablage.ORDNER / "Lösungen.pdf")
    assert (await annahme_dienst.get(f"/api/books/{buch}", headers=auth_headers)).json()["material"] == 1

    assert await textlauf.runde() == 1
    treffer = (await annahme_dienst.get("/api/search", params={"q": "Spannungsteiler"}, headers=auth_headers)).json()
    assert sorted((t["buch_id"], t["titel"], t["name"], t["seite"]) for t in treffer["material"]) == \
        [(buch, "Sensoren zum Selbstbauen", "Lösungen.pdf", 1), (buch, "Sensoren zum Selbstbauen", "Lösungen.pdf", 2)]   # je Seite ein Treffer
    assert "<mark>Spannungsteiler</mark>" in treffer["material"][0]["auszug"]

    datei = await annahme_dienst.get(f"/api/books/{buch}/material/{m['id']}/datei", headers=auth_headers)
    assert datei.status_code == 200 and datei.headers["content-type"] == "application/pdf" and "inline" in datei.headers["content-disposition"]
    laden = await annahme_dienst.get(f"/api/books/{buch}/material/{m['id']}/datei", params={"herunterladen": True}, headers=auth_headers)
    assert "attachment" in laden.headers["content-disposition"]

    neu = await annahme_dienst.patch(f"/api/books/{buch}/material/{m['id']}", headers=auth_headers, json={"name": "Lösungen zur 2. Auflage"})
    assert neu.status_code == 200 and neu.json()["name"] == "Lösungen zur 2. Auflage.pdf"            # die Endung bleibt
    assert (get_storage_path("mat-geraet") / ablage.ORDNER / "Lösungen zur 2. Auflage.pdf").is_file()
    assert (await annahme_dienst.patch(f"/api/books/{buch}/material/{m['id']}", headers=auth_headers, json={"name": "a/b"})).status_code == 422

    folgen = (await annahme_dienst.get(f"/api/books/{buch}/material/{m['id']}/folgen", headers=auth_headers)).json()
    assert (folgen["papierkorb"], folgen["suche"], folgen["seiten"], folgen["titel"]) == (False, True, 2, "Sensoren zum Selbstbauen")
    assert (await annahme_dienst.delete(f"/api/books/{buch}/material/{m['id']}", params={"stand": "alt"}, headers=auth_headers)).status_code == 409
    r = await annahme_dienst.delete(f"/api/books/{buch}/material/{m['id']}", params={"stand": folgen["stand"]}, headers=auth_headers)
    assert r.status_code == 200
    assert (await liste(annahme_dienst, auth_headers, buch))["material"] == []
    assert not (get_storage_path("mat-geraet") / ablage.ORDNER / "Lösungen zur 2. Auflage.pdf").exists()
    assert (await annahme_dienst.get("/api/search", params={"q": "Spannungsteiler"}, headers=auth_headers)).json()["material"] == []
    assert (await annahme_dienst.get(f"/api/books/{buch}", headers=auth_headers)).status_code == 200           # das Buch bleibt


async def test_zip_als_material_ausgepackt_oder_ganz(annahme_dienst, auth_headers, test_db):
    buch = await buch_erstellen(test_db, hash="mat-zip", title="Werkbank für Kinder", author="Lutz Probe")
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr("code/blinken.py", b"print('an')\n")
        z.writestr("Messwerte.csv", b"a;b\n1;2\n")
    inhalt = puffer.getvalue()
    assert (await material_hochladen(annahme_dienst, auth_headers, buch, "Beispielcode.zip", inhalt))["stand"] == "fertig"
    assert [m["name"] for m in (await liste(annahme_dienst, auth_headers, buch))["material"]] == ["Beispielcode.zip"]
    assert (await material_hochladen(annahme_dienst, auth_headers, buch, "Noch einmal.zip", inhalt))["stand"] == "da"   # gleiche Datei
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr("code/blinken.py", b"print('an')\n")
        z.writestr("Messwerte.csv", b"a;b\n1;2\n3;4\n")
    zip_ = await material_hochladen(annahme_dienst, auth_headers, buch, "Ausgepackt.zip", puffer.getvalue(), entpacken=True)
    assert zip_["stand"] == "entpackt"
    for _ in range(100):
        namen = [m["name"] for m in (await liste(annahme_dienst, auth_headers, buch))["material"]]
        if len(namen) == 3:
            break
        await warten(annahme_dienst, auth_headers, zip_["id"])
    assert sorted(namen) == ["Beispielcode.zip", "Messwerte.csv", "blinken.py"]


# -- in der Kellerwolke --------------------------------------------------------------------------------------------------

@pytest.fixture
def wolke(monkeypatch):
    w = Kellerwolke()
    w.einhaengen(monkeypatch)
    return w


async def buch_in_der_wolke(test_db, w: Kellerwolke, titel: str = "Sensoren zum Selbstbauen") -> tuple[int, str]:
    inhalt = pdf(titel)
    summe = hashlib.sha256(inhalt).hexdigest()
    buch = await buch_erstellen(test_db, hash=summe, title=titel, author="Lutz Probe")
    name = f"{titel} - Lutz Probe [{buch}].pdf"
    k = w.datei(f"Apps/BücherFreunde/Bücher/S/{name}", inhalt)
    await test_db.execute("INSERT INTO ablage_datei (hash, knoten, name, pfad, groesse) VALUES (?, ?, ?, ?, ?)",
                          (summe, k, name, f"Apps/BücherFreunde/Bücher/S/{name}", len(inhalt)))
    await test_db.commit()
    return buch, k


async def test_material_in_der_kellerwolke_als_begleiter_des_originals(annahme_dienst, auth_headers, test_db, wolke):
    buch, original = await buch_in_der_wolke(test_db, wolke)
    z = await material_hochladen(annahme_dienst, auth_headers, buch, "Lösungen.pdf", pdf("Ohmsches Gesetz"))
    assert z["stand"] == "fertig", z
    [m] = (await liste(annahme_dienst, auth_headers, buch))["material"]
    [b] = [b for b in wolke.begleiter(original) if b["rolle"].startswith("material_")]
    assert b["name"] == f"Sensoren zum Selbstbauen - Lutz Probe [{buch}].material.loesungen.pdf" and b["rolle"].removeprefix("material_").isalpha()
    assert (m["ort"], m["pfad"], m["name"]) == ("kellerwolke", b["pfad"], "Lösungen.pdf")
    assert await textlauf.runde() == 1
    assert (await annahme_dienst.get("/api/search", params={"q": "Ohmsches"}, headers=auth_headers)).json()["material"][0]["name"] == "Lösungen.pdf"

    neu = (await annahme_dienst.patch(f"/api/books/{buch}/material/{m['id']}", headers=auth_headers, json={"name": "Korrekturen"})).json()
    assert neu["name"] == "Korrekturen.pdf" and wolke.knoten[b["id"]]["name"].endswith(".material.korrekturen.pdf")
    folgen = (await annahme_dienst.get(f"/api/books/{buch}/material/{m['id']}/folgen", headers=auth_headers)).json()
    assert folgen["papierkorb"] is True
    await annahme_dienst.delete(f"/api/books/{buch}/material/{m['id']}", params={"stand": folgen["stand"]}, headers=auth_headers)
    assert wolke.knoten[b["id"]]["geloescht"] and not wolke.knoten[original]["geloescht"]       # nur das Material


async def test_erkennen_neben_dem_original_erst_ja_macht_material(annahme_dienst, auth_headers, test_db, wolke):
    buch, original = await buch_in_der_wolke(test_db, wolke)
    eigene = wolke.datei("Apps/BücherFreunde/Bücher/S/Sensoren zum Selbstbauen - Lutz Probe - Lösungen.pdf", pdf("Lösungsweg"))
    karte = wolke.datei("Apps/BücherFreunde/Bücher/S/Sensoren zum Selbstbauen - Lutz Probe (Karte).png", b"\x89PNG bild")
    wolke.datei("Apps/BücherFreunde/Bücher/S/Sensorenkunde für alle.pdf", pdf("Fremd"))               # gehört nicht dazu
    assert await abgleich.lauf() == 2
    assert await abgleich.lauf() == 0                                                                # jede Datei nur einmal
    funde = (await liste(annahme_dienst, auth_headers, buch))["funde"]
    assert sorted(f["knoten"] for f in funde) == sorted([eigene, karte])
    assert (await liste(annahme_dienst, auth_headers, buch))["material"] == []                      # nichts still übernommen
    r = await annahme_dienst.post(f"/api/books/{buch}/material/funde/{eigene}/annehmen", headers=auth_headers)
    assert r.status_code == 200 and r.json()["name"] == "Lösungen.pdf" and r.json()["herkunft"] == "erkannt"
    assert wolke.knoten[eigene]["haupt_id"] == original and wolke.knoten[eigene]["rolle"].startswith("material_")
    assert (await annahme_dienst.post(f"/api/books/{buch}/material/funde/{karte}/ablehnen", headers=auth_headers)).status_code == 200
    assert await abgleich.lauf() == 0 and (await liste(annahme_dienst, auth_headers, buch))["funde"] == []
    assert wolke.knoten[karte]["haupt_id"] is None                                                   # bleibt, wo sie ist
    stand = (await annahme_dienst.get("/api/material/stand", headers=auth_headers)).json()
    assert stand["abgleich"]["bereit"] and stand["abgleich"]["ordner_gesamt"] == 1


# -- Folgen für das Buch ---------------------------------------------------------------------------------------------------

async def material_eintragen(test_db, buch: int, name: str, text: str = "") -> str:
    """Material direkt in der Tabelle (für die Sichtbarkeit), mit Text in der Suche."""
    nr = hashlib.md5(f"{buch}{name}".encode()).hexdigest()
    nr = f"{nr[:8]}-{nr[8:12]}-4{nr[13:16]}-8{nr[17:20]}-{nr[20:32]}"
    await test_db.execute("INSERT INTO buch_material (id, buch_id, name, art, groesse, ort, pfad, herkunft, text_stand, text_seiten) "
                          "VALUES (?, ?, ?, 'pdf', 10, 'geraet', '/nirgends', 'buchseite', ?, 1)", (nr, buch, name, "fertig" if text else "ohne"))
    if text:
        await test_db.execute("INSERT INTO material_text (material, buch_id, seite, inhalt) VALUES (?, ?, 1, ?)", (nr, buch, text))
    await test_db.commit()
    return nr


async def test_material_folgt_dem_buch_privat_freigaben_kinder(client, test_db):
    f = await familie_anlegen(client, test_db)
    await material_eintragen(test_db, f.buch["mond"], "Ausmalbild Mond.pdf", "Krater auf dem Mond zum Ausmalen")
    await material_eintragen(test_db, f.buch["zebra"], "Zebra Lösungen.pdf", "Streifengeheimnis")
    await material_eintragen(test_db, f.buch["steuer"], "Formular.pdf", "Steuerformular Krater")
    ada, bert, clara, dora = (f.kopf[n] for n in ("ada", "bert", "clara", "dora"))

    assert (await client.get(f"/api/books/{f.buch['zebra']}/material", headers=ada)).status_code == 404     # privat für Bert
    assert len((await client.get(f"/api/books/{f.buch['zebra']}/material", headers=bert)).json()["material"]) == 1
    assert len((await client.get(f"/api/books/{f.buch['mond']}/material", headers=clara)).json()["material"]) == 1   # freigegeben: lesen
    assert (await client.get(f"/api/books/{f.buch['steuer']}/material", headers=dora)).status_code == 404   # nicht freigegeben
    [m] = (await client.get(f"/api/books/{f.buch['mond']}/material", headers=clara)).json()["material"]
    assert (await client.patch(f"/api/books/{f.buch['mond']}/material/{m['id']}", headers=clara, json={"name": "x"})).status_code == 403
    assert (await client.get(f"/api/books/{f.buch['mond']}/material/{m['id']}/folgen", headers=dora)).status_code == 403
    assert (await client.post(f"/api/books/{f.buch['mond']}/material", headers=dora,
                              json={"name": "x.pdf", "groesse": 1})).status_code == 403

    treffer = (await client.get("/api/search", params={"q": "Krater"}, headers=dora)).json()["material"]
    assert [t["name"] for t in treffer] == ["Ausmalbild Mond.pdf"]                                    # Steuer ist nicht frei
    assert (await client.get("/api/search", params={"q": "Streifengeheimnis"}, headers=ada)).json()["material"] == []
    assert len((await client.get("/api/search", params={"q": "Streifengeheimnis"}, headers=bert)).json()["material"]) == 1

    privat = await client.put(f"/api/books/{f.buch['mond']}/privat", json={"privat": True}, headers=ada)
    assert privat.json() == {"privat": True, "material": 1}
    freigaben = (await client.get(f"/api/familie/profile/{f.ids['dora']}/freigaben", headers=ada)).json()
    assert [(b["id"], b["material"]) for b in freigaben["buecher"]] == [(f.buch["mond"], 1)]


async def test_loeschfolgen_nennen_material_und_formate(annahme_dienst, auth_headers, test_db):
    buch = await buch_erstellen(test_db, hash="mat-loesch", title="Kleines Gartenbuch", author="Rosa Probe", file_format="pdf")
    ordner = get_storage_path("mat-loesch")
    ordner.mkdir(parents=True)
    (ordner / "Kleines Gartenbuch.pdf").write_bytes(b"%PDF")
    await material_hochladen(annahme_dienst, auth_headers, buch, "Pflanzplan.png", b"\x89PNG plan")
    weiteres = get_storage_path("mat-loesch-epub")
    weiteres.mkdir(parents=True)
    (weiteres / "Kleines Gartenbuch.epub").write_bytes(b"epub")
    await test_db.execute("INSERT INTO buch_datei (id, buch_id, hash, format, name, groesse) VALUES (?, ?, 'mat-loesch-epub', 'epub', "
                          "'Kleines Gartenbuch.epub', 4)", ("0b0b0b0b-0000-4000-8000-000000000001", buch))
    await test_db.commit()
    f = (await annahme_dienst.get(f"/api/books/{buch}/loeschfolgen", headers=auth_headers)).json()
    assert f["material"] == [{"pfad": "Pflanzplan.png", "groesse": 9, "papierkorb": False}]
    assert f["formate"] == [{"pfad": "Kleines Gartenbuch.epub", "groesse": 4, "papierkorb": False}]
    assert (await annahme_dienst.delete(f"/api/books/{buch}", headers=auth_headers)).status_code == 200
    assert not ordner.exists() and not weiteres.exists()                                            # Buchordner mit Material fort
    assert await db.fetch_one("SELECT 1 AS da FROM buch_material WHERE buch_id = ?", (buch,)) is None
    assert await db.fetch_one("SELECT 1 AS da FROM buch_datei WHERE buch_id = ?", (buch,)) is None
