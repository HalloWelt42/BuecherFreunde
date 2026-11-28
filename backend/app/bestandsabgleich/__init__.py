"""Abgleich mit dem Bestand (BF-119): Bücher, die eine fremde Seite anbietet, gegen die eigene Bibliothek, für die Erweiterung
im Browser. Die Erweiterung liest nur die Seite und zeigt an; ob ein Buch schon da ist, entscheidet allein dieses Paket, mit
denselben Regeln für Titel und Namen wie der Abgleich mit den Quellen (`quellen/abgleich.py`).

- `modelle.py`: was die Erweiterung schickt und zurückbekommt
- `regeln.py`: die Stufe eines Kandidaten (vorhanden, ähnlich) und der Vergleich Feld für Feld, ohne Datenbank
- `dienst.py`: Kandidaten aus Bestand und Suchindex, nur was das Profil sieht
"""
