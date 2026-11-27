"""Texterkennung für gescannte Bücher (BF-109, docs/neubau/TEXTERKENNUNG.md): Seiten eines PDF ohne lesbaren Text werden
klassisch erkannt, damit Textansicht, Volltext, Suche und Codestellen sie lesen können. Die Erkennung ist eine Rückfallschicht
(docs/neubau/SCHICHTEN.md): ohne das Programm auf dem Gerät ruht sie mit Grund, und die App läuft ohne sie weiter.

Aufbau:
- werkzeug.py: das Programm als eigener Prozess (bereit oder nicht, mit Grund; eine Seite als TSV, mit Frist und Kernen)
- erkennen.py: eine Seite rendern und erkennen, das Ergebnis in PDF-Punkten (`Seitenerkennung`, modelle.py)
- ablage.py: `erkennung.jsonl` je Buch im Ort texte, nur angehängt, die jüngste Zeile je Seite gilt
- textschicht.py: die eine Stelle, die je Seite entscheidet, ob die Textschicht des PDF gilt oder ihre Erkennung
- auftrag.py: der Auftrag "Texte erkennen" mit Vorrang für die gelesenen Seiten und seiner Wache"""
