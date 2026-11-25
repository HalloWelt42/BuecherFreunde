"""Sachgruppen der Deutschen Nationalbibliografie: aus der Notation ("510", "B") wird ein Wort für das Regal. Die Gruppen folgen
der Dewey-Klassifikation; eine Dewey-Notation anderer Kataloge fällt auf die nächsthöhere Gruppe."""

from __future__ import annotations

import re

NAMEN = {
    "000": "Allgemeines", "004": "Informatik", "010": "Bibliografien", "020": "Bibliothekswesen", "030": "Enzyklopädien", "050": "Zeitschriften", "060": "Museumswissenschaft",
    "070": "Publizistik", "080": "Zitate", "090": "Handschriften", "100": "Philosophie", "130": "Esoterik", "150": "Psychologie", "200": "Religion", "220": "Bibel", "230": "Theologie",
    "290": "Andere Religionen", "300": "Sozialwissenschaften", "310": "Statistik", "320": "Politik", "330": "Wirtschaft", "333.7": "Energie und Umwelt", "340": "Recht",
    "350": "Öffentliche Verwaltung", "355": "Militär", "360": "Soziales", "370": "Erziehung und Bildung", "380": "Handel und Verkehr", "390": "Volkskunde", "400": "Sprache",
    "420": "Englisch", "430": "Deutsch", "439": "Germanische Sprachen", "440": "Französisch", "450": "Italienisch", "460": "Spanisch", "470": "Latein", "480": "Griechisch", "490": "Andere Sprachen",
    "500": "Naturwissenschaften", "510": "Mathematik", "520": "Astronomie", "530": "Physik", "540": "Chemie", "550": "Geowissenschaften", "560": "Paläontologie", "570": "Biologie",
    "580": "Pflanzen", "590": "Tiere", "600": "Technik", "610": "Medizin", "620": "Ingenieurwissenschaften", "621.3": "Elektrotechnik", "624": "Bauingenieurwesen", "630": "Landwirtschaft",
    "640": "Haushalt", "650": "Management", "660": "Technische Chemie", "670": "Industrielle Fertigung", "690": "Bauwesen", "700": "Kunst", "710": "Landschaftsgestaltung", "720": "Architektur",
    "730": "Bildhauerei", "740": "Grafik und Design", "741.5": "Comics", "750": "Malerei", "760": "Druckgrafik", "770": "Fotografie", "780": "Musik", "790": "Freizeit", "791": "Film und Rundfunk",
    "792": "Theater", "793": "Spiele", "796": "Sport", "800": "Literatur", "810": "Amerikanische Literatur", "820": "Englische Literatur", "830": "Deutsche Literatur",
    "839": "Skandinavische Literatur", "840": "Französische Literatur", "850": "Italienische Literatur", "860": "Spanische Literatur", "870": "Lateinische Literatur", "880": "Griechische Literatur",
    "890": "Andere Literatur", "900": "Geschichte", "910": "Reisen", "914.3": "Reisen in Deutschland", "920": "Biografien", "930": "Alte Geschichte", "940": "Geschichte Europas",
    "943": "Deutsche Geschichte", "950": "Geschichte Asiens", "960": "Geschichte Afrikas", "970": "Geschichte Nordamerikas", "980": "Geschichte Südamerikas", "990": "Geschichte anderer Länder",
    "B": "Belletristik", "K": "Kinder- und Jugendbuch", "S": "Schulbuch",
}
EINZELN_HOECHSTENS = 3          # mehr Notationen in einem Feld: alte Sammelgruppe, dann zählen nur die Buchstaben


def aus_dnb(notationen: list[str]) -> list[str]:
    buchstaben = [n for n in notationen if n in ("B", "K", "S")]
    gemeint = buchstaben or (notationen if len(notationen) <= EINZELN_HOECHSTENS else [])
    return list(dict.fromkeys(NAMEN[n] for n in gemeint if n in NAMEN))


def aus_dewey(notation: str) -> str:
    """"005.1" -> Informatik, "519" -> Mathematik; leer, wenn es keine ist."""
    treffer = re.match(r"\d{3}(?:\.\d+)?", (notation or "").strip())
    if not treffer:
        return ""
    n = treffer.group()
    if n[:3] in ("005", "006"):
        return NAMEN["004"]
    for teil in (n[:5], n[:3], n[:2] + "0", n[0] + "00"):
        if teil in NAMEN:
            return NAMEN[teil]
    return ""
