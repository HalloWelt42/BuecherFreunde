"""Textansicht: eine PDF-Seite wird zu Bausteinen (Absätze, Überschriften, Kästen, Abbildungen)."""

import fitz

from backend.app.services.textansicht import abbildung_png, lesbar, seitenaufbau, seiten_lesen, verbinde

ABSATZ = ("Am Morgen ging die Sonne über dem kleinen Dorf auf, und die Bauern zogen mit ihren Wagen hinaus auf "
          "die Felder, die noch nass vom Tau der Nacht waren. Niemand ahnte, was an diesem Tag geschehen würde.")
KASTEN = ("Kein Mensch und keine Institution besitzt die wissenschaftliche Wahrheit. Ihre Autorität ruht nicht auf "
          "Personen, sondern auf einem Verfahren: veröffentlichen, prüfen, wiederholen.")


def probeseite() -> fitz.Document:
    doc = fitz.open()
    seite = doc.new_page(width=595, height=842)
    seite.insert_text((74, 45), "1 Kapitel über das Dorf", fontsize=9)                       # Kopfzeile
    seite.insert_text((74, 110), "1.1 Der Morgen", fontsize=16)                               # Überschrift
    seite.insert_textbox(fitz.Rect(74, 125, 521, 200), ABSATZ, fontsize=10)                  # Absatz
    seite.draw_rect(fitz.Rect(200, 220, 400, 320), color=(0, 0, 1), fill=(0.9, 0.9, 1))       # Zeichnung
    seite.insert_text((410, 270), "Beschriftung", fontsize=9)                                 # daneben
    seite.insert_textbox(fitz.Rect(74, 335, 521, 360), "Abbildung 1.1: Das Dorf im Morgenlicht.", fontsize=9)
    seite.draw_rect(fitz.Rect(80, 400, 515, 480), color=(0, 0.5, 0), fill=(0.9, 1, 0.9))      # Kasten
    seite.insert_text((90, 396), "Merke", fontsize=10)                                        # Titel auf dem Rahmen
    seite.insert_textbox(fitz.Rect(90, 410, 505, 475), KASTEN, fontsize=10)
    seite.insert_text((290, 820), "7", fontsize=9)                                            # Fußzeile
    return doc


def test_seitenaufbau_in_lesereihenfolge():
    bausteine = seitenaufbau(probeseite()[0])
    assert [b.art for b in bausteine] == ["ueberschrift", "absatz", "bild", "unterschrift", "kasten"]
    assert bausteine[0].text == "1.1 Der Morgen"
    assert bausteine[1].text == ABSATZ
    assert bausteine[3].text.startswith("Abbildung 1.1")
    kasten = bausteine[4]
    assert kasten.titel == "Merke"
    assert [t.text for t in kasten.inhalt] == [KASTEN]


def test_abbildung_umfasst_beschriftung():
    bild = next(b for b in seitenaufbau(probeseite()[0]) if b.art == "bild")
    assert bild.bild == 0
    assert bild.rechteck.x1 > 400          # die Beschriftung rechts neben der Zeichnung gehört dazu


def test_abbildung_als_png(tmp_path):
    pfad = tmp_path / "probe.pdf"
    probeseite().save(pfad)
    png = abbildung_png(pfad, 1, 0)
    assert png and png.startswith(b"\x89PNG")
    assert abbildung_png(pfad, 1, 5) is None
    assert abbildung_png(pfad, 9, 0) is None


def test_seiten_lesen_zaehlt_dateiseiten(tmp_path):
    pfad = tmp_path / "probe.pdf"
    doc = probeseite()
    doc.new_page()
    doc.save(pfad)
    gesamt, seiten = seiten_lesen(pfad, 2, 5)
    assert gesamt == 2
    assert [(nr, b) for nr, b in seiten] == [(2, [])]


def test_trennstrich_wird_verbunden():
    assert verbinde(["Das Wort wird getrennt wer-", "den, weil die Zeile endet."]) == \
        "Das Wort wird getrennt werden, weil die Zeile endet."


def test_bindestrich_vor_grossbuchstabe_bleibt():
    assert verbinde(["Ein Satz über Nord-", "Süd-Verbindungen."]) == "Ein Satz über Nord-Süd-Verbindungen."


def test_steuerzeichen_fallen_weg():
    assert verbinde(["Ein ganz normaler" + chr(0x02) + " Satz."]) == "Ein ganz normaler Satz."


def test_zeichensalat_ist_nicht_lesbar():
    salat = "".join(chr(c) for c in (0x19, 0x12, 0x13, 0x10, 0x06, 0x01, 0x14, 0x16, 0x0E, 0x10, 0x05, 0x2020))
    assert not lesbar(salat)
    assert lesbar(ABSATZ)
