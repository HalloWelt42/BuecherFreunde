"""BF-17: Ein EPUB, das beim Aufnehmen nicht lesbar war (sein Verzeichnis nennt ein Bild, das fehlt), bekommt beim Ergänzen
"Volltext" Text und Seitenzahl, über denselben Leser wie beim Aufnehmen."""

import asyncio
import zipfile

from backend.app.core.config import settings
from backend.app.services.storage import get_storage_path, load_fulltext
from tests.api.conftest import buch_erstellen

KAPITEL = ("<html xmlns='http://www.w3.org/1999/xhtml'><body><h1>Kapitel {n}</h1><p>" + "Ein Satz über den Nebel in der Stadt. " * 40
           + "</p></body></html>")


def epub_mit_luecke(pfad) -> None:
    opf = ('<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">probe</dc:identifier><dc:title>Nebel</dc:title>'
           '<dc:language>de</dc:language></metadata><manifest>'
           '<item id="k1" href="k1.xhtml" media-type="application/xhtml+xml"/><item id="k2" href="k2.xhtml" media-type="application/xhtml+xml"/>'
           '<item id="bild" href="Images/fehlt.jpg" media-type="image/jpeg"/></manifest>'
           '<spine><itemref idref="k1"/><itemref idref="k2"/></spine></package>')
    container = ('<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                 '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    with zipfile.ZipFile(pfad, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        for n in (1, 2):
            z.writestr(f"OEBPS/k{n}.xhtml", KAPITEL.format(n=n))


async def test_volltext_und_seiten_nachholen(client, test_db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "speicher")
    ordner = get_storage_path("nebelhash")
    ordner.mkdir(parents=True)
    epub_mit_luecke(ordner / "Nebel.epub")
    buch = await buch_erstellen(test_db, hash="nebelhash", file_format="epub", file_name="Nebel.epub", page_count=0)
    vorschau = (await client.get("/api/books/rescan/vorschau", params={"typen": "volltext"})).json()
    assert vorschau["typen"]["volltext"] == 1
    assert (await client.post("/api/books/rescan", params={"typen": "volltext"})).json()["gestartet"]
    for _ in range(300):
        stand = (await client.get("/api/books/rescan/status")).json()
        if not stand["laeuft"]:
            break
        await asyncio.sleep(0.1)
    assert stand["volltext_extrahiert"] == 1, stand
    z = await test_db.fetch_one("SELECT page_count FROM books WHERE id = ?", (buch,))
    assert z["page_count"] == 2 and "Nebel in der Stadt" in load_fulltext("nebelhash")
    assert (await client.get("/api/books/rescan/vorschau", params={"typen": "volltext"})).json()["typen"].get("volltext", 0) == 0
