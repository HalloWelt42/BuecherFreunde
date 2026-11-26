"""Zentrale Konfiguration - alle Werte aus .env oder Umgebungsvariablen."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


def _project_root() -> Path:
    """Ermittelt das Projektstammverzeichnis (zwei Ebenen über diesem Modul)."""
    return Path(__file__).resolve().parent.parent.parent.parent


def _read_version() -> str:
    """Liest die Version aus der zentralen VERSION-Datei."""
    version_file = _project_root() / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0"


class Settings(BaseSettings):
    """Anwendungskonfiguration mit Umgebungsvariablen."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    external_port: int = 8160

    # Pfade
    storage_dir: Path = _project_root() / "storage"
    external_dir: Path = _project_root() / "external"
    import_dir: Path = _project_root() / "import"
    database_dir: Path = _project_root() / "database"
    # Orte des Neubaus (ablage/orte.py); ohne Angabe liegen sie wie früher beim Speicher und bei der Datenbank
    suche_dir: Path = Path("")
    umschlaege_dir: Path = Path("")
    zwischen_dir: Path = _project_root() / "zwischen"
    zwischen_mb: int = 900             # so viel dürfen Originale im Zwischenspeicher belegen
    ablage_ordner: str = "Apps/BücherFreunde"
    # Eingangsordner auf dem Gerät (ohne Kellerwolke): was hier liegt, nimmt die App jede Minute auf und zieht es um
    eingangsordner_dir: Path = _project_root() / "eingangsordner"

    # Fundus (Suche nach Bedeutung) und Assistent; leer: die Fähigkeit fehlt, die App läuft weiter
    fundus_url: str = ""
    fundus_sammlung: str = "Bücher"
    assistent_url: str = ""
    nachschlag_url: str = ""           # Nachschlagen in Lexika und Handbüchern; leer: die Fähigkeit fehlt
    # Codestellen ausführen (BF-29): Sandbox der Codeschmiede; leer: die Fähigkeit fehlt, die Erkennung läuft trotzdem
    codeschmiede_url: str = ""
    codestellen_je_runde: int = Field(default=3, ge=0)        # so viele Bücher erkennt die Pflege je Runde nach (alle 10 Minuten)
    vorpruefung_abstand_s: float = Field(default=5.0, ge=0)   # Pause zwischen zwei Vorprüfungen, damit die Sandbox frei bleibt
    # Leitstelle: der eine Weg zur KI (Vorprüfung, Einordnen); leer: ohne KI, eingeordnet wird von Hand
    leitstelle_adresse: str = ""
    leitstelle_schluessel_datei: str = ""                     # Schlüssel der Anwendung (Datei, Modus 0600)
    ki_modell: str = "qwen/qwen3-next-80b"                    # Modellwahl der App; die Leitstelle wählt nie eins
    sprechdienst: str = "klangwerk-sprechen"                  # Vorlesen über diesen Dienst der Leitstelle; ohne: Stimmen des Geräts
    # Gestaltete Deckblätter (BF-59): die Umschlagprüfung findet schlichte Umschläge, die lokale KI ordnet diese Bücher ein
    umschlaege_pruefen_takt_s: float = Field(default=600, gt=0)   # so oft sieht die Umschlagprüfung nach neuen oder geänderten Umschlägen
    # Art aller Werke (BF-77): erst feste Regeln (services/artregeln.py), den Rest die lokale KI, gebündelt
    einordnen_an: bool = True                                    # Art (und, wo das Deckblatt sie braucht, Gattung) bestimmen
    einordnen_takt_s: float = Field(default=600, gt=0)          # so oft sieht das Einordnen von selbst nach offenen Werken
    einordnen_abstand_s: float = Field(default=5, ge=0)         # Pause zwischen zwei Anfragen an die KI
    einordnen_je_anfrage: int = Field(default=40, ge=1, le=200)  # so viele Werke je Anfrage an die KI
    einordnen_buch_ab_seiten: int = Field(default=40, ge=0)      # mit ISBN und mehr Seiten: ein Buch
    einordnen_dokument_bis_seiten: int = Field(default=4, ge=0)  # ohne ISBN und höchstens so viele Seiten: ein Dokument
    # Sammlungen finden (BF-66): Reihen aus Titeln und Dateinamen, geprüft von der lokalen KI
    sammlung_vorschlag_ab: int = Field(default=3, ge=2)          # ab so vielen Büchern einer Reihe ein Vorschlag
    sammlungen_finden_abstand_s: float = Field(default=5, ge=0)  # Pause zwischen zwei Anfragen an die KI
    # Katalog (BF-69): Vorgaben; was in den Einstellungen (app_settings, katalog/einstellungen.py) steht, gilt vor ihnen
    katalog_stapel: int = Field(default=500, ge=1)               # so viele Titel je Stapel eines Laufs
    katalog_ki_je_anfrage: int = Field(default=40, ge=1)         # so viele Bücher je Anfrage an die KI
    katalog_sicher_ab: int = Field(default=80, ge=0, le=100)     # so sichere Vorschläge sind vorab angehakt
    katalog_teilen_ab: int = Field(default=300, ge=1)            # über so vielen Treffern wird eine Kategorie im Entwurf geteilt
    # nur hier einstellbar:
    katalog_abstand_s: float = Field(default=5, ge=0)            # Pause zwischen zwei Anfragen an die KI
    katalog_neu_ab: int = Field(default=3, ge=1)                 # ab so vielen Büchern zählt ein Schlagwort ohne Kategorie als häufig

    # Quellen für Angaben zu Büchern und Autoren (backend/app/quellen), jede freiwillig und ohne Schlüssel.
    # Google Books antwortet seit 2026 nur noch mit eigenem Schlüssel
    google_books_enabled: bool = True
    google_books_api_key: str = ""
    openlibrary_enabled: bool = True
    openlibrary_rate_limit: int = 1    # Anfragen je Sekunde
    wikipedia_enabled: bool = True     # Wikipedia und Wikidata
    dnb_enabled: bool = True           # Deutsche Nationalbibliothek
    k10plus_enabled: bool = True       # Verbundkatalog K10plus
    crossref_enabled: bool = True      # Fachartikel und Fachbücher mit DOI
    gnd_enabled: bool = True           # Gemeinsame Normdatei (Autoren)
    gutenberg_enabled: bool = True     # gemeinfreie Bücher
    quellen_kontakt: str = ""          # freiwillig: Adresse einer Seite oder Mail im Ausweis der App, manche Quellen erlauben damit mehr
    quellen_hintergrund_tag: int = Field(default=500, ge=1)   # höchstens so viele Anfragen je Quelle und Tag in Hintergrundläufen
    quellen_vorrat_mb: int = Field(default=32, ge=1)          # so viel dürfen gemerkte Antworten in der Datenbank belegen
    suche_ausdruck_s: float = Field(default=5.0, gt=0)        # so lange darf ein regulärer Ausdruck im Buch suchen

    # Host-Pfade (von Docker durchgereicht, für Anzeige im Frontend)
    host_storage_dir: str = ""
    host_external_dir: str = ""
    host_import_dir: str = ""
    host_database_dir: str = ""

    # Anbieter für Fundus (fundus-anbieter/1): Apps rufen mit ihrem App-Schlüssel der Kellerwolke;
    # geprüft wird bei der Kellerwolke, wer ruft. Nur die genannten Apps dürfen den Bestand lesen.
    kellerwolke_url: str = ""
    kellerwolke_ca: str = ""          # Zertifikatsstelle für https zur Kellerwolke; leer: die üblichen Stellen
    kellerwolke_schluessel_datei: str = ""   # eigener App-Zugang der Kellerwolke (Datei, Modus 0600)
    anmeldung_konten: str = ""        # weitere Konten der Kellerwolke, die die App nutzen dürfen (kommagetrennt)
    fundus_apps: str = "Fundus"       # Kommagetrennte Namen der Apps, die den Bestand lesen dürfen

    # Sicherungsregel (backend/app/services/sicherung.py): regelmäßig nur, wenn die jüngste älter ist als
    # sicherung_abstand_tage, vor dem Aktualisieren nur, wenn sie älter ist als sicherung_vor_ausrollen_ab_stunden; nie
    # ohne Änderung; es bleiben höchstens sicherung_behalten Stände.
    sicherung_abstand_tage: int = 7
    sicherung_vor_ausrollen_ab_stunden: int = 24
    sicherung_behalten: int = Field(default=3, ge=1)

    # Logging
    log_level: str = "info"

    # Version (nur lesend)
    version: str = _read_version()

    model_config = {
        "env_file": str(_project_root() / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def model_post_init(self, _kontext) -> None:
        if not self.suche_dir.name:
            self.suche_dir = self.database_dir
        if not self.umschlaege_dir.name:
            self.umschlaege_dir = self.storage_dir

    @property
    def host_pfade(self) -> dict[str, str]:
        """Pfade auf dem Gerät, wie Compose sie eingehängt hat (nur zur Anzeige)."""
        return {"bestand": self.host_database_dir, "suche": "", "texte": self.host_storage_dir, "umschlaege": "", "zwischen": "Arbeitsspeicher" if "/app/" in str(self.zwischen_dir) else ""}

    @property
    def database_path(self) -> Path:
        return self.database_dir / "buecherfreunde.db"

    @property
    def backup_dir(self) -> Path:
        return self.database_dir / "backups"

    def public_config(self) -> dict:
        """Gibt die öffentlich sichtbaren Konfigurationswerte zurück (ohne Token)."""
        return {
            "version": self.version,
            "external_port": self.external_port,
            "google_books": {
                "aktiviert": self.google_books_enabled,
                "hat_api_key": bool(self.google_books_api_key),
            },
            "openlibrary": {
                "aktiviert": self.openlibrary_enabled,
                "rate_limit": self.openlibrary_rate_limit,
            },
            "wikipedia": {
                "aktiviert": self.wikipedia_enabled,
            },
            "quellen": {
                "dnb": self.dnb_enabled,
                "k10plus": self.k10plus_enabled,
                "crossref": self.crossref_enabled,
                "gnd": self.gnd_enabled,
                "gutenberg": self.gutenberg_enabled,
                "kontakt": bool(self.quellen_kontakt),
                "hintergrund_tag": self.quellen_hintergrund_tag,
            },
            # KI über die Leitstelle; der Feldname ist der, den die Oberfläche liest
            "lm_studio": {
                "aktiviert": bool(self.leitstelle_adresse.strip() and self.leitstelle_schluessel_datei),
                "url": self.leitstelle_adresse,
                "modell": self.ki_modell,
            },
            "pfade": {
                "speicher": str(self.storage_dir),
                "extern": str(self.external_dir),
                "import": str(self.import_dir),
                "datenbank": str(self.database_dir),
            },
        }


settings = Settings()
