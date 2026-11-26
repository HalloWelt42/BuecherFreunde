"""Regeln ohne Datenbank für Hochladen mit Vorschau (BF-80) und Begleitmaterial (BF-81): Pfade aus der ZIP, Einteilen nach dem
Namen, Namen und Rollen in der Kellerwolke, Sprache gegen die Lücke. Alles erfunden."""

from __future__ import annotations

import io
import zipfile

import pytest

from backend.app.annahme import entpacken
from backend.app.annahme.einstellungen import Zipgrenzen
from backend.app.annahme.modelle import Gelesen, Vorgabe
from backend.app.annahme.zuordnen import _sprache
from backend.app.material import zugehoerig
from backend.app.material.ablage import ZUSATZ_HOECHSTENS, rolle, zusatz
from backend.app.material.erkennen import bestes_buch

GRENZEN = Zipgrenzen(dateien=100, datei_mb=10, gesamt_mb=100, tiefe=4, verhaeltnis=100)


@pytest.mark.parametrize(("name", "erwartet"), [
    ("Romane/Kaltwasser/Band 4.epub", (["Romane", "Kaltwasser"], "Band 4.epub")),
    ("a\\b\\c.pdf", (["a", "b"], "c.pdf")),
    ("./a//b.pdf", (["a"], "b.pdf")),
    ("../boese.pdf", None),
    ("a/../../boese.pdf", None),
    ("/etc/passwd", None),
    ("C:\\Windows\\x.pdf", None),
])
def test_pfade_aus_der_zip_sind_nur_hinweise(name, erwartet):
    assert entpacken.hinweis(name) == erwartet


def test_einteilen_nach_dem_namen(tmp_path):
    datei = tmp_path / "probe.zip"
    with zipfile.ZipFile(datei, "w") as z:
        for name in ("X/Moorbuch.pdf", "X/Moorbuch - Beispielcode.zip", "X/Moorbuch - Schaltpläne.pdf", "X/Moorbuch - Band 2.pdf",
                     "Y/Moorbuch - Karte.png", "X/Notiz.txt.png", "X/Krieg.pdf", "X/Kriegsbericht.png"):
            z.writestr(name, b"x")
    e = {x.pfad: x for x in entpacken.verzeichnis(datei, GRENZEN)}
    buch = e["X/Moorbuch.pdf"].nr
    assert e["X/Moorbuch.pdf"].einteilung == "buch"
    assert (e["X/Moorbuch - Beispielcode.zip"].einteilung, e["X/Moorbuch - Beispielcode.zip"].zu) == ("material", buch)
    assert (e["X/Moorbuch - Schaltpläne.pdf"].einteilung, e["X/Moorbuch - Schaltpläne.pdf"].zu) == ("material", buch)   # ein PDF als Beilage
    assert e["X/Moorbuch - Band 2.pdf"].einteilung == "buch"                                                          # nennt einen Band
    assert e["Y/Moorbuch - Karte.png"].einteilung == "rest"                                                           # anderer Ordner
    assert e["X/Kriegsbericht.png"].einteilung == "rest" and e["X/Kriegsbericht.png"].grund == "Bild ohne Buch gleichen Namens"


def test_grenzen_fuer_die_ganze_zip(tmp_path):
    datei = tmp_path / "gross.zip"
    with zipfile.ZipFile(datei, "w") as z:
        z.writestr("a.txt", b"a" * 10)
    with pytest.raises(entpacken.ZipFehler, match="erlaubt sind 0"):
        entpacken.verzeichnis(datei, GRENZEN.model_copy(update={"dateien": 0}))
    (tmp_path / "kaputt.zip").write_bytes(b"PK kein zip")
    with pytest.raises(entpacken.ZipFehler, match="lässt sich nicht lesen"):
        entpacken.verzeichnis(tmp_path / "kaputt.zip", GRENZEN)


def test_auspacken_bricht_ab_wenn_es_mehr_wird_als_erlaubt(tmp_path):
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("viel.txt", b"\x00" * 5000)
    (tmp_path / "z.zip").write_bytes(puffer.getvalue())
    [e] = entpacken.verzeichnis(tmp_path / "z.zip", GRENZEN)
    with pytest.raises(entpacken.ZuGross):
        entpacken.auspacken(tmp_path / "z.zip", e, tmp_path / "aus" / "viel.txt", 1000)
    assert not (tmp_path / "aus" / "viel.txt").exists()
    groesse, summe = entpacken.auspacken(tmp_path / "z.zip", e, tmp_path / "aus" / "viel.txt", 10_000)
    assert groesse == 5000 and len(summe) == 64


@pytest.mark.parametrize(("name", "erwartet"), [
    ("Lösungen.pdf", ".material.loesungen.pdf"),
    ("Schaltpläne für Anfänger und Fortgeschrittene.pdf", ".material.schaltplaene-fuer-an.pdf"),
    ("Messwerte.CSV", ".material.messwerte.csv"),
    ("ohne Endung", ".material.ohne-endung"),
    ("###.zip", ".material.datei.zip"),
])
def test_zusatz_nach_den_regeln_der_kellerwolke(name, erwartet):
    z = zusatz(name)
    assert z == erwartet and len(z) <= ZUSATZ_HOECHSTENS
    assert "-2" in zusatz(name, 2) and len(zusatz(name, 2)) <= ZUSATZ_HOECHSTENS        # ist der Name neben dem Original vergeben


def test_rolle_nur_aus_buchstaben():
    r = rolle("0f3a9c21-77b2-4e1d-9a00-123456789abc")
    assert r.startswith("material_") and r.removeprefix("material_").isalpha() and r == rolle("0f3a9c21-77b2-4e1d-9a00-123456789abc")
    assert r != rolle("1f3a9c21-77b2-4e1d-9a00-123456789abc")


def test_zugehoerig_und_kurzname():
    assert zugehoerig.gehoert_zu("Moorbuch - Lösungen.pdf", "Moorbuch")
    assert zugehoerig.gehoert_zu("Moorbuch (Karte).png", "Moorbuch")
    assert not zugehoerig.gehoert_zu("Moorbuchhandlung.pdf", "Moorbuch")
    assert not zugehoerig.gehoert_zu("Moorbuch.epub", "Moorbuch")                    # derselbe Name ist ein anderes Format
    assert zugehoerig.als_material("Titel - Probe [12] - Lösungen.pdf", "Titel - Probe [12].pdf") == "Lösungen.pdf"
    assert zugehoerig.als_material("Titel - Probe - Lösungen.pdf", "Titel - Probe [12].pdf") == "Lösungen.pdf"
    buecher = [{"id": 1, "name": "Titel [1].pdf"}, {"id": 12, "name": "Titel [12].pdf"}]
    assert bestes_buch("Titel [12] - Karte.png", buecher)["id"] == 12                # der längste passende Name gewinnt


def test_sprache_der_datei_gegen_die_luecke():
    wert, hinweise = _sprache(Gelesen(sprache="English"), Vorgabe(sprache="de"))
    assert (wert.wert, wert.herkunft, hinweise) == ("en", "datei", ["Die Datei ist englisch, die Lücke deutsch"])
    wert, hinweise = _sprache(Gelesen(), Vorgabe(sprache="de"))
    assert (wert.wert, wert.herkunft, hinweise) == ("de", "luecke", [])
