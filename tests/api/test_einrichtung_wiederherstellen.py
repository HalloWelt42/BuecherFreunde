"""Wiederherstellen aus Sicherung (BF-82) aus drei Quellen: hochgeladene Datei, Sicherungsordner des Geräts, Kellerwolke. Danach
prüft ein Auftrag die Originale; der Bericht nennt erreichbare, über die Prüfsumme wiedergefundene und fehlende, gelöscht wird
nichts. Das alte Gerät ist eine eigene Probedatenbank, die Kellerwolke die Attrappe, alle Orte liegen in tmp_path."""

from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from backend.app.ablage.auszug import FORM
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.einrichtung.pruefung import pruefung
from backend.app.einrichtung.wiederherstellen import einspielen
from backend.app.services.storage import get_sidecar_path
from tests.api.einrichtung_hilfen import als_verwaltung, altes_geraet, laufend, neu, orte, sicherung_von  # noqa: F401 - Fixtures
from tests.api.kellerwolke_attrappe import Kellerwolke

pytestmark = pytest.mark.asyncio
INHALT = {"da": b"%PDF Probeband da", "umgezogen": b"%PDF Probeband umgezogen", "fort": b"%PDF Probeband fort"}
KIND = "0f5a1c2e-7b3d-4e8f-9a10-1b2c3d4e5f61"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _auszug_zip(titel: str) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr("fulltext.txt", f"Volltext von {titel} mit Leuchtturmwärter")
        z.writestr("angaben.json", f'{{"art": "{FORM}", "buch": {{"title": "{titel}"}}}}')
    return puffer.getvalue()


def _wolke(monkeypatch) -> Kellerwolke:
    """Wie die Kellerwolke nach dem Umzug: "da" liegt am alten Ort mit Auszug, "umgezogen" an einem neuen, "fort" nirgends."""
    w = Kellerwolke()
    w.einhaengen(monkeypatch)
    w.knoten_da = w.datei("Apps/BücherFreunde/Bücher/P/Probeband da [1].pdf", INHALT["da"])
    k = w._neu("datei", "Probeband da [1].auszug.zip", w.knoten[w.knoten_da]["parent_id"], _auszug_zip("Probeband da"))
    w.knoten[k] |= {"haupt_id": w.knoten_da, "rolle": "auszug"}
    w.knoten_neu = w.datei("Apps/BücherFreunde/Bücher/Neu/Probeband umgezogen [2].pdf", INHALT["umgezogen"])
    return w


async def _fuellen(alt, w: Kellerwolke) -> None:
    for nr, (name, inhalt) in enumerate(INHALT.items(), start=1):
        await alt.execute("INSERT INTO books(id, hash, title, author, file_format, file_name, file_size, storage_path) VALUES (?, ?, ?, 'Ida Probe', 'pdf', ?, ?, '')",
                          (nr, _sha(inhalt), f"Probeband {name}", f"{name}.pdf", len(inhalt)))
    await alt.execute("INSERT INTO ablage_datei(hash, knoten, name, pfad) VALUES (?, ?, 'Probeband da [1].pdf', 'alt/da')", (_sha(INHALT["da"]), w.knoten_da))
    await alt.execute("INSERT INTO ablage_datei(hash, knoten, name, pfad) VALUES (?, 'k-gibt-es-nicht', 'x.pdf', 'alt/umgezogen')", (_sha(INHALT["umgezogen"]),))
    await alt.execute("INSERT INTO ablage_datei(hash, knoten, name, pfad) VALUES (?, 'k-auch-nicht', 'y.pdf', 'alt/fort')", (_sha(INHALT["fort"]),))
    await alt.execute("INSERT INTO profil(id, name, rolle, stufe) VALUES (?, 'Lotte Probe', 'kind', 'schule')", (KIND,))
    await alt.execute("INSERT INTO nutzer(name, kennwort) VALUES ('Ida Probe', 'scrypt$00$00')")
    await alt.execute("INSERT INTO app_settings(key, value) VALUES ('persoenlich_in_kellerwolke', '0')")


async def _sicherung(tmp_path, monkeypatch, w: Kellerwolke, ziel):
    async def fuellen(alt):
        await _fuellen(alt, w)
    datenbank = await altes_geraet(tmp_path / "altes_geraet", fuellen)
    return sicherung_von(datenbank, monkeypatch, ziel)


async def _bericht_pruefen(client) -> None:
    await pruefung.warten()
    client.headers.update(await als_verwaltung(client))
    b = (await client.get("/api/einrichtung/pruefung/bericht")).json()
    assert b["auftrag"]["stand"] == "fertig" and (b["erreichbar"], b["wiedergefunden"], b["fehlt"], b["texte"]) == (1, 1, 1, 1), b
    je = {e["titel"]: e for e in b["eintraege"]}
    assert je["Probeband umgezogen"]["ergebnis"] == "wiedergefunden" and je["Probeband umgezogen"]["pfad"].endswith("Probeband umgezogen [2].pdf")
    assert je["Probeband fort"]["ergebnis"] == "fehlt"
    assert (await db.fetch_one("SELECT knoten FROM ablage_datei WHERE hash = ?", (_sha(INHALT["umgezogen"]),)))["knoten"] != "k-gibt-es-nicht"
    assert (await db.fetch_one("SELECT COUNT(*) AS n FROM books"))["n"] == 3, "nichts gelöscht, auch das fehlende Buch bleibt"
    assert get_sidecar_path(_sha(INHALT["da"]), "fulltext.txt").read_text().startswith("Volltext von Probeband da")
    treffer = (await client.get("/api/search", params={"q": "Leuchtturmwärter"})).json()
    assert [t["titel"] for t in treffer["treffer"]] == ["Probeband da"], "der Volltext aus dem Auszug ist in der Suche"


async def _danach(client) -> None:
    e = (await client.get("/api/einrichtung")).json()
    assert e["modus"] == "neu" and {s["schluessel"]: s["stand"] for s in e["schritte"]}["sicherung"] == "erledigt"
    assert e["konto"], "das Konto kam mit der Sicherung"
    profile = {p["name"] for p in (await db.fetch_all("SELECT name FROM profil"))}
    assert "Lotte Probe" in profile
    assert (await db.fetch_one("SELECT value FROM app_settings WHERE key = 'persoenlich_in_kellerwolke'"))["value"] == "0", "Einstellungen kamen mit"


async def _wiederherstellen(c, quelle: str, kennung: str, weg: str = "/api/einrichtung/wiederherstellen") -> dict:
    """Erst die Folgen, ohne ihren Stand geht nichts, mit ihm beginnt der Auftrag; zurück kommen die Folgen."""
    f = (await c.get(f"{weg}/folgen", params={"quelle": quelle, "kennung": kennung})).json()
    assert "stand" in f, f
    assert (await c.post(weg, json={"quelle": quelle, "kennung": kennung})).status_code == 422, "nur nach den Folgen"
    r = await c.post(weg, json={"quelle": quelle, "kennung": kennung, "stand": f["stand"]})
    assert r.status_code == 200 and r.json()["art"] == "einspielen", r.text
    assert [t["schluessel"] for t in r.json()["teile"]][:2] == ["holen", "pruefen"]
    await einspielen.warten()
    s = await einspielen.stand()
    assert s.stand == "fertig", s
    return f


async def _hochladen(c, datei, teil: int = 4096) -> str:
    inhalt = datei.read_bytes()
    s = (await c.post("/api/einrichtung/sicherungen/hochladen", json={"name": datei.name, "groesse": len(inhalt), "sha256": _sha(inhalt)})).json()
    ab = s["empfangen"]
    while ab < len(inhalt):
        r = await c.patch(f"/api/einrichtung/sicherungen/hochladen/{s['id']}", content=inhalt[ab:ab + teil], headers={"Upload-Offset": str(ab)})
        assert r.status_code == 200, r.text
        ab = r.json()["empfangen"]
    return s["id"]


async def test_aus_dem_sicherungsordner_des_geraets(neu, client, client_ohne_auth, tmp_path, monkeypatch):
    w = _wolke(monkeypatch)
    datei = await _sicherung(tmp_path, monkeypatch, w, settings.backup_dir)
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "sicherung"})
    e = (await client_ohne_auth.get("/api/einrichtung")).json()
    assert [s["schluessel"] for s in e["schritte"]] == ["orte", "sicherung", "pruefung", "abschluss"], "kein eigenes Konto: es kommt aus der Sicherung"
    liste = (await client_ohne_auth.get("/api/einrichtung/sicherungen", params={"quelle": "geraet"})).json()
    s = liste["sicherungen"][0]
    assert (s["name"], s["buecher"], s["profile"], s["groesse"]) == (datei.name, 3, 2, datei.stat().st_size)
    f = await _wiederherstellen(client_ohne_auth, "geraet", datei.name)
    assert f["ersetzt"] == [] and f["vorher_sichern"] is False, "auf einer neuen Installation ersetzt sie nichts"
    erg = (await client.get("/api/einrichtung/wiederherstellen", headers=await als_verwaltung(client))).json()["ergebnis"]
    assert erg == {"name": datei.name, "buecher": 3, "profile": 2, "version": settings.version, "vorher": ""}
    await _bericht_pruefen(client)
    await _danach(client)
    assert datei.exists() and not (db.db_path.parent / ".wiederherstellen").exists(), "die Sicherung bleibt, der Weg hinein ist leer"


async def test_hochladen_in_teilen_fortsetzbar(neu, client, client_ohne_auth, tmp_path, monkeypatch):
    w = _wolke(monkeypatch)
    datei = await _sicherung(tmp_path, monkeypatch, w, tmp_path / "hochladen")
    inhalt = datei.read_bytes()
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "sicherung"})
    anmeldung = {"name": datei.name, "groesse": len(inhalt), "sha256": _sha(inhalt)}
    s = (await client_ohne_auth.post("/api/einrichtung/sicherungen/hochladen", json=anmeldung)).json()
    assert (s["empfangen"], s["fertig"]) == (0, False) and s["teil_groesse"] > 0
    weg = f"/api/einrichtung/sicherungen/hochladen/{s['id']}"
    assert (await client_ohne_auth.patch(weg, content=inhalt[:1000], headers={"Upload-Offset": "0"})).json()["empfangen"] == 1000
    r = await client_ohne_auth.patch(weg, content=inhalt[:1000], headers={"Upload-Offset": "0"})
    assert r.status_code == 409 and r.json()["empfangen"] == 1000, "der Server nennt den wahren Stand"
    wieder = (await client_ohne_auth.post("/api/einrichtung/sicherungen/hochladen", json=anmeldung)).json()
    assert (wieder["id"], wieder["empfangen"]) == (s["id"], 1000), "nach einem Abbruch geht es am Stand weiter"
    assert (await client_ohne_auth.get("/api/einrichtung/wiederherstellen/folgen", params={"quelle": "datei", "kennung": s["id"]})).status_code == 409
    assert await _hochladen(client_ohne_auth, datei) == s["id"]
    assert (await client_ohne_auth.get(weg)).json()["fertig"]
    await _wiederherstellen(client_ohne_auth, "datei", s["id"])
    await _bericht_pruefen(client)
    await _danach(client)


async def test_hochladen_mit_falscher_pruefsumme(neu, client_ohne_auth):
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "sicherung"})
    s = (await client_ohne_auth.post("/api/einrichtung/sicherungen/hochladen", json={"name": "x.zip", "groesse": 9, "sha256": "0" * 64})).json()
    r = await client_ohne_auth.patch(f"/api/einrichtung/sicherungen/hochladen/{s['id']}", content=b"keine zip", headers={"Upload-Offset": "0"})
    assert r.status_code == 422 and "Prüfsumme" in r.json()["detail"]
    assert (await client_ohne_auth.get(f"/api/einrichtung/sicherungen/hochladen/{s['id']}")).json()["empfangen"] == 0


async def test_aus_der_kellerwolke(neu, client, client_ohne_auth, tmp_path, monkeypatch):
    w = _wolke(monkeypatch)
    datei = await _sicherung(tmp_path, monkeypatch, w, tmp_path / "wolke")
    k = w.datei(f"Apps/BücherFreunde/Sicherung/{datei.name}", datei.read_bytes())
    w.knoten[k]["felder"] = {"buecher": 3, "profile": 2}
    w.datei("Apps/BücherFreunde/Sicherung/notiz.txt", b"keine Sicherung")
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "sicherung"})
    liste = (await client_ohne_auth.get("/api/einrichtung/sicherungen", params={"quelle": "kellerwolke"})).json()
    assert liste["bereit"] and [(s["kennung"], s["buecher"], s["profile"]) for s in liste["sicherungen"]] == [(k, 3, 2)]
    f = await _wiederherstellen(client_ohne_auth, "kellerwolke", k)
    assert f["sicherung"]["buecher"] == 3
    await _bericht_pruefen(client)
    await _danach(client)


async def test_ein_schon_angelegtes_konto_steht_in_den_folgen(neu, client, client_ohne_auth, tmp_path, monkeypatch):
    w = _wolke(monkeypatch)
    datei = await _sicherung(tmp_path, monkeypatch, w, settings.backup_dir)
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "sicherung"})
    await client_ohne_auth.post("/api/anmeldung/einrichten", json={"kennung": "Mira Probe", "passwort": "ein langes Kennwort"})
    weg = "/api/einrichtung/wiederherstellen/folgen"
    assert (await client_ohne_auth.get(weg, params={"quelle": "geraet", "kennung": datei.name})).status_code == 401
    f = await _wiederherstellen(client, "geraet", datei.name)
    assert f["ersetzt"] == ["Das Konto Mira Probe wird durch das aus der Sicherung ersetzt"]
    assert [z["name"] for z in await db.fetch_all("SELECT name FROM nutzer")] == ["Ida Probe"], "das Konto kam aus der Sicherung"


async def test_nie_auf_einem_bestand_oder_einer_laufenden_installation(laufend, client, tmp_path, monkeypatch):
    w = _wolke(monkeypatch)
    datei = await _sicherung(tmp_path, monkeypatch, w, settings.backup_dir)
    r = await client.get("/api/einrichtung/wiederherstellen/folgen", params={"quelle": "geraet", "kennung": datei.name})
    assert r.status_code == 409
    r = await client.post("/api/einrichtung/wiederherstellen", json={"quelle": "geraet", "kennung": datei.name, "stand": "x"})
    assert r.status_code == 409
    assert (await db.fetch_one("SELECT COUNT(*) AS n FROM books"))["n"] == 0


async def test_nie_ueber_vorhandene_buecher(neu, client_ohne_auth, tmp_path, monkeypatch, test_db):
    from tests.api.conftest import buch_erstellen

    w = _wolke(monkeypatch)
    datei = await _sicherung(tmp_path, monkeypatch, w, settings.backup_dir)
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "sicherung"})
    await buch_erstellen(test_db, title="Schon da", hash="e" * 64)
    r = await client_ohne_auth.get("/api/einrichtung/wiederherstellen/folgen", params={"quelle": "geraet", "kennung": datei.name})
    assert r.status_code == 409 and "nicht leer" in r.json()["detail"]
    assert [b["title"] for b in await db.fetch_all("SELECT title FROM books")] == ["Schon da"]


async def test_zurueckspielen_unter_einstellungen_mit_folgen_und_auftrag(laufend, client, tmp_path, monkeypatch, test_db):
    """Der alte Weg `/api/backup/restore`: dieselben Folgen, derselbe Auftrag; vorher eine Sicherung des jetzigen Stands."""
    from backend.app.core.config import Settings
    from backend.app.services import sicherung
    from tests.api.conftest import buch_erstellen

    w = _wolke(monkeypatch)
    datei = await _sicherung(tmp_path, monkeypatch, w, tmp_path / "zum_zurueckspielen")
    monkeypatch.setattr(Settings, "database_path", property(lambda _s: db.db_path))
    await buch_erstellen(test_db, title="Jetziger Stand", hash="e" * 64)
    k = w.datei(f"Apps/BücherFreunde/Sicherung/{datei.name}", datei.read_bytes())
    f = await _wiederherstellen(client, "kellerwolke", k, weg="/api/backup/restore")
    assert f["vorher_sichern"] and any("Der Bestand mit 1 Büchern" in s for s in f["ersetzt"]), f
    titel = {z["title"] for z in await db.fetch_all("SELECT title FROM books")}
    assert titel == {"Probeband da", "Probeband umgezogen", "Probeband fort"}
    erg = await einspielen.ergebnis()
    vorher = settings.backup_dir / erg.vorher
    assert vorher.exists() and sicherung.inhalt(vorher).buecher == 1, "der jetzige Stand liegt vorher gesichert im Sicherungsordner"
    assert (await db.fetch_one("SELECT modus FROM einrichtung"))["modus"] == "aus", "die Einrichtung bleibt abgeschlossen"
    await pruefung.warten()
    assert (await pruefung.stand()).stand == "fertig"


async def test_buch_traegt_den_hinweis_aus_dem_pruefbericht(laufend, client, test_db):
    from tests.api.conftest import buch_erstellen

    da = await buch_erstellen(test_db, title="Da", hash="1" * 64)
    fort = await buch_erstellen(test_db, title="Fort", hash="2" * 64)
    await db.execute("INSERT INTO original_befund(book_id, ergebnis, text) VALUES (?, 'erreichbar', ''), (?, 'fehlt', 'Weder am alten Ort noch über die Prüfsumme')",
                     (da, fort))
    await db.commit()
    assert (await client.get(f"/api/books/{da}")).json()["original"] is None
    h = (await client.get(f"/api/books/{fort}")).json()["original"]
    assert h["text"] == "Weder am alten Ort noch über die Prüfsumme" and h["geprueft_am"]


async def test_sicherungen_auch_in_der_kellerwolke_einstellbar(laufend, client, monkeypatch, test_db):
    from backend.app.core.config import Settings
    from tests.api.conftest import buch_erstellen

    w = Kellerwolke()
    w.einhaengen(monkeypatch)
    monkeypatch.setattr(Settings, "database_path", property(lambda _s: db.db_path))
    r = (await client.post("/api/backup/create")).json()
    assert r["neu"]
    abgelegt = [z for z in w.knoten.values() if w.pfad(z["id"]) == f"Apps/BücherFreunde/Sicherung/{r['filename']}"]
    assert len(abgelegt) == 1 and abgelegt[0]["felder"] == {"buecher": 0, "profile": 1, "version": settings.version}
    liste = (await client.get("/api/einrichtung/sicherungen", params={"quelle": "kellerwolke"})).json()
    assert [s["name"] for s in liste["sicherungen"]] == [r["filename"]]

    await client.put("/api/kellerwolke/einstellungen", json={"sicherungen_ablegen": False})
    assert (await client.get("/api/kellerwolke/einstellungen")).json()["sicherungen_ablegen"] is False
    await buch_erstellen(test_db, title="Neu seit der Sicherung", hash="9" * 64)
    assert (await client.post("/api/backup/create")).json()["neu"]
    assert sum(1 for z in w.knoten.values() if z["name"].startswith("buecherfreunde_backup_")) == 1, "ausgeschaltet: nur auf dem Gerät"
