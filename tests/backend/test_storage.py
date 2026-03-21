"""Tests fuer das Hash-basierte Dateispeichersystem.

Testet Hash-Berechnung, Speicherung, Duplikaterkennung,
Sidecar-Dateien und Speicher-Statistiken.
"""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.app.services.storage import (
    SUPPORTED_FORMATS,
    compute_hash,
    compute_hash_from_bytes,
    get_storage_path,
    file_exists_in_storage,
    store_file,
    check_duplicate,
    save_metadata,
    load_metadata,
    save_fulltext,
    load_fulltext,
    save_cover,
    get_original_file,
    get_sidecar_path,
    delete_stored_file,
    get_storage_stats,
)


# ---------------------------------------------------------------------------
# Hash-Berechnung
# ---------------------------------------------------------------------------

class TestHashBerechnung:
    """Tests fuer die SHA-256 Hash-Funktionen."""

    def test_hash_von_datei_berechnen(self, erstelle_textdatei):
        """Hash einer Datei muss dem erwarteten SHA-256 entsprechen."""
        inhalt = "Hallo Welt - Testinhalt"
        datei = erstelle_textdatei("test.txt", inhalt)
        erwartet = hashlib.sha256(inhalt.encode("utf-8")).hexdigest()
        ergebnis = compute_hash(datei)
        assert ergebnis == erwartet

    def test_hash_von_bytes_berechnen(self):
        """Hash von Bytes muss dem erwarteten SHA-256 entsprechen."""
        daten = b"Testdaten fuer Hash"
        erwartet = hashlib.sha256(daten).hexdigest()
        ergebnis = compute_hash_from_bytes(daten)
        assert ergebnis == erwartet

    def test_hash_ist_deterministisch(self, erstelle_textdatei):
        """Gleicher Inhalt muss immer den gleichen Hash ergeben."""
        inhalt = "Deterministischer Test"
        datei = erstelle_textdatei("test.txt", inhalt)
        hash1 = compute_hash(datei)
        hash2 = compute_hash(datei)
        assert hash1 == hash2

    def test_unterschiedlicher_inhalt_verschiedene_hashes(self, erstelle_textdatei):
        """Verschiedener Inhalt muss verschiedene Hashes ergeben."""
        datei1 = erstelle_textdatei("a.txt", "Inhalt A")
        datei2 = erstelle_textdatei("b.txt", "Inhalt B")
        assert compute_hash(datei1) != compute_hash(datei2)

    def test_hash_hat_64_zeichen(self, erstelle_textdatei):
        """SHA-256 Hash muss immer 64 Hex-Zeichen lang sein."""
        datei = erstelle_textdatei("test.txt", "Irgendein Inhalt")
        ergebnis = compute_hash(datei)
        assert len(ergebnis) == 64
        assert all(c in "0123456789abcdef" for c in ergebnis)

    def test_hash_leere_datei(self, erstelle_textdatei):
        """Auch eine leere Datei muss einen gueltigen Hash liefern."""
        datei = erstelle_textdatei("leer.txt", "")
        ergebnis = compute_hash(datei)
        erwartet = hashlib.sha256(b"").hexdigest()
        assert ergebnis == erwartet

    def test_hash_grosse_datei(self, erstelle_binaerdatei):
        """Grosse Dateien muessen korrekt chunk-basiert gehasht werden."""
        # 256 KB - groesser als HASH_CHUNK_SIZE (65536)
        daten = b"X" * (256 * 1024)
        datei = erstelle_binaerdatei("gross.bin", daten)
        erwartet = hashlib.sha256(daten).hexdigest()
        ergebnis = compute_hash(datei)
        assert ergebnis == erwartet


# ---------------------------------------------------------------------------
# Speicherpfad
# ---------------------------------------------------------------------------

class TestSpeicherpfad:
    """Tests fuer die Pfadberechnung im Hash-Speicher."""

    def test_pfad_zweistufige_struktur(self, storage_dir):
        """Pfad muss dem Schema /ab/cd/abcdef.../ folgen."""
        test_hash = "abcdef1234567890" * 4  # 64 Zeichen
        pfad = get_storage_path(test_hash, storage_dir)
        assert pfad == storage_dir / "ab" / "cd" / test_hash

    def test_pfad_mit_verschiedenen_hashes(self, storage_dir):
        """Verschiedene Hashes muessen verschiedene Pfade ergeben."""
        hash1 = "aa" + "bb" + "c" * 60
        hash2 = "xx" + "yy" + "z" * 60
        pfad1 = get_storage_path(hash1, storage_dir)
        pfad2 = get_storage_path(hash2, storage_dir)
        assert pfad1 != pfad2

    def test_pfad_nutzt_settings_als_standard(self):
        """Ohne expliziten Pfad muss settings.storage_dir genutzt werden."""
        test_hash = "a" * 64
        with patch("backend.app.services.storage.settings") as mock_settings:
            mock_settings.storage_dir = Path("/mock/storage")
            pfad = get_storage_path(test_hash)
            assert pfad == Path("/mock/storage") / "aa" / "aa" / test_hash


# ---------------------------------------------------------------------------
# Datei-Existenz
# ---------------------------------------------------------------------------

class TestDateiExistenz:
    """Tests fuer die Existenzpruefung im Speicher."""

    def test_existiert_nicht_wenn_leer(self, storage_dir):
        """In einem leeren Speicher darf nichts gefunden werden."""
        assert file_exists_in_storage("a" * 64, storage_dir) is False

    def test_existiert_nach_anlegen(self, storage_dir):
        """Nach dem Anlegen des Verzeichnisses muss die Datei gefunden werden."""
        test_hash = "ab" + "cd" + "e" * 60
        pfad = get_storage_path(test_hash, storage_dir)
        pfad.mkdir(parents=True)
        assert file_exists_in_storage(test_hash, storage_dir) is True


# ---------------------------------------------------------------------------
# Datei speichern
# ---------------------------------------------------------------------------

class TestDateiSpeichern:
    """Tests fuer das Speichern von Dateien im Hash-Speicher."""

    def test_textdatei_speichern(self, erstelle_textdatei, storage_dir):
        """Eine Textdatei muss korrekt im Hash-Speicher landen."""
        datei = erstelle_textdatei("buch.txt", "Buchinhalt")
        with patch("backend.app.services.storage.settings") as mock:
            mock.storage_dir = storage_dir
            file_hash, ziel_pfad = store_file(datei, storage_dir=storage_dir)

        assert len(file_hash) == 64
        assert ziel_pfad.exists()
        assert (ziel_pfad / "buch.txt").exists()
        # Inhalt pruefen
        gespeichert = (ziel_pfad / "buch.txt").read_text(encoding="utf-8")
        assert gespeichert == "Buchinhalt"

    def test_speichern_mit_vorberechnetem_hash(self, erstelle_textdatei, storage_dir):
        """Ein vorberechneter Hash muss direkt verwendet werden."""
        datei = erstelle_textdatei("buch.txt", "Inhalt")
        bekannter_hash = hashlib.sha256(b"Inhalt").hexdigest()
        with patch("backend.app.services.storage.settings") as mock:
            mock.storage_dir = storage_dir
            file_hash, _ = store_file(datei, file_hash=bekannter_hash, storage_dir=storage_dir)
        assert file_hash == bekannter_hash

    def test_duplikat_wirft_fehler(self, erstelle_textdatei, storage_dir):
        """Ein zweites Speichern desselben Hashs muss FileExistsError ausloesen."""
        datei = erstelle_textdatei("buch.txt", "Duplikat-Test")
        with patch("backend.app.services.storage.settings") as mock:
            mock.storage_dir = storage_dir
            store_file(datei, storage_dir=storage_dir)
            with pytest.raises(FileExistsError):
                store_file(datei, storage_dir=storage_dir)

    def test_nicht_unterstuetztes_format(self, erstelle_textdatei, storage_dir):
        """Ein nicht unterstuetztes Format muss ValueError ausloesen."""
        datei = erstelle_textdatei("bild.jpg", "Kein Buch")
        with patch("backend.app.services.storage.settings") as mock:
            mock.storage_dir = storage_dir
            with pytest.raises(ValueError, match="nicht unterstuetzt"):
                store_file(datei, storage_dir=storage_dir)

    def test_fehlende_datei_wirft_fehler(self, tmp_path, storage_dir):
        """Eine nicht existierende Quelldatei muss FileNotFoundError ausloesen."""
        with patch("backend.app.services.storage.settings") as mock:
            mock.storage_dir = storage_dir
            with pytest.raises(FileNotFoundError):
                store_file(tmp_path / "gibt_es_nicht.txt", storage_dir=storage_dir)

    def test_unterstuetzte_formate(self):
        """Alle erwarteten Formate muessen in SUPPORTED_FORMATS enthalten sein."""
        erwartete = {".pdf", ".epub", ".mobi", ".txt", ".md"}
        assert SUPPORTED_FORMATS == erwartete


# ---------------------------------------------------------------------------
# Duplikaterkennung
# ---------------------------------------------------------------------------

class TestDuplikaterkennung:
    """Tests fuer die Duplikat-Pruefung ueber mehrere Speicherorte."""

    def test_kein_duplikat_bei_leerem_speicher(self, storage_dir, external_dir):
        """In leeren Speichern darf kein Duplikat gefunden werden."""
        with patch("backend.app.services.storage.settings") as mock:
            mock.storage_dir = storage_dir
            mock.external_dir = external_dir
            ergebnis = check_duplicate("a" * 64)
        assert ergebnis is None

    def test_duplikat_im_hauptspeicher(self, storage_dir, external_dir):
        """Ein Duplikat im Hauptspeicher muss als solches erkannt werden."""
        test_hash = "ab" + "cd" + "e" * 60
        pfad = get_storage_path(test_hash, storage_dir)
        pfad.mkdir(parents=True)

        with patch("backend.app.services.storage.settings") as mock:
            mock.storage_dir = storage_dir
            mock.external_dir = external_dir
            ergebnis = check_duplicate(test_hash)

        assert ergebnis is not None
        assert ergebnis["gefunden_in"] == "hauptspeicher"

    def test_duplikat_im_externen_speicher(self, storage_dir, external_dir):
        """Ein Duplikat im externen Speicher muss erkannt werden."""
        test_hash = "ef" + "gh" + "i" * 60
        pfad = get_storage_path(test_hash, external_dir)
        pfad.mkdir(parents=True)

        with patch("backend.app.services.storage.settings") as mock:
            mock.storage_dir = storage_dir
            mock.external_dir = external_dir
            ergebnis = check_duplicate(test_hash)

        assert ergebnis is not None
        assert ergebnis["gefunden_in"] == "extern"


# ---------------------------------------------------------------------------
# Sidecar-Dateien (Metadaten, Volltext, Cover)
# ---------------------------------------------------------------------------

class TestSidecarDateien:
    """Tests fuer Sidecar-Dateien neben den Originaldateien."""

    def test_metadaten_speichern_und_laden(self, storage_dir):
        """Metadaten muessen als JSON gespeichert und wieder geladen werden."""
        test_hash = "ab" + "cd" + "e" * 60
        pfad = get_storage_path(test_hash, storage_dir)
        pfad.mkdir(parents=True)

        metadaten = {
            "titel": "Testbuch",
            "autor": "Testautor",
            "seiten": 42,
        }
        save_metadata(test_hash, metadaten, storage_dir)
        geladen = load_metadata(test_hash, storage_dir)

        assert geladen is not None
        assert geladen["titel"] == "Testbuch"
        assert geladen["autor"] == "Testautor"
        assert geladen["seiten"] == 42

    def test_metadaten_nicht_vorhanden(self, storage_dir):
        """Fehlende Metadaten muessen None zurueckgeben."""
        ergebnis = load_metadata("x" * 64, storage_dir)
        assert ergebnis is None

    def test_metadaten_mit_umlauten(self, storage_dir):
        """Umlaute muessen korrekt gespeichert und gelesen werden."""
        test_hash = "ab" + "cd" + "e" * 60
        pfad = get_storage_path(test_hash, storage_dir)
        pfad.mkdir(parents=True)

        metadaten = {"titel": "Buecher ueber Aerzte"}
        save_metadata(test_hash, metadaten, storage_dir)
        geladen = load_metadata(test_hash, storage_dir)

        assert geladen is not None
        assert geladen["titel"] == "Buecher ueber Aerzte"

    def test_volltext_speichern_und_laden(self, storage_dir):
        """Volltext muss korrekt gespeichert und geladen werden."""
        test_hash = "ab" + "cd" + "e" * 60
        pfad = get_storage_path(test_hash, storage_dir)
        pfad.mkdir(parents=True)

        text = "Dies ist der vollstaendige Text des Buches."
        save_fulltext(test_hash, text, storage_dir)
        geladen = load_fulltext(test_hash, storage_dir)

        assert geladen == text

    def test_volltext_nicht_vorhanden(self, storage_dir):
        """Fehlender Volltext muss None zurueckgeben."""
        ergebnis = load_fulltext("x" * 64, storage_dir)
        assert ergebnis is None

    def test_cover_speichern(self, storage_dir):
        """Cover-Daten muessen korrekt als Binaerdatei gespeichert werden."""
        test_hash = "ab" + "cd" + "e" * 60
        pfad = get_storage_path(test_hash, storage_dir)
        pfad.mkdir(parents=True)

        bilddaten = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # Fake-JPEG-Header
        cover_pfad = save_cover(test_hash, bilddaten, storage_dir)

        assert cover_pfad.exists()
        assert cover_pfad.name == "cover.jpg"
        assert cover_pfad.read_bytes() == bilddaten

    def test_sidecar_pfad_korrekt(self, storage_dir):
        """Sidecar-Pfade muessen im Hash-Verzeichnis liegen."""
        test_hash = "ab" + "cd" + "e" * 60
        pfad = get_sidecar_path(test_hash, "metadata.json", storage_dir)
        assert pfad.parent == get_storage_path(test_hash, storage_dir)
        assert pfad.name == "metadata.json"


# ---------------------------------------------------------------------------
# Originaldatei finden
# ---------------------------------------------------------------------------

class TestOriginaldateiFinden:
    """Tests fuer das Finden der Originaldatei im Hash-Verzeichnis."""

    def test_originaldatei_finden(self, storage_dir):
        """Die Originaldatei muss gefunden werden (Sidecars ausgeschlossen)."""
        test_hash = "ab" + "cd" + "e" * 60
        pfad = get_storage_path(test_hash, storage_dir)
        pfad.mkdir(parents=True)

        # Originaldatei und Sidecars anlegen
        (pfad / "mein_buch.pdf").write_bytes(b"PDF-Inhalt")
        (pfad / "metadata.json").write_text("{}")
        (pfad / "fulltext.txt").write_text("Text")

        ergebnis = get_original_file(test_hash, storage_dir)
        assert ergebnis is not None
        assert ergebnis.name == "mein_buch.pdf"

    def test_keine_originaldatei_bei_leerem_verzeichnis(self, storage_dir):
        """Bei nicht existierendem Hash-Verzeichnis muss None kommen."""
        ergebnis = get_original_file("x" * 64, storage_dir)
        assert ergebnis is None

    def test_nur_sidecars_keine_originaldatei(self, storage_dir):
        """Wenn nur Sidecars vorhanden sind, muss None kommen."""
        test_hash = "ab" + "cd" + "e" * 60
        pfad = get_storage_path(test_hash, storage_dir)
        pfad.mkdir(parents=True)

        (pfad / "metadata.json").write_text("{}")
        (pfad / "fulltext.txt").write_text("Text")
        (pfad / "cover.jpg").write_bytes(b"\xff")

        ergebnis = get_original_file(test_hash, storage_dir)
        assert ergebnis is None


# ---------------------------------------------------------------------------
# Datei loeschen
# ---------------------------------------------------------------------------

class TestDateiLoeschen:
    """Tests fuer das Loeschen von Dateien aus dem Speicher."""

    def test_datei_loeschen(self, erstelle_textdatei, storage_dir):
        """Eine gespeicherte Datei muss vollstaendig geloescht werden koennen."""
        datei = erstelle_textdatei("buch.txt", "Loeschtest")
        with patch("backend.app.services.storage.settings") as mock:
            mock.storage_dir = storage_dir
            file_hash, ziel = store_file(datei, storage_dir=storage_dir)
            assert ziel.exists()

            erfolg = delete_stored_file(file_hash, storage_dir)
            assert erfolg is True
            assert not ziel.exists()

    def test_nicht_existierende_datei_loeschen(self, storage_dir):
        """Das Loeschen einer nicht vorhandenen Datei muss False ergeben."""
        erfolg = delete_stored_file("x" * 64, storage_dir)
        assert erfolg is False


# ---------------------------------------------------------------------------
# Speicher-Statistiken
# ---------------------------------------------------------------------------

class TestSpeicherStatistiken:
    """Tests fuer die Speicher-Statistiken."""

    def test_statistiken_leerer_speicher(self, storage_dir):
        """Ein leerer Speicher muss 0 Dateien und 0 Bytes melden."""
        stats = get_storage_stats(storage_dir)
        assert stats["anzahl_dateien"] == 0
        assert stats["gesamtgroesse"] == 0

    def test_statistiken_mit_dateien(self, storage_dir):
        """Statistiken muessen die tatsaechliche Dateianzahl und -groesse zeigen."""
        # Einige Testdateien anlegen
        unterverzeichnis = storage_dir / "ab" / "cd"
        unterverzeichnis.mkdir(parents=True)
        (unterverzeichnis / "datei1.txt").write_text("Hallo")
        (unterverzeichnis / "datei2.txt").write_text("Welt!")

        stats = get_storage_stats(storage_dir)
        assert stats["anzahl_dateien"] == 2
        assert stats["gesamtgroesse"] > 0
        assert "gesamtgroesse_mb" in stats

    def test_statistiken_nicht_existierender_speicher(self, tmp_path):
        """Ein nicht existierender Speicherpfad muss 0 ergeben."""
        stats = get_storage_stats(tmp_path / "gibt_es_nicht")
        assert stats["anzahl_dateien"] == 0
        assert stats["gesamtgroesse"] == 0
