"""Hilfen für die Tests der Familie (BF-78): eine erfundene Familie mit Profilen, Büchern, Freigaben und je Profil seinem
Schlüssel. Alle Namen und Titel sind erfunden."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from httpx import AsyncClient

from backend.app.core.database import Database
from backend.app.familie import pin
from tests.api.conftest import buch_erstellen, kategorie_erstellen, verwaltung

GERAET = "probe-geraet-0001"
BILDER = ["sonne", "katze", "mond"]
PIN_BERT = "4711"


@dataclass
class Familie:
    ids: dict[str, str] = field(default_factory=dict)          # Name -> Profil
    kopf: dict[str, dict[str, str]] = field(default_factory=dict)   # Name -> {"X-Profil": Schlüssel}
    buch: dict[str, int] = field(default_factory=dict)         # Kurzname -> Buch
    kategorie: dict[str, int] = field(default_factory=dict)


async def anlegen(client: AsyncClient, kopf: dict | None = None, **angaben) -> dict:
    r = await client.post("/api/familie/profile", json=angaben, headers=kopf or {})
    assert r.status_code == 201, r.text
    return r.json()


async def waehlen(client: AsyncClient, profil_id: str, **geheim) -> dict[str, str]:
    r = await client.post("/api/familie/wahl", json={"profil_id": profil_id, **geheim})
    assert r.status_code == 200, r.text
    client.cookies.clear()                                       # jede Anfrage nennt ihr Profil selbst
    return {"X-Profil": r.json()["schluessel"]}


async def familie_anlegen(client: AsyncClient, test_db: Database) -> Familie:
    """Ada (Verwaltung), Bert (Erwachsen, PIN), Clara (Kind, Vorlesen, Bild-PIN), Dora (Kind, Schule), Emil (Kind, Jugend).

    Bücher: "Mondfahrt" für Clara freigegeben, "Sternenwald" in der freigegebenen Kategorie Märchen (genauer: in ihrer
    Unterkategorie Feen), "Zebrageheimnis" privat für Bert, "Steuerkram" für niemanden freigegeben."""
    pin.versuche.leeren()
    f = Familie()
    f.ids["ada"] = await verwaltung(test_db)
    f.buch["mond"] = await buch_erstellen(test_db, hash="fam01", title="Mondfahrt mit Paula", author="Rike Fantasia")
    f.buch["stern"] = await buch_erstellen(test_db, hash="fam02", title="Sternenwald und Funkelfee", author="Rike Fantasia")
    f.buch["zebra"] = await buch_erstellen(test_db, hash="fam03", title="Zebrageheimnis", author="Quirin Verborgen",
                                           fts_content="Zebrageheimnis bleibt unter uns")
    f.buch["steuer"] = await buch_erstellen(test_db, hash="fam04", title="Steuerkram ganz trocken", author="Otto Amtlich",
                                            fts_content="Steuerkram und Formulare")
    f.kategorie["maerchen"] = await kategorie_erstellen(test_db, name="Märchen")
    f.kategorie["feen"] = await kategorie_erstellen(test_db, name="Feen")
    await test_db.execute("UPDATE categories SET parent_id = ? WHERE id = ?", (f.kategorie["maerchen"], f.kategorie["feen"]))
    await test_db.execute("INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)", (f.buch["stern"], f.kategorie["feen"]))
    await test_db.commit()

    f.ids["bert"] = (await anlegen(client, name="Bert", rolle="erwachsen"))["id"]
    f.kopf["ada"] = await waehlen(client, f.ids["ada"])
    ada = f.kopf["ada"]
    f.ids["clara"] = (await anlegen(client, ada, name="Clara", rolle="kind", stufe="vorlesen", geburtsjahr=date.today().year - 5))["id"]
    f.ids["dora"] = (await anlegen(client, ada, name="Dora", rolle="kind", stufe="schule"))["id"]
    f.ids["emil"] = (await anlegen(client, ada, name="Emil", rolle="kind", stufe="jugend"))["id"]
    assert (await client.put(f"/api/familie/profile/{f.ids['bert']}/pin", json={"pin": PIN_BERT}, headers=ada)).status_code == 200
    assert (await client.put(f"/api/familie/profile/{f.ids['clara']}/pin", json={"bild_pin": BILDER}, headers=ada)).status_code == 200

    f.kopf["bert"] = await waehlen(client, f.ids["bert"], pin=PIN_BERT)
    f.kopf["clara"] = await waehlen(client, f.ids["clara"], bild_pin=BILDER)
    f.kopf["dora"] = await waehlen(client, f.ids["dora"])
    f.kopf["emil"] = await waehlen(client, f.ids["emil"])

    assert (await client.put(f"/api/books/{f.buch['zebra']}/privat", json={"privat": True}, headers=f.kopf["bert"])).status_code == 200
    for kind in ("clara", "dora", "emil"):
        await freigeben(client, ada, f.ids[kind], "buch", [f.buch["mond"]])
        await freigeben(client, ada, f.ids[kind], "kategorie", [f.kategorie["maerchen"]])
    return f


async def freigeben(client: AsyncClient, kopf: dict, kind: str, art: str, ziele: list[int]) -> dict:
    r = await client.post(f"/api/familie/profile/{kind}/freigaben", json={"art": art, "ziel_ids": ziele}, headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()
