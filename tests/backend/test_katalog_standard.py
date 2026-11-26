"""Der Standard-Katalog (BF-69, backend/app/katalog/standard.json): für jede Bibliothek, Schlüssel eindeutig, jedes Zeichen
in Font Awesome Free (solid), Farben gültig und dunkel genug für ein weißes Zeichen, jede Kategorie mit Beschreibung für die
KI und Regeln, Arten nur die bekannten."""

import json
import re
from pathlib import Path

import pytest

from backend.app.katalog.datei import STANDARD, standard
from backend.app.katalog.modelle import REGELARTEN, Katalog
from backend.app.models.book import TYPEN

SOLID = Path(__file__).resolve().parents[2] / "frontend/node_modules/@fortawesome/fontawesome-free/svgs/solid"
KONTRAST_AB = 4.5


def leuchtdichte(farbe: str) -> float:
    """Relative Leuchtdichte nach WCAG 2.1."""
    def kanal(wert: int) -> float:
        c = wert / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(farbe[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * kanal(r) + 0.7152 * kanal(g) + 0.0722 * kanal(b)


def kontrast_zu_weiss(farbe: str) -> float:
    return 1.05 / (leuchtdichte(farbe) + 0.05)


def alle_kategorien(k: Katalog):
    for _, kat in k.kategorien():
        yield kat
        yield from kat.teile


def test_die_datei_ist_ein_gueltiger_katalog():
    roh = json.loads(STANDARD.read_text(encoding="utf-8"))
    k = Katalog.model_validate(roh)                       # prüft Form, Schlüssel und Namen
    assert k.fassung == 1
    assert len(k.bereiche) == 10
    assert 50 <= sum(1 for _ in k.kategorien()) <= 75
    assert [b.name for b in k.bereiche] == ["Romane", "Kinder und Jugend", "Wissen", "Technik", "Wirtschaft und Recht",
                                            "Kunst und Kultur", "Leben", "Lernen", "Comics", "Besonderes"]


def test_schluessel_eindeutig_und_unter_ihrem_bereich():
    k = standard()
    schluessel = list(k.schluessel())
    assert len(schluessel) == len(set(schluessel))
    for b in k.bereiche:
        for kat in b.kategorien:
            assert kat.schluessel.startswith(f"{b.schluessel}/")
            assert all(t.schluessel.startswith(f"{b.schluessel}/") for t in kat.teile)


def test_zeichen_gibt_es_in_font_awesome():
    k = standard()
    zeichen = {b.zeichen for b in k.bereiche} | {kat.zeichen for kat in alle_kategorien(k)}
    assert "" not in zeichen and all(re.fullmatch(r"[a-z0-9-]+", z) for z in zeichen)
    if not SOLID.is_dir():
        pytest.skip("Font Awesome ist nicht eingerichtet (frontend/node_modules)")
    assert sorted(z for z in zeichen if not (SOLID / f"{z}.svg").is_file()) == []


def test_farben_gueltig_verschieden_und_dunkel_genug():
    k = standard()
    farben = [b.farbe for b in k.bereiche]
    assert all(re.fullmatch(r"#[0-9a-f]{6}", f) for f in farben)
    assert len(set(farben)) == len(farben)
    zu_hell = {b.name: round(kontrast_zu_weiss(b.farbe), 2) for b in k.bereiche if kontrast_zu_weiss(b.farbe) < KONTRAST_AB}
    assert zu_hell == {}
    assert all(kat.farbe == "" for kat in alle_kategorien(k) if hasattr(kat, "farbe"))     # Kategorien erben


def test_jede_kategorie_mit_beschreibung_und_regeln():
    for kat in alle_kategorien(standard()):
        assert len(kat.ki_beschreibung) >= 20, kat.schluessel
        assert not kat.regeln.leer, kat.schluessel
        assert kat.regeln.schlagworte, kat.schluessel
        assert kat.regeln.titelwoerter, kat.schluessel


def test_regeln_auf_deutsch_und_englisch():
    """Stichprobe: die Schlagworte großer Kategorien tragen beide Sprachen."""
    regeln = {kat.schluessel: kat.regeln for kat in alle_kategorien(standard())}
    for schluessel, deutsch, englisch in (("technik/informatik", "Informatik", "Computer science"), ("romane/krimi", "Kriminalroman", "Crime fiction"),
                                          ("leben/kochen", "Kochen", "Cooking"), ("besonderes/gebrauchsanleitungen", "Bedienungsanleitung", "User manual")):
        assert {deutsch, englisch} <= set(regeln[schluessel].schlagworte)


def test_sachgruppen_nach_dezimalklassifikation_und_buchstaben():
    regeln = {kat.schluessel: kat.regeln for kat in alle_kategorien(standard())}
    assert regeln["romane/roman"].sachgruppen == ["B"]
    assert "K" in regeln["kinder/kinderbuch"].sachgruppen
    assert "004" in regeln["technik/informatik"].sachgruppen
    for kat in alle_kategorien(standard()):
        assert all(re.fullmatch(r"[0-9]{1,3}(\.[0-9]+)?|[A-Z]", s) for s in kat.regeln.sachgruppen), kat.schluessel


def test_grosse_kategorien_haben_teile():
    teile = {kat.schluessel: [t.schluessel for t in kat.teile] for _, kat in standard().kategorien() if kat.teile}
    assert "technik/programmierung" in teile["technik/informatik"]
    assert set(teile) >= {"technik/informatik", "wissen/naturwissenschaften", "wissen/geschichte", "romane/krimi"}


def test_arten_der_bereiche():
    arten = {b.schluessel: b.arten for b in standard().bereiche}
    assert arten.pop("besonderes") == ["dokument", "heft", "katalog", "broschuere"]
    assert set(map(tuple, arten.values())) == {("",)}
    bekannt = {"", *(t["id"] for t in TYPEN)}
    assert all(set(a) <= bekannt for a in arten.values())


def test_besonderes_nach_art_des_schriftstuecks():
    besonderes = next(b for b in standard().bereiche if b.schluessel == "besonderes")
    assert besonderes.name == "Besonderes" and besonderes.beschreibung == "Alles, was kein Buch ist"
    namen = {k.name for k in besonderes.kategorien}
    assert {"Gebrauchsanleitungen", "Datenblätter", "Handbücher und Referenzen", "Belege und Rechnungen", "Verträge",
            "Zeugnisse und Urkunden", "Formulare", "Kataloge und Prospekte", "Folien und Vorträge", "Skripte und Abschlussarbeiten",
            "Projektdokumentationen", "Zeitschriften und Hefte"} <= namen
    assert all(k.ki_beschreibung.startswith("Die Art des Dokuments") for k in besonderes.kategorien)
    assert all(set(k.regeln.model_dump()) == set(REGELARTEN) for k in besonderes.kategorien)       # keine neue Art von Regel
