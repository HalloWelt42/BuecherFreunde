"""Umzug mit Einmalcode (BF-82). Altes Gerät: frische Sicherung und Code, nur einmal, nur kurz, wenige Versuche; das alte Gerät
bleibt unverändert. Neues Gerät: holt mit Adresse und Code Sicherung, Einstellungen und Schlüssel (nur in die Schlüsseldatei),
dann ohne Kellerwolke "Originale kopieren" (fortsetzbar, mit Prüfsummen) oder "Ort übernehmen" (nur prüfen).

Beide Geräte sind eigene Probedatenbanken in tmp_path: erst spricht der Test mit den echten Wegen des alten Geräts und schneidet
ihre Antworten mit, dann spielt ein Netz im Speicher sie dem neuen Gerät vor. Nichts geht ins Netz."""

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass

import httpx
import pytest

from backend.app.core import schluessel
from backend.app.core.config import Settings, settings
from backend.app.core.database import Database, db
from backend.app.einrichtung import umzug, zustand
from backend.app.einrichtung.kopieren import kopieren
from backend.app.einrichtung.pruefung import pruefung
from backend.app.einrichtung.wiederherstellen import einspielen
from backend.app.services.storage import get_storage_path
from tests.api.conftest import buch_erstellen
from tests.api.einrichtung_hilfen import LEITSTELLE, als_verwaltung, laufend, orte  # noqa: F401 - Fixtures

pytestmark = pytest.mark.asyncio
ALT = "https://alt.probe.test"
LS_SCHLUESSEL = "ls_altes_geraet_schluessel_42"
ORIGINALE = {"eins.pdf": b"%PDF eins " * 50, "zwei.epub": b"PK zwei " * 4000}


@dataclass
class Mitschnitt:
    paket: dict
    sicherung: bytes
    liste: list
    dateien: dict[str, bytes]


@pytest.fixture
def altes_geraet(laufend, test_db, monkeypatch):
    """Die laufende Installation dieses Tests ist das alte Gerät: Bestand, Sicherungen und Schlüssel in tmp_path."""
    monkeypatch.setattr(Settings, "database_path", property(lambda _s: db.db_path))
    monkeypatch.setattr(settings, "leitstelle_adresse", LEITSTELLE)
    schluessel.eintragen(schluessel.Art.LEITSTELLE, LS_SCHLUESSEL)
    return laufend


async def _bestand(test_db) -> dict[str, str]:
    hashes = {}
    for nr, (name, inhalt) in enumerate(ORIGINALE.items(), start=1):
        h = hashlib.sha256(inhalt).hexdigest()
        ordner = get_storage_path(h)
        ordner.mkdir(parents=True)
        (ordner / name).write_bytes(inhalt)
        await buch_erstellen(test_db, title=f"Umzugsband {nr}", hash=h, file_name=name, file_size=len(inhalt))
        hashes[name] = h
    return hashes


async def test_code_gilt_einmal_kurz_und_mit_wenigen_versuchen(altes_geraet, client, client_ohne_auth, test_db):
    await _bestand(test_db)
    v = (await client.post("/api/umzug/vorbereiten")).json()
    assert len(v["code"]) == 9 and v["code"][4] == "-" and v["sicherung"].startswith("buecherfreunde_backup_")
    assert v["code"] not in (await client.get("/api/umzug")).text, "der Code steht nur in der Antwort auf Vorbereiten"
    assert (await client_ohne_auth.post("/api/umzug/vorbereiten")).status_code == 401

    r = await client_ohne_auth.post("/api/umzug/einloesen", json={"code": "ZZZZ-ZZZZ"})
    assert r.status_code == 403 and r.json()["detail"] == "Der Code stimmt nicht"
    assert (await client.get("/api/umzug")).json()["versuche_frei"] == settings.umzug_versuche - 1, "der Fehlversuch zählt trotz 403"
    assert (await client_ohne_auth.get("/api/umzug/sicherung")).status_code == 403

    r = await client_ohne_auth.post("/api/umzug/einloesen", json={"code": v["code"].lower().replace("-", " ")})
    assert r.status_code == 200, r.text
    paket = r.json()
    assert paket["schluessel"] == {"leitstelle": LS_SCHLUESSEL} and paket["anschluesse"] == {"leitstelle": LEITSTELLE}
    assert paket["originale"] == {"ort": "geraet", "anzahl": 2, "groesse": sum(len(b) for b in ORIGINALE.values())}
    s = await client_ohne_auth.get("/api/umzug/sicherung", headers={umzug.KOPF: paket["sitzung"]})
    assert s.status_code == 200 and hashlib.sha256(s.content).hexdigest() == paket["sha256"]
    assert (await client_ohne_auth.get("/api/umzug/sicherung", headers={umzug.KOPF: "falsche-sitzung"})).status_code == 403

    r = await client_ohne_auth.post("/api/umzug/einloesen", json={"code": v["code"]})
    assert r.status_code == 403 and r.json()["detail"] == "Dieser Code ist schon eingelöst"

    v = (await client.post("/api/umzug/vorbereiten")).json()            # neu vorbereitet: der alte Code gilt nicht mehr
    await db.execute("UPDATE umzug SET gilt_bis = '2000-01-01T00:00:00Z'")
    await db.commit()
    r = await client_ohne_auth.post("/api/umzug/einloesen", json={"code": v["code"]})
    assert r.status_code == 403 and "abgelaufen" in r.json()["detail"]

    v = (await client.post("/api/umzug/vorbereiten")).json()
    for _ in range(settings.umzug_versuche):
        await client_ohne_auth.post("/api/umzug/einloesen", json={"code": "ZZZZ-ZZZZ"})
    r = await client_ohne_auth.post("/api/umzug/einloesen", json={"code": v["code"]})
    assert r.status_code == 403 and "Zu viele" in r.json()["detail"] and (await client.get("/api/umzug")).json()["gesperrt"]

    assert (await db.fetch_one("SELECT COUNT(*) AS n FROM books"))["n"] == 2, "das alte Gerät bleibt unverändert"
    assert (await client.delete("/api/umzug")).json()["vorbereitet"] is False


async def _mitschneiden(client, client_ohne_auth, test_db) -> Mitschnitt:
    hashes = await _bestand(test_db)
    v = (await client.post("/api/umzug/vorbereiten")).json()
    paket = (await client_ohne_auth.post("/api/umzug/einloesen", json={"code": v["code"]})).json()
    kopf = {umzug.KOPF: paket["sitzung"]}
    sicherung = (await client_ohne_auth.get("/api/umzug/sicherung", headers=kopf)).content
    liste = (await client_ohne_auth.get("/api/umzug/originale", headers=kopf)).json()
    dateien = {h: (await client_ohne_auth.get(f"/api/umzug/originale/{h}", headers=kopf)).content for h in hashes.values()}
    assert {e["hash"] for e in liste} == set(dateien) and all(len(b) for b in dateien.values())
    return Mitschnitt(paket, sicherung, liste, dateien)


class _Abbruch(httpx.AsyncByteStream):
    """Liefert den Anfang und bricht dann ab, wie eine Verbindung, die mitten im Kopieren wegfällt."""

    def __init__(self, daten: bytes) -> None:
        self.daten = daten

    async def __aiter__(self):
        yield self.daten
        raise httpx.ReadError("Verbindung weg")


def _altes_geraet_im_netz(m: Mitschnitt, *, abbrechen: set[str]) -> dict:
    gesehen = {"bereiche": []}

    def antworten(a: httpx.Request) -> httpx.Response:
        weg, sitzung = a.url.path, a.headers.get(umzug.KOPF)
        if weg == "/api/umzug/einloesen":
            return httpx.Response(200, json=m.paket) if json.loads(a.content)["code"] == "ABCD-EFGH" else httpx.Response(403, json={"detail": "Der Code stimmt nicht"})
        if sitzung != m.paket["sitzung"]:
            return httpx.Response(403, json={"detail": "Keine gültige Sitzung für den Umzug"})
        if weg == "/api/umzug/sicherung":
            return httpx.Response(200, content=m.sicherung)
        if weg == "/api/umzug/originale":
            return httpx.Response(200, json=m.liste)
        h = weg.rsplit("/", 1)[-1]
        daten = m.dateien[h]
        if h in abbrechen:
            abbrechen.discard(h)
            return httpx.Response(200, stream=_Abbruch(daten[: len(daten) // 3]))
        if bereich := a.headers.get("range"):
            ab = int(bereich.removeprefix("bytes=").rstrip("-"))
            gesehen["bereiche"].append((h, ab))
            return httpx.Response(206, content=daten[ab:])
        return httpx.Response(200, content=daten)

    return gesehen | {"client": lambda adresse: httpx.AsyncClient(transport=httpx.MockTransport(antworten), base_url=adresse)}


async def _neues_geraet(tmp_path, monkeypatch) -> Database:
    """Ab hier ist der Test das neue Gerät: eigener Bestand, eigener Speicher, eigene Schlüsseldatei, neu installiert."""
    neu = Database(db_path=tmp_path / "neues_geraet" / "buecherfreunde.db")
    await neu.connect()
    await db.vorrat_leeren()
    db._connection, db.db_path, db.suche_dir = neu._connection, neu.db_path, neu.suche_dir
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "neues_geraet" / "texte")
    monkeypatch.setattr(settings, "schluessel_datei", tmp_path / "neues_geraet" / "schluessel.json")
    for feld in ("leitstelle_adresse", "kellerwolke_url"):
        monkeypatch.setattr(settings, feld, "")
    await zustand.erkennen(True)
    return neu


async def test_umzug_mit_originale_kopieren_fortsetzbar(altes_geraet, client, client_ohne_auth, test_db, tmp_path, monkeypatch):
    m = await _mitschneiden(client, client_ohne_auth, test_db)
    zwei = hashlib.sha256(ORIGINALE["zwei.epub"]).hexdigest()
    netz = _altes_geraet_im_netz(m, abbrechen={zwei})
    monkeypatch.setattr(umzug, "client", netz["client"])
    neu = await _neues_geraet(tmp_path, monkeypatch)
    try:
        await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "umzug"})
        r = await client_ohne_auth.post("/api/einrichtung/umzug/verbinden", json={"adresse": "http://alt.probe.test", "code": "ABCD-EFGH"})
        assert r.status_code == 422 and "https" in r.json()["detail"]
        r = await client_ohne_auth.post("/api/einrichtung/umzug/verbinden", json={"adresse": ALT, "code": "falsch-0000"})
        assert r.status_code == 403 and "Code" in r.json()["detail"]
        r = await client_ohne_auth.post("/api/einrichtung/umzug/verbinden", json={"adresse": ALT, "code": "ABCD-EFGH"})
        assert r.status_code == 200, r.text
        erg = r.json()
        assert (erg["originale"]["anzahl"], erg["schluessel"], erg["einstellungen"], erg["originale"]["ort"]) == (2, ["leitstelle"], ["leitstelle"], "geraet")
        assert erg["einspielen"]["art"] == "einspielen", "das Einspielen läuft als Auftrag, nicht in der Anfrage"
        assert LS_SCHLUESSEL not in r.text and m.paket["sitzung"] not in r.text
        await einspielen.warten()
        assert (await einspielen.stand()).stand == "fertig" and (await db.fetch_one("SELECT COUNT(*) AS n FROM books"))["n"] == 2
        assert (await pruefung.stand()).stand == "", "ohne Kellerwolke wählt man erst, wie die Originale kommen"
        datei = json.loads(settings.schluessel_pfad.read_text())
        assert datei["schluessel"] == {"leitstelle": LS_SCHLUESSEL, "umzug": m.paket["sitzung"]}
        assert stat.S_IMODE(settings.schluessel_pfad.stat().st_mode) == 0o600
        assert settings.leitstelle_adresse == LEITSTELLE, "die Adresse kam mit dem Umzug"
        e = (await client.get("/api/einrichtung", headers=await als_verwaltung(client))).json()
        assert {s["schluessel"]: s["stand"] for s in e["schritte"]} == {"verbinden": "erledigt", "orte": "offen", "originale": "offen",
                                                                            "pruefung": "offen", "abschluss": "offen"}

        s = (await client_ohne_auth.post("/api/einrichtung/originale", json={"weg": "kopieren"})).json()
        assert s["art"] == "kopieren"
        await kopieren.warten()
        s = (await client_ohne_auth.get("/api/einrichtung/auftraege")).json()
        k = next(a for a in s if a["art"] == "kopieren")
        assert k["stand"] == "pause" and "an derselben Stelle" in k["grund"], k
        teil = get_storage_path(zwei) / ".zwei.epub.teil"
        assert teil.exists() and 0 < teil.stat().st_size < len(ORIGINALE["zwei.epub"])

        await client_ohne_auth.post("/api/einrichtung/auftraege/kopieren/fortsetzen")
        await kopieren.warten()
        assert netz["bereiche"] == [(zwei, len(ORIGINALE["zwei.epub"]) // 3)], "fortgesetzt am Ende der angefangenen Datei"
        for name, inhalt in ORIGINALE.items():
            assert (get_storage_path(hashlib.sha256(inhalt).hexdigest()) / name).read_bytes() == inhalt
        assert not teil.exists()
        await pruefung.warten()
        b = (await client_ohne_auth.get("/api/einrichtung/pruefung/bericht")).json()
        assert (b["auftrag"]["stand"], b["erreichbar"], b["fehlt"]) == ("fertig", 2, 0)
    finally:
        await einspielen.stoppen()
        await kopieren.stoppen()
        await pruefung.stoppen()
        await db.vorrat_leeren()
        await neu.disconnect()


async def test_umzug_mit_ort_uebernehmen_prueft_nur(altes_geraet, client, client_ohne_auth, test_db, tmp_path, monkeypatch):
    m = await _mitschneiden(client, client_ohne_auth, test_db)
    monkeypatch.setattr(umzug, "client", _altes_geraet_im_netz(m, abbrechen=set())["client"])
    neu = await _neues_geraet(tmp_path, monkeypatch)
    try:
        await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "umzug"})
        assert (await client_ohne_auth.post("/api/einrichtung/originale", json={"weg": "ort"})).status_code == 409, "erst verbinden"
        assert (await client_ohne_auth.post("/api/einrichtung/umzug/verbinden", json={"adresse": ALT, "code": "ABCD-EFGH"})).status_code == 200
        await einspielen.warten()
        # die Platte des alten Geräts hängt jetzt am neuen: eins stimmt, zwei ist beschädigt
        for name, inhalt in (("eins.pdf", ORIGINALE["eins.pdf"]), ("zwei.epub", b"beschaedigt")):
            ordner = get_storage_path(hashlib.sha256(ORIGINALE[name]).hexdigest())
            ordner.mkdir(parents=True)
            (ordner / name).write_bytes(inhalt)
        s = (await client_ohne_auth.post("/api/einrichtung/originale", json={"weg": "ort"})).json()
        assert s["art"] == "pruefung"
        await pruefung.warten()
        b = (await client_ohne_auth.get("/api/einrichtung/pruefung/bericht")).json()
        assert (b["erreichbar"], b["fehlt"]) == (1, 1)
        assert b["eintraege"][0]["text"] == "Die Datei auf dem Gerät hat eine andere Prüfsumme"
        assert (get_storage_path(hashlib.sha256(ORIGINALE["zwei.epub"]).hexdigest()) / "zwei.epub").read_bytes() == b"beschaedigt", "nur geprüft"
    finally:
        await einspielen.stoppen()
        await pruefung.stoppen()
        await db.vorrat_leeren()
        await neu.disconnect()
