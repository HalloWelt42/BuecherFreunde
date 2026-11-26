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
| `KI_MODELL` | Modellwahl der App (Vorgabe `qwen/qwen3-next-80b`); in den Einstellungen änderbar (`PATCH /api/ai/config`, gemerkt als `ki_modell` in `app_settings`), die Leitstelle wählt nie ein Modell |

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
| Einordnen von Büchern (BF-10, `services/ai_categorization.py`) | `text`, Anweisung aus `ai_prompts` | Vorgabe der App (ein Mensch wartet) | keine Vorschläge, Grund statt Fehler; eingeordnet wird von Hand |

## Was geändert wurde

- BF-29: `services/ki.py` (Leitstellen-Anschluss), Einstellungen `LEITSTELLE_ADRESSE`, `LEITSTELLE_SCHLUESSEL_DATEI`,
  `KI_MODELL`; Vorprüfung der Codestellen als erste Nutzerin; Leitstelle unter `GET /api/verbindungen`.
- BF-10: das Einordnen nutzt denselben Anschluss und denselben Schlüssel. `GET /api/ai/status` fragt nur die Modellliste der
  Leitstelle; `GET /api/ai/config` nennt Adresse, Modell und ob eingerichtet; `PATCH /api/ai/config` wählt nur noch das
  Modell, eine Adresse lehnt es mit Hinweis auf die Einrichtung ab. Anschluss `ki` heißt: Leitstelle eingerichtet. Eine
  früher gewählte Modellwahl (`lm_studio_model`) gilt als Wahl für die Leitstelle weiter; der alte Wert bleibt stehen.

## Was zurückgebaut wurde

- BF-10: Einstellungen `LM_STUDIO_ENABLED`, `LM_STUDIO_URL`, `LM_STUDIO_MODEL`, `KI_SCHLUESSEL_DATEI` (config.py,
  .env.example, README, install.sh, setup.sh, einrichten.sh).
- BF-10: eigener Aufruf der Vervollständigung mit Lese-Zeitgrenze 60 s und eigenem Schlüsselkopf (`send_prompt` alt,
  `_kopf`), Erreichbarkeitsprüfung über die Modellliste des Läufers mit Zeitgrenze 5 s (`check_connection`), Adresse
  aus der Oberfläche (`PATCH /api/ai/config` mit `lm_studio_url`) und die Suche nach Modell-Läufern im Netz
  (`GET /api/ai/scan`, Ausweichliste von Adressen).

## Abnahme Stufe 1

| Punkt | Stand |
|---|---|
| Antwort über die Fassade | gegen eine Attrappe geprüft (`tests/api/test_ausfuehren.py`, `tests/api/test_ki_einordnen.py`): Modell, Schlüssel, Titel, Priorität, Arbeit; am 26.11.2026 sparsam an der echten Leitstelle: Modellliste mit `qwen/qwen3-next-80b`, Einschätzungen der Vorprüfung und ein Einordnen kamen an |
| Warten ohne Zeitgrenze | im Appkern ohne Lese-Zeitgrenze; Halt mit Retry-After gegen die Attrappe geprüft (wartet, fragt erneut, lässt sich anhalten) |
| Halt zeigt Hinweis statt Fehlerspur | Grund in der Vorprüfung (`GET /api/ausfuehren/vorpruefung`) |
| Anwendung und Aufträge in der Leitstelle sichtbar | offen: Aufträge liefen, ihr Eintrag im Verlauf (Dauer, Modell) ist in der Oberfläche der Leitstelle noch anzusehen |
| Rückbau sichtbar | ja: keine eigene Adresse, keine Netzsuche, keine Lese-Zeitgrenze, kein Laden oder Entladen; die Modellwahl bleibt bei der App |

## Offene Punkte

- Oberfläche: Die Felder der KI-Einstellungen heißen in der Schnittstelle noch wie früher (`lm_studio` in `GET /api/config`,
  `lm_studio_model` in `PATCH /api/ai/config`), damit die heutige Oberfläche weiterläuft; umbenennen zusammen mit der
  Oberfläche. Dort entfallen dann Adressfeld und "Netz absuchen" (die Schnittstelle lehnt die Adresse ab, die Suche gibt
  es nicht mehr).
- Verlauf der Leitstelle ansehen: Aufträge "BücherFreunde: Vorprüfung ..." und "BücherFreunde: Einordnen ..." mit Dauer und Modell.
- Im Betrieb die `.env` ergänzen: `LEITSTELLE_ADRESSE`, `LEITSTELLE_SCHLUESSEL_DATEI=/app/zugang/leitstelle.schluessel`.
- Stufe 2 und 3, sobald die Leitstelle Anwendungen über den Kanal anmeldet.
