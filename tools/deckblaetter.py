"""Falsche und fehlende Umschläge von EPUB-Büchern berichtigen (im Container: python - [los] [schnell]).

Ersetzt wird nur, was sicher falsch ist: kein Umschlag, kein JPEG, zu breit oder zu klein, oder das gemerkte Bild ist eines aus
dem Inneren des Buchs, obwohl das Buch einen Umschlag nennt. Das alte Bild bleibt unter `_vorher` neben den Umschlägen. Das Buch
selbst ändert sich nicht (updated_at bleibt, der Fundus bettet nichts neu ein)."""

import asyncio
import hashlib
import io
import shutil
import sys
import zipfile

from PIL import Image

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services import deckblatt
from backend.app.services.storage import get_original_file, get_sidecar_path, save_cover

LOS = "los" in sys.argv
SCHNELL = "schnell" in sys.argv        # nur, was schon dem Bild anzusehen ist; sonst auch jedes Buch auf Bilder aus dem Inneren


def verdacht(daten: bytes | None) -> str:
    if not daten:
        return "fehlt"
    try:
        b = Image.open(io.BytesIO(daten))
    except Exception:
        return "unlesbar"
    return "kein JPEG" if b.format != "JPEG" else "" if deckblatt.taugt(daten) else "Form"


def aus_dem_inneren(datei, daten: bytes) -> bool:
    summe = hashlib.sha1(daten).digest()
    with zipfile.ZipFile(datei) as z:
        genannt = {hashlib.sha1(b).digest() for b in deckblatt._genannt(z) if deckblatt.taugt(b)}
        return bool(genannt) and summe not in genannt and any(
            hashlib.sha1(z.read(n)).digest() == summe for n in z.namelist() if n.lower().endswith(deckblatt.BILD))


async def lauf() -> None:
    await db.connect()
    gruende: dict[str, int] = {}
    for b in await db.fetch_all("SELECT id, hash, title FROM books WHERE file_format = 'epub' ORDER BY id"):
        pfad = get_sidecar_path(b["hash"], "cover.jpg")
        alt = pfad.read_bytes() if pfad.exists() else None
        grund = verdacht(alt)
        if SCHNELL and not grund:
            continue
        datei = get_original_file(b["hash"])
        if datei is None:
            gruende["noch nicht kopiert"] = gruende.get("noch nicht kopiert", 0) + 1
            continue
        try:
            grund = grund or ("Bild aus dem Inneren" if aus_dem_inneren(datei, alt) else "")
        except (zipfile.BadZipFile, KeyError, NotImplementedError):
            pass
        if not grund:
            continue
        neu = deckblatt.von_datei(datei, "epub")
        if not neu:
            grund += ", kein besseres"
        elif LOS:
            if alt:
                vorher = settings.umschlaege_dir / "_vorher" / f"{b['id']}.jpg"
                vorher.parent.mkdir(exist_ok=True)
                shutil.copyfile(pfad, vorher)
            save_cover(b["hash"], neu)
            await db.execute("UPDATE books SET cover_path = 'cover.jpg' WHERE id = ?", (b["id"],))
            await db.commit()
        gruende[grund] = gruende.get(grund, 0) + 1
        print(b["id"], grund, b["title"][:50], flush=True)
    print("ersetzt" if LOS else "Vorschau", gruende)
    await db.disconnect()


asyncio.run(lauf())
