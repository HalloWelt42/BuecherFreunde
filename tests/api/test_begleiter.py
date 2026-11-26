"""BF-46: Begleiter neben dem Buch (Codestellen, Seiten, Angaben) gelten nie als Original."""

from pathlib import Path

from backend.app.ablage import antwort
from backend.app.codestellen import dienst
from backend.app.services import seiten, storage


def test_jeder_begleiter_steht_in_der_einen_liste():
    for name in (dienst.BEGLEITER, seiten.BEGLEITER, "metadata.json", "fulltext.txt", "cover.jpg"):
        assert name in storage.BEGLEITER


def test_ordner_nur_mit_begleitern_hat_kein_original_auf_dem_geraet(tmp_path: Path, monkeypatch):
    ordner = tmp_path / "ab" / "cd" / "abcd"
    ordner.mkdir(parents=True)
    for name in storage.BEGLEITER:
        (ordner / name).write_text("{}")
    monkeypatch.setattr(antwort, "get_storage_path", lambda h: ordner)
    monkeypatch.setattr(antwort.settings, "zwischen_dir", tmp_path / "zwischen")
    assert antwort._auf_dem_geraet("abcd") is None
    (ordner / "buch.pdf").write_bytes(b"%PDF-1.4")
    assert antwort._auf_dem_geraet("abcd") == ordner / "buch.pdf"
    assert storage.get_original_file("abcd", storage_dir=tmp_path) == ordner / "buch.pdf"
