"""Textansicht: eine PDF-Seite wird zu Bausteinen (Absätze, Überschriften, Kästen, Abbildungen)."""

import fitz

from backend.app.services.textansicht import (Baustein, abbildung_png, lesbar, seitenaufbau, seiten_lesen, ueber_seitenwechsel,
                                             verbinde)

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
    assert [(s.nr, s.bausteine, s.schicht) for s in seiten] == [(2, [], "ohne")]


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


# -- BF-103: Absätze, Trennung, Seitenwechsel, Code, Abbildungen -------------------------------------------------------------
# Alle PDF entstehen hier, mit erfundenem Text. Wie in aus E-Books gedruckten PDF steht jede Zeile für sich (eigener Block).

LINKS_X, RECHTS_X, GROESSE_15, SCHRITT = 77.0, 520.0, 15.0, 26.3


def umbrechen(text: str, breite: float = RECHTS_X - LINKS_X, groesse: float = GROESSE_15, schrift: str = "helv") -> list[str]:
    """Wörter auf Zeilen verteilen, so breit wie die Spalte: jede Zeile ist voll, das nächste Wort passte nicht mehr."""
    zeilen, laufend = [], ""
    for wort in text.split():
        probe = f"{laufend} {wort}".strip()
        if laufend and fitz.get_text_length(probe, fontname=schrift, fontsize=groesse) > breite:
            zeilen.append(laufend)
            laufend = wort
        else:
            laufend = probe
    return zeilen + [laufend]


def zeilenweise(seite: fitz.Page, y: float, zeilen: list[str], schritt: float = SCHRITT, schrift: str = "helv",
                x: float = LINKS_X, groesse: float = GROESSE_15) -> float:
    """Jede Zeile als eigenes Textstück; gibt die Grundlinie der letzten zurück."""
    for i, z in enumerate(zeilen):
        seite.insert_text((x, y + i * schritt), z, fontname=schrift, fontsize=groesse)
    return y + (len(zeilen) - 1) * schritt


ERSTER = ("Ein Leuchtturm steht am Rand der kleinen Insel und zeigt den Schiffen in jeder Nacht den Weg zum Hafen, auch wenn "
          "der Nebel so dicht ist, dass man die eigene Hand kaum sieht.")
ZWEITER = ("Die Wärterin steigt jeden Abend die hundert Stufen hinauf, putzt das Glas der großen Lampe und schreibt in ihr "
           "Buch, wie das Wetter war und welche Schiffe vorbeigefahren sind.")


def seite_mit(*absaetze: str, abstand: float = 44.0) -> fitz.Document:
    doc = fitz.open()
    seite = doc.new_page(width=612, height=792)
    y = 100.0
    for absatz in absaetze:
        y = zeilenweise(seite, y, umbrechen(absatz)) + abstand
    return doc


def test_zeilen_als_eigene_bloecke_werden_ein_absatz():
    doc = seite_mit(ERSTER, ZWEITER)
    assert len([b for b in doc[0].get_text("dict")["blocks"] if b["type"] == 0]) > 2      # wirklich Zeile für Zeile
    bausteine = seitenaufbau(doc[0])
    assert [(b.art, b.text) for b in bausteine] == [("absatz", ERSTER), ("absatz", ZWEITER)]


def test_neuer_absatz_bei_einzug_ohne_abstand():
    doc = fitz.open()
    seite = doc.new_page(width=612, height=792)
    erste = umbrechen(ERSTER)
    letzte = zeilenweise(seite, 100, erste)
    zweite = umbrechen(ZWEITER, breite=RECHTS_X - LINKS_X - 20)
    seite.insert_text((LINKS_X + 20, letzte + SCHRITT), zweite[0], fontname="helv", fontsize=GROESSE_15)   # eingerückt
    zeilenweise(seite, letzte + 2 * SCHRITT, umbrechen(" ".join(zweite[1:])))
    assert [b.text for b in seitenaufbau(seite)] == [ERSTER, ZWEITER]


def test_trennung_am_zeilenende_beide_faelle():
    doc = fitz.open()
    seite = doc.new_page(width=612, height=792)
    zeilenweise(seite, 100, ["Der Wind war kalt, und die Fischer hielten sich dage-",
                             "gen mit heißem Tee und einem langen Schal warm, und",
                             "manche zählten in ihren Büchern jedes einzelne Caret-", "Zeichen nach."])
    (absatz,) = seitenaufbau(seite)
    assert absatz.text == ("Der Wind war kalt, und die Fischer hielten sich dagegen mit heißem Tee und einem langen Schal warm, "
                           "und manche zählten in ihren Büchern jedes einzelne Caret-Zeichen nach.")


def test_verbinde_trennung_nur_wo_eindeutig():
    from collections import Counter
    assert verbinde(["Ein Zahlenwert wird 3-", "fach geprüft."]) == "Ein Zahlenwert wird 3-fach geprüft."
    assert verbinde(["Die Seite ist HTML-", "basiert."]) == "Die Seite ist HTML-basiert."
    assert verbinde(["Das ist ein Rand -", "und noch einer."]) == "Das ist ein Rand - und noch einer."
    so_geschrieben = Counter({"wie-derum": 2})                                              # so schreibt es die Seite
    assert verbinde(["Das Wort wie-", "derum."], so_geschrieben) == "Das Wort wie-derum."
    assert verbinde(["Ein wei" + chr(0xAD), "ches Trennzeichen."]) == "Ein weiches Trennzeichen."


def test_code_im_text_umbrochen_bleibt_im_absatz():
    doc = fitz.open()
    seite = doc.new_page(width=612, height=792)
    y = zeilenweise(seite, 100, umbrechen(ERSTER)) + 44
    letzte = zeilenweise(seite, y, ["Gegeben seien die beiden Variablen von oben, also vorname und"])
    seite.insert_text((LINKS_X, letzte + SCHRITT), "nachname", fontname="cour", fontsize=GROESSE_15)
    seite.insert_text((LINKS_X + fitz.get_text_length("nachname", "cour", GROESSE_15), letzte + SCHRITT), ":", fontname="helv",
                      fontsize=GROESSE_15)
    assert [(b.art, b.text) for b in seitenaufbau(seite)] == [
        ("absatz", ERSTER), ("absatz", "Gegeben seien die beiden Variablen von oben, also vorname und nachname:")]


def buch_mit_seitenwechsel(pfad, mitten: str = "und am Ende der Seite") -> None:
    doc = fitz.open()
    eins = doc.new_page(width=612, height=792)
    y = zeilenweise(eins, 100, umbrechen(ERSTER)) + 44
    zeilenweise(eins, y, umbrechen("Wenn die Sonne aufgeht, löscht sie das Licht, legt sich schlafen " + mitten))
    zwei = doc.new_page(width=612, height=792)
    y = zeilenweise(zwei, 100, umbrechen("geht der Satz auf der nächsten Seite weiter und endet erst hier.")) + 44
    zeilenweise(zwei, y, umbrechen(ZWEITER))
    doc.save(pfad)


def test_satz_ueber_den_seitenwechsel_steht_ganz_auf_der_naechsten_seite(tmp_path):
    pfad = tmp_path / "wechsel.pdf"
    buch_mit_seitenwechsel(pfad)
    _, seiten = seiten_lesen(pfad, 1, 2)
    erste, zweite = (s.bausteine for s in seiten)
    assert [b.text for b in erste] == [ERSTER]
    assert zweite[0].text == ("Wenn die Sonne aufgeht, löscht sie das Licht, legt sich schlafen und am Ende der Seite geht der "
                              "Satz auf der nächsten Seite weiter und endet erst hier.")
    assert [b.text for b in seiten_lesen(pfad, 2, 1)[1][0].bausteine] == [b.text for b in zweite]   # einzeln geladen: gleich
    assert [b.text for b in seiten_lesen(pfad, 1, 1)[1][0].bausteine] == [ERSTER]


def test_mit_satzende_bleibt_der_absatz_auf_seiner_seite(tmp_path):
    pfad = tmp_path / "wechsel.pdf"
    buch_mit_seitenwechsel(pfad, mitten="und ruht.")
    erste, zweite = (s.bausteine for s in seiten_lesen(pfad, 1, 2)[1])
    assert len(erste) == 2 and erste[1].text.endswith("und ruht.") and zweite[0].text.startswith("geht der Satz")


def test_ueber_seitenwechsel_gibt_einen_einzigen_absatz_nicht_weiter():
    def absatz(text):
        return Baustein("absatz", 0, 0, text=text)
    seiten = {1: [absatz("Ganz allein auf der Seite und ohne Ende")], 2: [absatz("geht es weiter."), absatz("Neu und")],
              3: [absatz("fertig.")]}
    ueber_seitenwechsel(seiten)
    assert [[b.text for b in s] for s in seiten.values()] == [["Ganz allein auf der Seite und ohne Ende"],
                                                              ["geht es weiter."], ["Neu und fertig."]]


def test_festbreite_bleibt_code_mit_einrueckung():
    doc = fitz.open()
    seite = doc.new_page(width=612, height=792)
    seite.insert_textbox(fitz.Rect(LINKS_X, 80, RECHTS_X, 140), ERSTER, fontname="helv", fontsize=11)
    breite = fitz.get_text_length("x", "cour", 11)
    for i, zeile in enumerate(["def flaeche(breite, hoehe):", "    produkt = breite * hoehe", "    return produkt"]):
        tief = len(zeile) - len(zeile.lstrip())
        seite.insert_text((90 + tief * breite, 180 + i * 14), zeile.strip(), fontname="cour", fontsize=11)
    code = [b for b in seitenaufbau(seite) if b.art == "code"]
    assert len(code) == 1 and code[0].code.kennung == ""
    assert code[0].code.zeilen == ["def flaeche(breite, hoehe):", "    produkt = breite * hoehe", "    return produkt"]


def test_tafel_mit_code_in_textschrift_wird_code_ohne_bild():
    doc = fitz.open()
    seite = doc.new_page(width=612, height=792)
    zeilenweise(seite, 100, umbrechen("Zwei Sterne rechnen hoch, so sieht das aus:"))
    seite.draw_rect(fitz.Rect(LINKS_X, 140, 535, 320), color=None, fill=(0.93, 0.95, 0.96))
    seite.draw_rect(fitz.Rect(99, 174, 512, 200), color=None, fill=(0.86, 0.87, 0.87))
    zeilenweise(seite, 192, ["7 ** 2", "49"], schritt=67, x=99)
    zeilenweise(seite, 360, umbrechen(ZWEITER))
    arten = [(b.art, b.code.zeilen if b.code else b.text[:12]) for b in seitenaufbau(seite)]
    assert arten == [("absatz", "Zwei Sterne "), ("code", ["7 ** 2", "49"]), ("absatz", ZWEITER[:12])]


def test_kastenrest_ueber_den_seitenrand_ist_keine_abbildung():
    doc = fitz.open()
    seite = doc.new_page(width=612, height=792)
    seite.draw_rect(fitz.Rect(LINKS_X, -300, 535, 90), color=None, fill=(0.93, 0.95, 0.96))     # Ende von der Seite davor
    zeilenweise(seite, 130, umbrechen(ERSTER))
    assert [b.art for b in seitenaufbau(seite)] == ["absatz"]


def test_lose_codezeilen_werden_ein_codebaustein():
    doc = fitz.open()
    seite = doc.new_page(width=612, height=792)
    y = zeilenweise(seite, 100, umbrechen("Die Funktion bekommt zwei Werte und gibt ihre Summe zurück:")) + 67
    y = zeilenweise(seite, y, ["summe = links + rechts", "return summe", "print(summe)"], schritt=67) + 67
    zeilenweise(seite, y, umbrechen(ZWEITER))
    arten = [(b.art, b.code.zeilen if b.code else None) for b in seitenaufbau(seite)]
    assert arten == [("absatz", None), ("code", ["summe = links + rechts", "return summe", "print(summe)"]), ("absatz", None)]


def bild_mit_rand(pfad_png) -> None:
    """Ein Rasterbild wie ein Bildschirmfoto: weiß, ein dünner Rahmen ringsum, in der Mitte ein farbiges Feld."""
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 400, 200), False)
    pix.set_rect(pix.irect, (255, 255, 255))
    for r in (fitz.IRect(0, 0, 400, 2), fitz.IRect(0, 198, 400, 200), fitz.IRect(0, 0, 2, 200), fitz.IRect(398, 0, 400, 200)):
        pix.set_rect(r, (60, 60, 60))
    pix.set_rect(fitz.IRect(150, 60, 250, 140), (40, 90, 200))
    pix.save(pfad_png)


def test_abbildung_eng_um_den_inhalt_und_seitenverhaeltnis_wie_das_bild(tmp_path):
    bild_mit_rand(tmp_path / "bild.png")
    doc = fitz.open()
    seite = doc.new_page(width=612, height=792)
    seite.insert_image(fitz.Rect(100, 300, 500, 500), filename=str(tmp_path / "bild.png"))
    seite.insert_textbox(fitz.Rect(LINKS_X, 80, RECHTS_X, 160), ERSTER, fontname="helv", fontsize=11)
    pfad = tmp_path / "bild.pdf"
    doc.save(pfad)
    (bild,) = [b for b in seitenaufbau(fitz.open(pfad)[0]) if b.art == "bild"]
    assert abs(bild.rechteck.x0 - 250) <= 4 and abs(bild.rechteck.x1 - 350) <= 4          # das Feld samt etwas Luft
    assert abs(bild.rechteck.y0 - 360) <= 4 and abs(bild.rechteck.y1 - 440) <= 4
    png = fitz.Pixmap(abbildung_png(pfad, 1, 0))
    assert abs(png.width / png.height - bild.rechteck.width / bild.rechteck.height) < 0.02


def test_listing_mit_nummern_und_kommentarzeilen_bleibt_ein_block(tmp_path):
    """Wie in Lehrbüchern: Nummern in einer eigenen Spalte, unter jeder Codezeile eine Kommentarzeile ohne Nummer, darüber
    die Beschriftung "Beispiel ...:". Ein Listing ist ein Baustein, nichts fällt weg, die Beschriftung bleibt Text."""
    from backend.app.codestellen.erkennung import aus_pdf
    from backend.app.services.textansicht import Codeteil

    doc = fitz.open()
    seite = doc.new_page(width=612, height=792)
    zeilenweise(seite, 100, umbrechen(ERSTER))
    seite.insert_text((LINKS_X, 200), "Beispiel 1.2.3:", fontname="hebo", fontsize=GROESSE_15)
    zeilen = [("7", "laenge < breite"), ("", "# False, weil beide gleich lang sind."), ("8", "laenge <= breite"),
              ("", "# True, weil 4 <= 4 ist."), ("9", "hoehe != breite"), ("", "# True, weil 3 nicht 4 ist.")]
    y = 230.0
    for i in range(0, len(zeilen), 2):
        seite.draw_rect(fitz.Rect(LINKS_X, y - 12, 102, y + 22), color=None, fill=(0.85, 0.85, 0.85))     # Spalte der Nummern
        seite.draw_rect(fitz.Rect(102, y - 12, 535, y + 22), color=None, fill=(0.93, 0.93, 0.93))         # Fläche des Codes
        nummer, code_zeile = zeilen[i]
        seite.insert_text((93, y), nummer, fontname="helv", fontsize=11)
        seite.insert_text((93 + fitz.get_text_length(nummer, "helv", 11), y), " " + code_zeile, fontname="cour", fontsize=11)
        seite.insert_text((106, y + 16), zeilen[i + 1][1], fontname="cour", fontsize=11)
        y += 34
    zeilenweise(seite, y + 30, umbrechen(ZWEITER))
    pfad = tmp_path / "listing.pdf"
    doc.save(pfad)

    teile = [Codeteil(fitz.Rect(t.rechteck), s.kennung, s.sprache, s.titel, i, len(s.teile), z)
             for s in aus_pdf(pfad) for i, (t, z) in enumerate(zip(s.teile, s.zeilen_der_teile()))]
    bausteine = seitenaufbau(fitz.open(pfad)[0], teile)
    code = [b for b in bausteine if b.art == "code"]
    assert len(code) == 1
    text = "\n".join(code[0].code.zeilen)
    reihe = [z for _, z in zeilen]
    assert all(z in text for z in reihe) and [text.index(z) for z in reihe] == sorted(text.index(z) for z in reihe)
    assert not any(z.startswith(("7", "8", "9")) for z in code[0].code.zeilen)                   # Nummern abgenommen
    assert ("absatz", "Beispiel 1.2.3:") in [(b.art, b.text) for b in bausteine]
