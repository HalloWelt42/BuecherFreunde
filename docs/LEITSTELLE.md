# Anbindung an die Leitstelle

Einzige Wahrheit über den Stand der Anbindung von BücherFreunde an die Leitstelle (nach deren Anweisung `ANBINDUNG.md`,
Abschnitt 9).

## Rolle und Stufe

- Rolle: Anwendung (ruft Sprachmodelle auf, stellt nichts bereit).
- Stufe ist: 1, Fassade. Adresse und Schlüssel aus der Einrichtung, das Modell wählt die App.
- Stufe soll: 1. Stufe 2 und 3 (Anmeldung, Signale über den Kanal) folgen, sobald die Leitstelle Anwendungen über den
  Kanal anmeldet; Stufe 4 (Aufträge über das Protokoll) für lange Vorprüfungen, sobald es sie gibt.
- Anwendung in der Leitstelle: "BücherFreunde", Fähigkeiten `text` und `einordnen`, zwei Aufträge zugleich.

## Einstellungen

| Wert | Bedeutung |
|---|---|
| `LEITSTELLE_ADRESSE` | Adresse der Leitstelle (mit oder ohne `/v1`); leer: ohne KI |
| `LEITSTELLE_SCHLUESSEL_DATEI` | Schlüssel der Anwendung als Datei, Modus 0600; im Betrieb `zugang/leitstelle.schluessel`, im Container `/app/zugang/leitstelle.schluessel` (der Ordner `zugang` ist schon nur lesend eingehängt) |
| `KI_MODELL` | Modellwahl der App (Vorgabe `qwen/qwen3-next-80b`); die Leitstelle wählt nie ein Modell |

Die Zertifikatsstelle des Hauses gilt wie für die Kellerwolke (`KELLERWOLKE_CA`).

## Ein Ort für KI

`backend/app/services/ki.py` ist der einzige Weg zur KI. Den Zugang bringt der Appkern mit (`appkern.leitstelle`):

- keine Lese-Zeitgrenze für Arbeit, nur zehn Sekunden für den Verbindungsaufbau;
- Gesundheit nur über `GET /v1/models` (lädt nie ein Modell), zu sehen unter `GET /api/verbindungen`;
- jeder Auftrag trägt Titel ("BücherFreunde: Vorprüfung ...") und, wo es passt, die Priorität `hintergrund`;
- kein Wiederholen von selbst; Fehler der Leitstelle werden zu Gründen in Worten:
  - Schlüssel unbekannt, Fähigkeit oder Zone nicht erlaubt, Modell unbekannt, gesperrt: ein Mensch ist gefragt, nichts wird
    wiederholt;
  - Halt, Dienst weg, Rechner schläft: im Hintergrund wartet der Aufruf geduldig (Retry-After der Leitstelle, beim
    schlafenden Rechner ohne Grenze) und lässt sich dabei anhalten;
  - in der Leitstelle abgebrochen, Eingabe passt nicht, Fehler des Dienstes: nur diese eine Anfrage ging nicht.

## Wer die KI nutzt

| Teil | Fähigkeit | Priorität | Was ohne Leitstelle geschieht |
|---|---|---|---|
| Vorprüfung der Codestellen (BF-29, `codestellen/vorpruefung.py`) | `text`, Antwort in fester Form (JSON-Schema) | `hintergrund`, alle Anfragen einer Runde als eine Arbeit (`X-Leitstelle-Arbeit`) | der Fehler des Laufs ist der Grund |
| Einordnen von Büchern (`services/ai_categorization.py`) | noch direkt über `LM_STUDIO_*` | - | Einordnen von Hand |

## Was geändert wurde

- BF-29: `services/ki.py` (Leitstellen-Anschluss), Einstellungen `LEITSTELLE_ADRESSE`, `LEITSTELLE_SCHLUESSEL_DATEI`,
  `KI_MODELL`; Vorprüfung der Codestellen als erste Nutzerin; Leitstelle unter `GET /api/verbindungen`.

## Was zurückgebaut wurde

- Noch nichts; das Einordnen läuft bis zur Umstellung über die eigene Adresse.

## Abnahme Stufe 1

| Punkt | Stand |
|---|---|
| Antwort über die Fassade | gegen eine Attrappe geprüft (`tests/api/test_ausfuehren.py`): Modell, Schlüssel, Titel, Priorität, Arbeit |
| Warten ohne Zeitgrenze | im Appkern ohne Lese-Zeitgrenze; Halt mit Retry-After gegen die Attrappe geprüft (wartet, fragt erneut, lässt sich anhalten) |
| Halt zeigt Hinweis statt Fehlerspur | Grund in der Vorprüfung (`GET /api/ausfuehren/vorpruefung`) |
| Anwendung und Aufträge in der Leitstelle sichtbar | offen: an der echten Leitstelle zu prüfen |
| Rückbau sichtbar | offen: Einordnen noch über `LM_STUDIO_*` |

## Offene Punkte

- Einordnen auf denselben Anschluss umstellen, `LM_STUDIO_*` und die Netzsuche nach Modell-Läufern zurückbauen.
- Prüfung an der echten Leitstelle (Anwendung sichtbar, Auftrag im Verlauf mit Dauer und Modell).
- Stufe 2 und 3, sobald die Leitstelle Anwendungen über den Kanal anmeldet.
