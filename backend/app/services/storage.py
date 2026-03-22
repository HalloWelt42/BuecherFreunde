"""Hash-basiertes Dateispeichersystem.

Dateien werden anhand ihres SHA-256 Hashwerts in einer zweistufigen
Verzeichnisstruktur abgelegt: /ab/cd/abcdef1234.../
Neben jeder Datei liegen Sidecar-Dateien: metadata.json, cover.jpg, fulltext.txt
"""

import hashlib
import json
import logging
import re
import shutil
from pathlib import Path

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.storage")

HASH_CHUNK_SIZE = 65536
SUPPORTED_FORMATS = {".pdf", ".epub", ".mobi", ".txt", ".md"}

# Zeichen die auf Dateisystemen ungültig sind
_UNSAFE_CHARS = re.compile(r'[<>:"|?*\x00-\x1f\\]')


def sanitize_filename(name: str) -> str:
    """Bereinigt Dateinamen: entfernt Pfad, ersetzt ungültige Zeichen."""
    clean = Path(name).name
    clean = _UNSAFE_CHARS.sub("_", clean)
    clean = re.sub(r"_{2,}", "_", clean)
    return clean.strip("_. ") or "unbenannt"


def compute_hash(file_path: Path) -> str:
    """Berechnet den SHA-256 Hashwert einer Datei (chunk-basiert)."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(HASH_CHUNK_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_hash_from_bytes(data: bytes) -> str:
    """Berechnet den SHA-256 Hashwert von Bytes."""
    return hashlib.sha256(data).hexdigest()


def get_storage_path(file_hash: str, storage_dir: Path | None = None) -> Path:
    """Gibt den Speicherpfad für einen Hash zurück: /ab/cd/abcdef.../"""
    base = storage_dir or settings.storage_dir
    return base / file_hash[:2] / file_hash[2:4] / file_hash


def file_exists_in_storage(file_hash: str, storage_dir: Path | None = None) -> bool:
    """Prüft ob eine Datei mit diesem Hash bereits im Speicher existiert."""
    path = get_storage_path(file_hash, storage_dir)
    return path.exists()


def check_duplicate(file_hash: str) -> dict | None:
    """Prüft beide Speicherorte auf Duplikate.

    Gibt ein dict mit Infos zurück wenn Duplikat gefunden, sonst None.
    """
    # Hauptspeicher prüfen
    if file_exists_in_storage(file_hash, settings.storage_dir):
        return {
            "gefunden_in": "hauptspeicher",
            "pfad": str(get_storage_path(file_hash, settings.storage_dir)),
        }

    # Externen Speicher prüfen (falls konfiguriert und vorhanden)
    if settings.external_dir.exists():
        if file_exists_in_storage(file_hash, settings.external_dir):
            return {
                "gefunden_in": "extern",
                "pfad": str(get_storage_path(file_hash, settings.external_dir)),
            }

    return None


def store_file(
    source_path: Path,
    file_hash: str | None = None,
    storage_dir: Path | None = None,
) -> tuple[str, Path]:
    """Speichert eine Datei im Hash-Speicher.

    Args:
        source_path: Pfad zur Quelldatei
        file_hash: Optionaler vorberechneter Hash
        storage_dir: Optionaler Speicherort (Standard: settings.storage_dir)

    Returns:
        Tuple aus (hash, storage_path)

    Raises:
        FileExistsError: Wenn die Datei bereits existiert
        ValueError: Wenn das Dateiformat nicht unterstützt wird
    """
    if not source_path.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {source_path}")

    suffix = source_path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Format '{suffix}' nicht unterstützt. "
            f"Erlaubt: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    if file_hash is None:
        file_hash = compute_hash(source_path)

    base = storage_dir or settings.storage_dir
    target_dir = get_storage_path(file_hash, base)

    if target_dir.exists():
        raise FileExistsError(f"Datei existiert bereits: {file_hash}")

    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(source_path.name)
    target_file = target_dir / safe_name
    shutil.copy2(source_path, target_file)

    logger.info(
        "Datei gespeichert: %s -> %s",
        source_path.name,
        target_dir.relative_to(base),
    )
    return file_hash, target_dir


def get_sidecar_path(file_hash: str, filename: str, storage_dir: Path | None = None) -> Path:
    """Gibt den Pfad zu einer Sidecar-Datei zurück."""
    return get_storage_path(file_hash, storage_dir) / filename


def save_metadata(file_hash: str, metadata: dict, storage_dir: Path | None = None) -> Path:
    """Speichert Metadaten als JSON-Sidecar."""
    path = get_sidecar_path(file_hash, "metadata.json", storage_dir)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_metadata(file_hash: str, storage_dir: Path | None = None) -> dict | None:
    """Lädt Metadaten aus dem JSON-Sidecar."""
    path = get_sidecar_path(file_hash, "metadata.json", storage_dir)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_fulltext(file_hash: str, text: str, storage_dir: Path | None = None) -> Path:
    """Speichert den extrahierten Volltext als Sidecar."""
    path = get_sidecar_path(file_hash, "fulltext.txt", storage_dir)
    path.write_text(text, encoding="utf-8")
    return path


def load_fulltext(file_hash: str, storage_dir: Path | None = None) -> str | None:
    """Lädt den Volltext aus dem Sidecar."""
    path = get_sidecar_path(file_hash, "fulltext.txt", storage_dir)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def save_cover(file_hash: str, image_data: bytes, storage_dir: Path | None = None) -> Path:
    """Speichert ein Cover-Bild als Sidecar."""
    path = get_sidecar_path(file_hash, "cover.jpg", storage_dir)
    path.write_bytes(image_data)
    return path


def get_original_file(file_hash: str, storage_dir: Path | None = None) -> Path | None:
    """Findet die Originaldatei im Hash-Verzeichnis."""
    dir_path = get_storage_path(file_hash, storage_dir)
    if not dir_path.exists():
        return None

    sidecar_names = {"metadata.json", "fulltext.txt", "cover.jpg"}
    for f in dir_path.iterdir():
        if f.name not in sidecar_names and f.is_file():
            return f
    return None


def delete_stored_file(file_hash: str, storage_dir: Path | None = None) -> bool:
    """Löscht eine Datei und alle Sidecars aus dem Speicher."""
    dir_path = get_storage_path(file_hash, storage_dir)
    if not dir_path.exists():
        return False

    shutil.rmtree(dir_path)
    logger.info("Datei gelöscht: %s", file_hash)

    # Leere Elternverzeichnisse aufräumen
    parent = dir_path.parent
    try:
        parent.rmdir()
        parent.parent.rmdir()
    except OSError:
        pass  # Nicht leer, ist ok

    return True


def get_storage_stats(storage_dir: Path | None = None) -> dict:
    """Gibt Statistiken zum Speicher zurück."""
    base = storage_dir or settings.storage_dir
    if not base.exists():
        return {"anzahl_dateien": 0, "gesamtgroesse": 0, "pfad": str(base)}

    total_size = 0
    file_count = 0

    for f in base.rglob("*"):
        if f.is_file():
            total_size += f.stat().st_size
            file_count += 1

    return {
        "anzahl_dateien": file_count,
        "gesamtgroesse": total_size,
        "gesamtgroesse_mb": round(total_size / (1024 * 1024), 2),
        "pfad": str(base),
    }
