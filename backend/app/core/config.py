"""Zentrale Konfiguration - alle Werte aus .env oder Umgebungsvariablen."""

from pathlib import Path
from pydantic_settings import BaseSettings


def _project_root() -> Path:
    """Ermittelt das Projektstammverzeichnis (zwei Ebenen ueber diesem Modul)."""
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

    # Authentifizierung
    api_token: str = "bitte-aendern-sicherer-token-hier"

    # Pfade
    storage_dir: Path = _project_root() / "storage"
    external_dir: Path = _project_root() / "external"
    import_dir: Path = _project_root() / "import"
    database_dir: Path = _project_root() / "database"

    # Open Library
    openlibrary_enabled: bool = True
    openlibrary_rate_limit: int = 1

    # LM Studio
    lm_studio_enabled: bool = False
    lm_studio_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "qwen2.5"

    # Logging
    log_level: str = "info"

    # Version (nur lesend)
    version: str = _read_version()

    model_config = {
        "env_file": str(_project_root() / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def database_path(self) -> Path:
        return self.database_dir / "buecherfreunde.db"

    @property
    def backup_dir(self) -> Path:
        return self.database_dir / "backups"

    def public_config(self) -> dict:
        """Gibt die oeffentlich sichtbaren Konfigurationswerte zurueck (ohne Token)."""
        return {
            "version": self.version,
            "external_port": self.external_port,
            "openlibrary": {
                "aktiviert": self.openlibrary_enabled,
                "rate_limit": self.openlibrary_rate_limit,
            },
            "lm_studio": {
                "aktiviert": self.lm_studio_enabled,
                "url": self.lm_studio_url,
                "modell": self.lm_studio_model,
            },
            "pfade": {
                "speicher": str(self.storage_dir),
                "extern": str(self.external_dir),
                "import": str(self.import_dir),
                "datenbank": str(self.database_dir),
            },
        }


settings = Settings()
