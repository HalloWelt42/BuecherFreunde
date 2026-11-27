"""Gemeinsame Regeln zum Lesen einer PDF-Seite (BF-103, BF-104): Ligaturen, falsch abgebildete Ligaturen, sichtbare
Zeichnungen. Die Seiten entstehen hier; die Fehlzeichen stehen als Codepunkte, keine Buchkopien."""

import fitz

from backend.app.services.pdfseite import (TEXTART, TEXTART_SCHLICHT, fehlzeichen_aus_spuren, fehlzeichen_der_seite,
                                           fehlzeichen_im_wort, ligaturen_aufloesen, seitentext, sichtbare_zeichnungen)

TI, TT, FT = chr(0x19F), chr(0x1A9), chr(0x14C)          # so kommen "ti", "tt" und "ft" aus einer Fehlschrift


def spur(schrift: str, *zeichen: tuple[int, int]) -> dict:
    """Eine Spanne wie aus get_texttrace: Schrift und je Zeichen (Unicode, Glyphennummer, Ursprung, Rahmen)."""
    return {"font": schrift, "chars": [(u, g, (0, 0), (0, 0, 1, 1)) for u, g in zeichen]}


def test_textschicht_ohne_ligaturen():
    assert not TEXTART & fitz.TEXT_PRESERVE_LIGATURES and not TEXTART_SCHLICHT & fitz.TEXT_PRESERVE_LIGATURES


def test_fehlzeichen_nur_wo_die_glyphe_der_fehlschrift_ohne_zeichen_steht():
    ohne = 0xFFFD                                         # die Glyphe hat im PDF kein Zeichen (ToUnicode 0)
    assert fehlzeichen_aus_spuren([spur("ABCDEF+Calibri", (ord("a"), 68), (ohne, 0x19F)), spur("Calibri-Bold", (ohne, 0x14C))]) \
        == {TI, FT}
    assert fehlzeichen_aus_spuren([spur("TimesNewRomanPSMT", (ohne, 0x19F))]) == frozenset()       # keine Fehlschrift
    assert fehlzeichen_aus_spuren([spur("Calibri", (0x19F, 0x19F))]) == frozenset()                # mit eigenem Zeichen
    assert fehlzeichen_aus_spuren([spur("Calibri", (ohne, 0x398))]) == frozenset()                 # keine bekannte Ligatur


def test_ohne_fehlschrift_keine_spur():
    doc = fitz.open()
    seite = doc.new_page()
    seite.insert_text((72, 100), "Ein Satz in einer anderen Schrift.", fontname="helv", fontsize=11)
    assert fehlzeichen_der_seite(seite) == frozenset()


def test_ligaturen_aufloesen_an_jedem_wort_der_seite():
    zeichen = frozenset({TI, TT, FT})
    assert ligaturen_aufloesen("Funk" + TI + "on, Schri" + TT + " und o" + FT, zeichen) == "Funktion, Schritt und oft"
    assert ligaturen_aufloesen(TI + "ef unten", zeichen) == "tief unten"                     # auch am Wortanfang
    assert ligaturen_aufloesen("Funk" + TI + "on", frozenset()) == "Funk" + TI + "on"        # ohne Beleg bleibt es
    assert ligaturen_aufloesen("ein " + TI + " allein", zeichen) == "ein " + TI + " allein"   # nicht an einem Wort


def test_in_grossbuchstaben_gross():
    assert ligaturen_aufloesen("FUNK" + TI + "ON und Schri" + TT, frozenset({TI, TT})) == "FUNKTION und Schritt"


def test_fehlzeichen_im_wort_zaehlt_nur_zwischen_buchstaben():
    assert fehlzeichen_im_wort("Funk" + TI + "on, " + TI + " allein, Schri" + TT + " und Ende" + FT) == 1
    assert fehlzeichen_im_wort("Ein Text ohne solche Zeichen.") == 0


def test_seitentext_ohne_fehlzeichen_bleibt_gleich():
    doc = fitz.open()
    seite = doc.new_page()
    seite.insert_text((72, 100), "Ein ganz normaler Satz ohne besondere Zeichen.", fontname="helv", fontsize=11)
    assert seitentext(seite).strip() == "Ein ganz normaler Satz ohne besondere Zeichen."


def test_sichtbare_zeichnungen_ohne_hintergrund_und_beschnitten():
    doc = fitz.open()
    seite = doc.new_page(width=612, height=792)
    seite.draw_rect(fitz.Rect(60, -3000, 550, 9000), color=None, fill=(1, 1, 1))          # Hintergrund des Kapitels
    seite.draw_rect(fitz.Rect(77, 700, 535, 900), color=None, fill=(0.93, 0.95, 0.96))    # Kasten geht auf der nächsten weiter
    seite.draw_rect(fitz.Rect(90, 720, 200, 740), color=None, fill=(1, 1, 1))             # weiße Innenfläche bleibt
    zeichnungen = sichtbare_zeichnungen(seite)
    assert [(round(d["rect"].y0), round(d["rect"].y1), d["beschnitten"]) for d in zeichnungen] == [(700, 792, True),
                                                                                                    (720, 740, False)]
