"""Nachbesserung erkannter Seiten (BF-118) ohne Netz: das Markdown einer Antwort, beide Fassungen einer Seite und die Wahl in der
Ablage, die Textschicht und die Bausteine einer nachgebesserten Seite. Alle Texte sind erfunden."""

from __future__ import annotations

import fitz
import pytest

from backend.app.services.textansicht import nachgebessert
from backend.app.texterkennung import ablage, markdown, nachbessern, textschicht
from backend.app.texterkennung.modelle import ErkannteZeile, Seitenerkennung, Wort

ANTWORT = """<|begin_of_box|>```markdown
# Der Hafen im Wandel

[Bild: 1 Der alte Kai am Morgen]

Früher legten hier täglich **Frachter** an. Heute liegen im Becken vor allem
Ausflugsboote, und die Speicher sind Wohnungen geworden.

- erster Punkt
- zweiter Punkt mit \\_Unterstrich\\_

| Jahr | Schiffe im Monat | Kai |
|---|---:|---|
| 1960 | 412 | Nord |
| 2020 | 36 | Süd |

```php
$tage = berechne($ausgabe, $rueckgabe);
echo "Tage: " . $tage;
```

1. Nenne zwei Gründe.
2. Überlege.
```<|end_of_box|>"""


def _klassisch(seite: int = 1, text: str = "Früher legten hier täglich Frachter an") -> Seitenerkennung:
    woerter = [Wort(text=w, lage=(72.0 + 40 * i, 100.0, 108.0 + 40 * i, 112.0), sicherheit=95) for i, w in enumerate(text.split())]
    return Seitenerkennung(seite=seite, werkzeug="tesseract", fassung="5", sprachen="deu", dpi=300, erkannt_am="2026-11-28T10:00:00Z",
                           dauer_s=1.0, zeilen=[ErkannteZeile(block=1, absatz=1, zeile=1, woerter=woerter)],
                           flaechen=[(72.0, 300.0, 400.0, 500.0), (72.0, 150.0, 400.0, 280.0)])


def _ki(seite: int = 1, md: str = ANTWORT) -> Seitenerkennung:
    return Seitenerkennung(seite=seite, herkunft="ki", werkzeug="Qwen3.8 27B", fassung="qwen/qwen3.8-27b", sprachen="", dpi=150,
                           erkannt_am="2026-11-28T11:00:00Z", dauer_s=60.0, markdown=markdown.bereinigt(md),
                           flaechen=_klassisch(seite).flaechen)


def test_markdown_wird_zu_bloecken_und_schlichtem_text():
    b = markdown.bloecke(ANTWORT)
    assert [x.art for x in b] == ["ueberschrift", "bild", "absatz", "absatz", "absatz", "tabelle", "code", "absatz", "absatz"]
    assert b[1].text == "1 Der alte Kai am Morgen"
    assert b[2].text == "Früher legten hier täglich Frachter an. Heute liegen im Becken vor allem Ausflugsboote, und die Speicher sind Wohnungen geworden."
    assert [b[3].text, b[4].text] == ["• erster Punkt", "• zweiter Punkt mit _Unterstrich_"]
    assert (b[5].kopf, b[5].reihen, b[5].zahlen) == (("Jahr", "Schiffe im Monat", "Kai"), (("1960", "412", "Nord"), ("2020", "36", "Süd")), (True, True, False))
    assert (b[6].sprache, b[6].zeilen) == ("php", ('$tage = berechne($ausgabe, $rueckgabe);', 'echo "Tage: " . $tage;'))
    assert [b[7].text, b[8].text] == ["1. Nenne zwei Gründe.", "2. Überlege."]
    text = markdown.schlichter_text(ANTWORT)
    assert "Jahr Schiffe im Monat Kai" in text and "**" not in text and "<|" not in text


def test_beide_fassungen_bleiben_die_wahl_entscheidet(tmp_path, monkeypatch):
    monkeypatch.setattr(ablage, "pfad", lambda _h: tmp_path / "erkennung.jsonl")
    ablage.anhaengen("buch", _klassisch(1))
    ablage.anhaengen("buch", _klassisch(2))
    ablage.anhaengen("buch", _ki(1))
    with (tmp_path / "erkennung.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"seite": 3, "abgebroch\n')                                # halb geschrieben: zählt nicht
    assert ablage.lesen("buch")[1].herkunft == "ki"                        # ohne Wahl gilt die jüngste
    assert {s: (f.klassisch, f.ki, f.gilt) for s, f in ablage.fassungen("buch").items()} == {1: (True, True, "ki"), 2: (True, False, "klassisch")}
    ablage.waehlen("buch", 1, "klassisch")
    assert ablage.lesen("buch")[1].herkunft == "klassisch" and ablage.fassungen("buch")[1].gilt == "klassisch"
    assert ablage.fassung("buch", 1, "ki").markdown                        # die andere bleibt
    ablage.waehlen("buch", 2, "ki")                                        # eine Fassung, die es nicht gibt: es bleibt die klassische
    assert ablage.lesen("buch")[2].herkunft == "klassisch"
    ablage.waehlen("buch", 1, "ki")
    assert ablage.lesen("buch")[1].herkunft == "ki"


def test_textschicht_liest_die_nachbesserung():
    s = textschicht.schicht_aus("", _ki())
    assert s.art == "erkannt" and s.text.startswith("Der Hafen im Wandel\n1 Der alte Kai am Morgen")


def test_bausteine_einer_nachgebesserten_seite():
    doc = fitz.open()
    seite = doc.new_page(width=480, height=640)
    seite.draw_rect(fitz.Rect(72, 150, 400, 280), color=(0, 0, 0), fill=(0.4, 0.4, 0.4))
    seite.draw_rect(fitz.Rect(72, 300, 400, 500), color=(0, 0, 0), fill=(0.6, 0.6, 0.6))
    b = nachgebessert.bausteine(seite, _ki(), zuschneiden=False)
    assert [x.art for x in b] == ["ueberschrift", "bild", "unterschrift", "absatz", "absatz", "absatz", "tabelle", "code", "absatz", "absatz", "bild"]
    bilder = [x for x in b if x.art == "bild"]
    assert [(x.bild, x.rechteck.y0) for x in bilder] == [(0, 150), (1, 300)]          # von oben nach unten, die übrige am Ende
    assert b[6].tabelle.kopf == ["Jahr", "Schiffe im Monat", "Kai"] and b[7].code.zeilen[0].startswith("$tage")
    assert [x.oben for x in b] == sorted(x.oben for x in b)


async def test_nachbessern_nimmt_die_flaechen_der_klassischen_und_prueft_die_antwort(tmp_path, monkeypatch):
    doc = fitz.open()
    doc.new_page(width=480, height=640).insert_text((72, 100), "Eine erfundene Seite")
    pfad = tmp_path / "buch.pdf"
    doc.save(pfad)
    gefragt: list[dict] = []

    async def antwort(anweisung, bild, **art):
        gefragt.append({"anweisung": anweisung, "groesse": len(bild), **art})
        return ANTWORT, "Qwen3.8 27B"

    monkeypatch.setattr(nachbessern.ki, "bildantwort", antwort)
    e = await nachbessern.seite_nachbessern(pfad, 1, _klassisch())
    assert (e.herkunft, e.werkzeug, e.flaechen, e.zeilen) == ("ki", "Qwen3.8 27B", _klassisch().flaechen, [])
    assert e.markdown.startswith("# Der Hafen im Wandel") and "Wort für Wort" in gefragt[0]["anweisung"] and gefragt[0]["temperature"] == 0

    async def leer(anweisung, bild, **art):
        return "```\n```", "Qwen3.8 27B"

    monkeypatch.setattr(nachbessern.ki, "bildantwort", leer)
    with pytest.raises(nachbessern.Nachbesserungsfehler, match="keinen lesbaren Text"):
        await nachbessern.seite_nachbessern(pfad, 1, _klassisch())
    with pytest.raises(IndexError):
        await nachbessern.seite_nachbessern(pfad, 7, None)
