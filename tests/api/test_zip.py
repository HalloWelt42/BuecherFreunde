"""ZIP beim Hochladen (BF-80): auf dem Server ausgepackt, Teil für Teil; Ordnernamen schlagen Kategorie oder Etikett vor,
Dateien mit dem Namen eines Buchs werden sein Material, derselbe Name in einem anderen Format ein weiteres Format, der Rest
steht mit Grund unter "nicht übernommen"; Grenzen gegen ZIP-Bomben und Pfade mit `..`. Alles erfunden."""

from __future__ import annotations

import asyncio
import io
import os
import zipfile

from backend.app.core.config import settings
from backend.app.core.database import db
from tests.api.katalog_hilfen import katalog_annehmen, nummern
from tests.api.test_annahme_api import warten
from tests.api.test_vorschau import bis_bestaetigen, pdf, zeile

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def zip_aus(dateien: dict[str, bytes]) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, inhalt in dateien.items():
            z.writestr(name, inhalt)
    return puffer.getvalue()


async def ausgepackt(client, kopf, name: str, inhalt: bytes) -> tuple[dict, dict]:
    """Hochladen und warten, bis alle Teile gelesen sind; liefert die ZIP und ihre Vorschau."""
    z = await bis_bestaetigen(client, kopf, name, inhalt)
    for _ in range(300):
        v = (await client.get(f"/api/annahme/vorschau/{z['vorschau']}", headers=kopf)).json()
        if v["laeuft"] == 0:
            return (await client.get(f"/api/annahme/{z['id']}", headers=kopf)).json(), v
        await asyncio.sleep(.1)
    raise AssertionError(v)


async def grenzen(client, kopf, **zip_) -> None:
    jetzt = (await client.get("/api/annahme/einstellungen", headers=kopf)).json()
    r = await client.put("/api/annahme/einstellungen", headers=kopf, json=jetzt | {"zip": jetzt["zip"] | zip_})
    assert r.status_code == 200, r.text


async def test_zip_mit_ordnern_material_format_und_rest(annahme_dienst, auth_headers):
    katalog = nummern(await katalog_annehmen(annahme_dienst))
    innen = zip_aus({"main.py": b"print('Hallo Werkbank')\n"})
    zip_, v = await ausgepackt(annahme_dienst, auth_headers, "Probe-Ablage.zip", zip_aus({
        "Krimi/Lindgrün ermittelt.pdf": pdf("Lindgrün im Moor", 50),
        "Krimi/Lindgrün ermittelt - Lageplan.png": PNG,
        "Werkstatt/Bastelbuch Holz.pdf": pdf("Holz und Leim", 50),
        "Werkstatt/Bastelbuch Holz.md": b"# Bastelbuch Holz\n\nHobeln, schleifen, leimen.\n",
        "Werkstatt/Bastelbuch Holz - Beispielcode.zip": innen,
        "Haus/Einkaufsliste.xlsx": b"keine echte Tabelle",
        "Haus/Bild ohne Buch.png": PNG,
        "__MACOSX/Krimi/._Lindgrün ermittelt.pdf": b"x",
    }))
    assert zip_["stand"] == "entpackt" and "8 Dateien ausgepackt" in zip_["text"], zip_
    krimi, lageplan = zeile(v, "Lindgrün ermittelt.pdf"), zeile(v, "Lindgrün ermittelt - Lageplan.png")
    holz, holz_md, code = zeile(v, "Bastelbuch Holz.pdf"), zeile(v, "Bastelbuch Holz.md"), zeile(v, "Bastelbuch Holz - Beispielcode.zip")
    assert (krimi["ordner"], krimi["felder"]["kategorien"]) == ("Krimi", {"wert": [katalog["romane/krimi"]], "herkunft": "ordner", "grund": ""})
    assert (holz["felder"]["etiketten"]["wert"], holz["felder"]["etiketten"]["herkunft"]) == (["Werkstatt"], "ordner")
    assert (lageplan["rolle"], lageplan["felder"]["art"]["herkunft"], lageplan["felder"]["ziel"]["aufnahme"]) == ("material", "datei", krimi["id"])
    assert krimi["material"] == 1 and lageplan["ablage"]["ordner"] == "im Buchordner unter Material"
    assert code["rolle"] == "material" and code["felder"]["ziel"]["aufnahme"] in (holz["id"], holz_md["id"])
    assert (holz_md["felder"]["doppel"]["art"], holz_md["felder"]["ziel"]["aufnahme"]) == ("format", holz["id"])
    rest = {z["name"]: z for z in v["zeilen"] if z["rolle"] == "rest"}
    assert rest["Einkaufsliste.xlsx"]["felder"]["nicht"] == "Tabelle ohne Buch gleichen Namens"
    assert rest["Bild ohne Buch.png"]["felder"]["nicht"] == "Bild ohne Buch gleichen Namens"
    assert rest["._Lindgrün ermittelt.pdf"]["stand"] == "format" and "System" in rest["._Lindgrün ermittelt.pdf"]["text"]
    assert v["zaehler"]["material"] == 2 and v["zaehler"]["formate"] == 1 and v["zaehler"]["nicht"] == 3

    allein = await annahme_dienst.post(f"/api/annahme/vorschau/{v['id']}/uebernehmen", headers=auth_headers, json={"ids": [lageplan["id"]]})
    assert allein.status_code == 422 and "bitte beide übernehmen" in allein.json()["detail"]          # Material ohne sein Buch
    r = await annahme_dienst.post(f"/api/annahme/vorschau/{v['id']}/uebernehmen", headers=auth_headers, json={})
    assert r.status_code == 200 and r.json()["weiter"] == 5, r.text
    for z in (krimi, lageplan, holz, holz_md, code):
        assert (await warten(annahme_dienst, auth_headers, z["id"]))["stand"] == "fertig", z["name"]
    v = (await annahme_dienst.get(f"/api/annahme/vorschau/{v['id']}", headers=auth_headers)).json()
    assert v["stand"] == "uebernommen" and v["hinweis"] == "3 Dateien blieben im Eingang"
    buch_holz = (await annahme_dienst.get(f"/api/annahme/{holz['id']}", headers=auth_headers)).json()["buch_id"]
    buch = (await annahme_dienst.get(f"/api/books/{buch_holz}", headers=auth_headers)).json()
    assert [d["format"] for d in buch["dateien"]] == ["pdf", "md"] and buch["material"] == 1
    material = (await annahme_dienst.get(f"/api/books/{buch_holz}/material", headers=auth_headers)).json()["material"]
    assert [(m["name"], m["art"], m["herkunft"]) for m in material] == [("Beispielcode.zip", "zip", "hochladen")]
    etiketten = await db.fetch_all("SELECT name FROM book_labels WHERE book_id = ?", (buch_holz,))
    assert [e["name"] for e in etiketten] == ["Werkstatt"]
    lindgruen = (await annahme_dienst.get(f"/api/annahme/{krimi['id']}", headers=auth_headers)).json()["buch_id"]
    assert [m["name"] for m in (await annahme_dienst.get(f"/api/books/{lindgruen}/material", headers=auth_headers)).json()["material"]] == ["Lageplan.png"]
    assert (await annahme_dienst.get("/api/books", headers=auth_headers)).json()["gesamt"] == 2
    liegen = sorted(p.name for p in settings.eingang_dir.rglob("*") if p.is_file())
    assert liegen == ["Bild ohne Buch.png", "Einkaufsliste.xlsx", "Probe-Ablage.zip"]         # nichts wird von selbst weggeräumt


async def test_zip_grenzen_bombe_und_pfade(annahme_dienst, auth_headers, tmp_path):
    await grenzen(annahme_dienst, auth_headers, dateien=3)
    zu_viele, _ = await ausgepackt(annahme_dienst, auth_headers, "Viele.zip", zip_aus({f"{n}.txt": b"Text" for n in range(4)}))
    assert zu_viele["stand"] == "kaputt" and "4 Dateien, erlaubt sind 3" in zu_viele["text"]

    await grenzen(annahme_dienst, auth_headers, dateien=100, datei_mb=3, verhaeltnis=50, tiefe=2)
    zip_, v = await ausgepackt(annahme_dienst, auth_headers, "Grenzen.zip", zip_aus({
        "gross.pdf": os.urandom(4 * 1024 * 1024),
        "bombe.txt": b"\x00" * (2 * 1024 * 1024),
        "../boese.pdf": pdf("Böse"),
        "/absolut.pdf": pdf("Absolut"),
        "a/b/c/tief.pdf": pdf("Tief"),
        "gut.md": b"# Gut\n\nEin kurzer Text.\n",
    }))
    assert zip_["stand"] == "entpackt"
    gruende = {z["name"]: z["text"] for z in v["zeilen"] if z["rolle"] == "rest"}
    assert "erlaubt sind 3 MB je Datei" in gruende["gross.pdf"]
    assert "stark gepackt" in gruende["bombe.txt"]
    assert "führt aus der ZIP heraus" in gruende["boese.pdf"] and "führt aus der ZIP heraus" in gruende["absolut.pdf"]
    assert "3 Ordner tief, erlaubt sind 2" in gruende["tief.pdf"]
    assert zeile(v, "gut.md")["rolle"] == "buch"
    assert not (tmp_path / "boese.pdf").exists() and not (settings.eingang_dir.parent / "boese.pdf").exists()
    ausgepackte = sorted(p.name for p in settings.eingang_dir.rglob("*") if p.is_file() and p.suffix != ".zip")
    assert ausgepackte == ["gut.md"]                                                          # nur, was die Grenzen erlauben


async def test_auspacken_geht_nach_einer_unterbrechung_weiter(annahme_dienst, auth_headers, test_db):
    from backend.app.annahme.dienst import annahme

    zip_, v = await ausgepackt(annahme_dienst, auth_headers, "Unterbrochen.zip", zip_aus({"Eins.md": b"# Eins\n\nText.\n", "Zwei.md": b"# Zwei\n\nText.\n"}))
    zwei = zeile(v, "Zwei.md")
    (settings.eingang_dir / str(zwei["id"]) / "Zwei.md").unlink()                       # mitten im zweiten Teil abgebrochen
    await test_db.execute("UPDATE aufnahme SET stand = 'entpacken', gelesen = NULL, zuordnung = NULL WHERE id IN (?, ?)", (zip_["id"], zwei["id"]))
    await test_db.commit()
    await annahme._entpacken(await db.fetch_one("SELECT * FROM aufnahme WHERE id = ?", (zip_["id"],)))
    teile = await db.fetch_all("SELECT name, stand FROM aufnahme WHERE teil_von = ? ORDER BY id", (zip_["id"],))
    assert [z["name"] for z in teile] == ["Eins.md", "Zwei.md"]                         # kein Teil doppelt
    assert (settings.eingang_dir / str(zwei["id"]) / "Zwei.md").is_file()
    assert (await warten(annahme_dienst, auth_headers, zwei["id"], bestaetigen=False))["stand"] == "bestaetigen"
