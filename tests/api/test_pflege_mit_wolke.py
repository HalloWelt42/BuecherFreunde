"""Bibliothek ergänzen und Dateien prüfen, wenn die Originale in der Kellerwolke liegen: gezählt wird ohne zu laden, und von hier
wird dort nichts verschoben."""

import pytest

from backend.app.ablage.wolke import Wolke, WolkeFehler
from backend.app.core.database import db
from backend.app.services import rescan_service
from backend.app.services.storage import save_fulltext
from tests.api.test_annahme_api import hochladen, pdf, warten


async def buecher(client, kopf) -> list[int]:
    nummern = []
    for wort in ("Erstes", "Zweites"):
        z = await hochladen(client, kopf, f"{wort}.pdf", pdf(f"{wort} Buch mit genug Text, damit er als Volltext gilt", 4))
        nummern.append((await warten(client, kopf, z["id"]))["buch_id"])
    return nummern


@pytest.mark.asyncio
async def test_volltext_zaehlt_nur_fehlende(annahme_dienst, auth_headers):
    _, zweites = await buecher(annahme_dienst, auth_headers)
    z = await db.fetch_one("SELECT hash FROM books WHERE id = ?", (zweites,))
    save_fulltext(z["hash"], "kurz")
    v = await rescan_service.vorschau(["volltext", "isbn"])
    assert v == {"gesamt": 2, "typen": {"isbn": 2, "volltext": 1}}


@pytest.mark.asyncio
async def test_dateien_pruefen_fragt_nur_die_kellerwolke(annahme_dienst, auth_headers, monkeypatch):
    erstes, zweites = await buecher(annahme_dienst, auth_headers)
    hashes = {b["id"]: b["hash"] for b in await db.fetch_all("SELECT id, hash FROM books")}
    await db.execute("INSERT INTO ablage_datei(hash, knoten, name) VALUES (?, 'k1', 'a'), (?, 'k2', 'b')", (hashes[erstes], hashes[zweites]))
    await db.commit()

    async def knoten(_s, kennung):
        if kennung == "k2":
            raise WolkeFehler("gibt es nicht", 404)
        return {"sha256": hashes[erstes]}

    monkeypatch.setattr(Wolke, "bereit", property(lambda _s: True))
    monkeypatch.setattr(Wolke, "knoten", knoten)
    bericht = (await annahme_dienst.post("/api/wartung/defekte-pruefen", headers=auth_headers)).json()
    assert [(e["id"], e["grund"]) for e in bericht["eintraege"]] == [(zweites, "fehlt in der Kellerwolke")]
    antwort = await annahme_dienst.post("/api/wartung/defekte-pruefen", params={"verschieben": True}, headers=auth_headers)
    assert antwort.status_code == 409
    assert len(await db.fetch_all("SELECT id FROM books")) == 2
