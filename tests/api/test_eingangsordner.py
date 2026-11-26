"""Der Eingangsordner in der Kellerwolke (mit nachgebauter Ablage) und auf dem Gerät: Neues wird einmal aufgenommen, Doppel
und Fremdes bleiben liegen."""

import hashlib
import os
import time

import pytest

from backend.app.ablage import originale
from backend.app.ablage.wolke import Wolke
from backend.app.annahme import eingangsordner
from backend.app.core.config import settings
from tests.api.test_annahme_api import pdf, warten


class Ablage:
    """Ein Ordner mit Unterordner, gerade so viel Kellerwolke, wie die Aufnahme braucht."""

    def __init__(self, dateien: dict[str, bytes]) -> None:
        self.inhalt = {f"d{n}": (name, i) for n, (name, i) in enumerate(dateien.items())}
        self.umgezogen: dict[str, str] = {}

    def knoten(self, k: str) -> dict:
        name, i = self.inhalt[k]
        return {"id": k, "typ": "datei", "name": self.umgezogen.get(k, name), "groesse": len(i), "sha256": hashlib.sha256(i).hexdigest(), "pfad": f"Apps/Probe/{name}"}

    async def ordner(self, _selbst, pfad: str) -> dict:
        return {"id": "eingang" if pfad.endswith("Eingangsordner") else "anderer"}

    async def kinder(self, ordner: str):
        lage = {"eingang": [k for k in self.inhalt if k != "d0" and k not in self.umgezogen], "unter": [k for k in self.inhalt if k == "d0" and k not in self.umgezogen]}
        if ordner == "eingang":
            yield {"id": "unter", "typ": "ordner", "name": "Unterordner"}
        for k in lage.get(ordner, []):
            yield self.knoten(k)

    def einhaengen(self, monkeypatch) -> None:
        async def umziehen(_s, k, _ordner, name):
            self.umgezogen[k] = name
            return self.knoten(k)

        async def nichts(*_a, **_b):
            return {}

        async def auszug(*_a, **_b):
            return "begleiter"

        def holen(pruefsumme):
            ziel = settings.zwischen_dir / "probe" / pruefsumme / "Buch.pdf"
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(next(i for _, i in self.inhalt.values() if hashlib.sha256(i).hexdigest() == pruefsumme))
            return ziel

        async def ordner(s, pfad):
            return await self.ordner(s, pfad)

        monkeypatch.setattr(Wolke, "bereit", property(lambda _s: True))
        monkeypatch.setattr(Wolke, "kinder", lambda _s, o: self.kinder(o))
        for name, tun in {"ordner": ordner, "umziehen": umziehen, "felder": nichts, "auszug_schreiben": auszug}.items():
            monkeypatch.setattr(Wolke, name, tun)
        monkeypatch.setattr(originale, "holen", holen)


async def aufnahmen(client, kopf) -> dict[str, dict]:
    return {z["name"]: z for z in (await client.get("/api/annahme", headers=kopf)).json()["eintraege"]}


@pytest.mark.asyncio
async def test_abgelegtes_kommt_in_die_bibliothek(annahme_dienst, auth_headers, monkeypatch):
    buch = pdf("Eingang Probe")
    ablage = Ablage({"Im Unterordner.pdf": buch, "Noch einmal.pdf": buch, "Comic.cbz": b"x"})
    ablage.einhaengen(monkeypatch)
    assert await eingangsordner.aufnehmen() == 3
    assert await eingangsordner.aufnehmen() == 0, "jede Datei nur einmal"
    alle = await aufnahmen(annahme_dienst, auth_headers)
    fertig = [await warten(annahme_dienst, auth_headers, alle[n]["id"]) for n in ("Im Unterordner.pdf", "Noch einmal.pdf")]
    assert sorted(z["stand"] for z in fertig) == ["da", "fertig"], fertig
    assert fertig[0]["buch_id"] == fertig[1]["buch_id"]
    assert alle["Comic.cbz"]["stand"] == "format"
    assert len(ablage.umgezogen) == 1, "nur das aufgenommene Buch zieht um"


@pytest.mark.asyncio
async def test_entferntes_kommt_nicht_wieder(annahme_dienst, auth_headers, monkeypatch):
    Ablage({"Comic.cbz": b"x", "Bild.png": b"y"}).einhaengen(monkeypatch)
    await eingangsordner.aufnehmen()
    nr = (await aufnahmen(annahme_dienst, auth_headers))["Bild.png"]["id"]
    await annahme_dienst.delete(f"/api/annahme/{nr}", headers=auth_headers)
    assert await eingangsordner.aufnehmen() == 0
    assert "Bild.png" not in await aufnahmen(annahme_dienst, auth_headers)


# -- Ohne Kellerwolke: der Eingangsordner auf dem Gerät (BF-18) -----------------------------------------------------------

@pytest.fixture
def geraeteordner(tmp_path, monkeypatch):
    ort = tmp_path / "eingangsordner"
    monkeypatch.setattr(settings, "eingangsordner_dir", ort)
    eingangsordner.einrichten()
    return ort


def ablegen(ort, name: str, inhalt: bytes, alt: bool = True):
    datei = ort / name
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_bytes(inhalt)
    if alt:                                                    # liegt schon eine Weile: fertig geschrieben
        os.utime(datei, (time.time() - 60, time.time() - 60))
    return datei


@pytest.mark.asyncio
async def test_auf_dem_geraet_wie_in_der_kellerwolke(annahme_dienst, auth_headers, geraeteordner):
    buch = pdf("Geräteordner Probe")
    ablegen(geraeteordner, "unter/Im Unterordner.pdf", buch)
    ablegen(geraeteordner, "Noch einmal.pdf", buch)
    ablegen(geraeteordner, "Comic.cbz", b"x")
    assert await eingangsordner.aufnehmen() == 3
    assert await eingangsordner.aufnehmen() == 0, "jede Datei nur einmal"
    alle = await aufnahmen(annahme_dienst, auth_headers)
    assert {z["quelle"] for z in alle.values()} == {"eingangsordner"}
    fertig = [await warten(annahme_dienst, auth_headers, alle[n]["id"]) for n in ("Im Unterordner.pdf", "Noch einmal.pdf")]
    assert sorted(z["stand"] for z in fertig) == ["da", "fertig"], fertig
    assert alle["Comic.cbz"]["stand"] == "format"
    liegt = sorted(p.name for p in geraeteordner.rglob("*") if p.is_file())
    assert len(liegt) == 2 and "Comic.cbz" in liegt, "nur das aufgenommene Buch zieht um, Doppel und Fremdes bleiben"
    stand = (await annahme_dienst.get("/api/annahme/eingangsordner", headers=auth_headers)).json()
    assert stand["bereit"] and stand["pfad"] == str(geraeteordner)
    assert sorted(d["stand"] for d in stand["dateien"]) == ["da", "format"]
    assert await eingangsordner.aufnehmen() == 0


@pytest.mark.asyncio
async def test_frisch_geschriebenes_wartet_und_entferntes_kommt_nicht_wieder(annahme_dienst, auth_headers, geraeteordner):
    datei = ablegen(geraeteordner, "Wird noch geschrieben.pdf", pdf("Frisch"), alt=False)
    assert await eingangsordner.aufnehmen() == 0
    os.utime(datei, (time.time() - 60, time.time() - 60))
    ablegen(geraeteordner, "Bild.png", b"y")
    assert await eingangsordner.aufnehmen() == 2
    nr = (await aufnahmen(annahme_dienst, auth_headers))["Bild.png"]["id"]
    await annahme_dienst.delete(f"/api/annahme/{nr}", headers=auth_headers)
    assert await eingangsordner.aufnehmen() == 0
    assert "Bild.png" not in await aufnahmen(annahme_dienst, auth_headers)
