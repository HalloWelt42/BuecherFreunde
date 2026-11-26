"""Eine nachgebaute Kellerwolke für Tests (BF-80, BF-81, BF-82): Ordner, Dateien, fortsetzbares Hochladen, Begleiter mit Rolle
und Namen nach den Regeln der Kellerwolke (Stamm der Hauptdatei und Zusatz, sonst der volle Name davor, sonst 409), Felder,
neue Versionen mit Stand, Suche nach Prüfsumme und ein Papierkorb. Alles liegt im Speicher, nichts geht ins Netz; die echte Kellerwolke wird nie gefragt."""

from __future__ import annotations

import hashlib
import itertools
import posixpath
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from backend.app.ablage import originale
from backend.app.ablage.wolke import Wolke, WolkeFehler
from backend.app.core.config import settings
from backend.app.core.database import db

ZUSATZ = re.compile(r"^(\.[a-z0-9][a-z0-9_-]{0,19}){1,3}$")
ROLLE = re.compile(r"^[a-z][a-z_]{0,39}$")


class Kellerwolke:
    def __init__(self) -> None:
        self.knoten: dict[str, dict] = {}
        self.inhalt: dict[str, bytes] = {}
        self.uploads: dict[str, dict] = {}
        self.geschrieben: list[tuple[str, int]] = []     # je Schreiben eines Begleiters: Rolle und Größe in Byte
        self._nr = itertools.count(1)
        self.wurzel = self._neu("ordner", "Apps", None)

    # -- Speicher ------------------------------------------------------------------------------------------------------
    def _neu(self, typ: str, name: str, eltern: str | None, inhalt: bytes | None = None, **mehr) -> str:
        k = f"k{next(self._nr)}"
        self.knoten[k] = {"id": k, "typ": typ, "name": name, "parent_id": eltern, "haupt_id": None, "rolle": None, "geloescht": False, **mehr}
        if inhalt is not None:
            self.inhalt[k] = inhalt
        return k

    def pfad(self, k: str) -> str:
        teile, z = [], self.knoten[k]
        while z is not None:
            teile.append(z["name"])
            z = self.knoten.get(z["parent_id"]) if z["parent_id"] else None
        return "/".join(reversed(teile))

    def ansicht(self, k: str) -> dict:
        z = self.knoten[k]
        aus = {key: z[key] for key in ("id", "typ", "name", "parent_id", "haupt_id", "rolle")} | {"pfad": self.pfad(k), "etag": f"e{z.get('version', 1)}"}
        if z.get("felder"):
            aus["felder"] = dict(z["felder"])
        if k in self.inhalt:
            aus |= {"groesse": len(self.inhalt[k]), "sha256": hashlib.sha256(self.inhalt[k]).hexdigest()}
        return aus

    def lebend(self, eltern: str) -> list[str]:
        return [k for k, z in self.knoten.items() if z["parent_id"] == eltern and not z["geloescht"]]

    def finden(self, eltern: str, name: str) -> str | None:
        return next((k for k in self.lebend(eltern) if self.knoten[k]["name"] == name), None)

    def ordner_von(self, pfad: str) -> str:
        teile = pfad.split("/")
        assert teile[0] == "Apps"
        k = self.wurzel
        for t in teile[1:]:
            k = self.finden(k, t) or self._neu("ordner", t, k)
        return k

    def datei(self, pfad: str, inhalt: bytes) -> str:
        """Eine Datei an einen Ort legen (wie der Nutzer selbst)."""
        ordner, name = posixpath.split(pfad)
        return self._neu("datei", name, self.ordner_von(ordner), inhalt)

    def begleiter(self, haupt: str) -> list[dict]:
        return [self.ansicht(k) for k, z in self.knoten.items() if z["haupt_id"] == haupt and not z["geloescht"]]

    def im_papierkorb(self) -> list[str]:
        return [z["name"] for z in self.knoten.values() if z["geloescht"]]

    # -- Wege der Kellerwolke ----------------------------------------------------------------------------------------------
    def _begleiter_name(self, haupt: str, zusatz: str) -> str:
        if not ZUSATZ.match(zusatz) or len(zusatz) > 40:
            raise WolkeFehler(f"Zusatz {zusatz} ungültig", 422)
        h = self.knoten[haupt]
        stamm = h["name"].rpartition(".")[0] or h["name"]
        for name in (f"{stamm}{zusatz}", f"{h['name']}{zusatz}"):
            if not self.finden(h["parent_id"], name):
                return name
        raise WolkeFehler(f"Neben {h['name']} ist kein Name frei", 409)

    def _rolle_frei(self, haupt: str, rolle: str) -> None:
        if not ROLLE.match(rolle):
            raise WolkeFehler(f"Rolle {rolle} ungültig", 422)
        if any(z["haupt_id"] == haupt and z["rolle"] == rolle and not z["geloescht"] for z in self.knoten.values()):
            raise WolkeFehler("Den Begleiter gibt es schon", 412)

    def einhaengen(self, monkeypatch) -> None:
        w = self

        async def ordner(_s, pfad):
            return w.ansicht(w.ordner_von(pfad))

        async def kinder(_s, ordner):
            for k in w.lebend(ordner):
                yield w.ansicht(k)

        async def knoten(_s, k):
            if k not in w.knoten or w.knoten[k]["geloescht"]:
                raise WolkeFehler("Nicht gefunden", 404)
            return w.ansicht(k)

        async def datei_schreiben(_s, pfad, quelle: Path):
            ordner_, name = posixpath.split(pfad)
            o = w.ordner_von(ordner_)
            if w.finden(o, name):
                raise WolkeFehler("Name vergeben", 409)
            return w.ansicht(w._neu("datei", name, o, quelle.read_bytes()))

        async def umziehen(_s, k, ordner_, name):
            if (da := w.finden(ordner_, name)) and da != k:
                raise WolkeFehler("Name vergeben", 409)
            stamm_alt = w.knoten[k]["name"].rpartition(".")[0]
            w.knoten[k] |= {"parent_id": ordner_, "name": name}
            for b in w.knoten.values():                  # die Gruppe zieht mit, Begleiter folgen dem neuen Namen
                if b["haupt_id"] == k and not b["geloescht"]:
                    b["parent_id"] = ordner_
                    if stamm_alt and b["name"].startswith(stamm_alt + "."):
                        b["name"] = name.rpartition(".")[0] + b["name"][len(stamm_alt):]
            return w.ansicht(k)

        async def nichts(*_a, **_b):
            return {}

        async def felder(_s, k, felder_):
            w.knoten[k].setdefault("felder", {}).update(felder_)

        async def begleiter_lesen(_s, haupt):
            return w.begleiter(haupt)

        async def inhalt(_s, k):
            if k not in w.inhalt or w.knoten[k]["geloescht"]:
                raise WolkeFehler("Die Datei fehlt in der Kellerwolke (404)", 404)
            return w.inhalt[k]

        async def inhalt_ersetzen(_s, k, quelle: Path, etag):
            if etag != w.ansicht(k)["etag"]:
                raise WolkeFehler("Die Datei hat sich geändert", 412)
            w.inhalt[k] = quelle.read_bytes()
            w.knoten[k]["version"] = w.knoten[k].get("version", 1) + 1
            return w.ansicht(k)

        async def gibt_es(_s, sha256):
            return [w.ansicht(k) for k, z in w.knoten.items() if not z["geloescht"] and k in w.inhalt
                    and hashlib.sha256(w.inhalt[k]).hexdigest() == sha256]

        async def begleiter_setzen(_s, haupt, rolle, zusatz, inhalt, _art):
            if not ROLLE.match(rolle):
                raise WolkeFehler(f"Rolle {rolle} ungültig", 422)
            w.geschrieben.append((rolle, len(inhalt)))
            alt = next((b for b in w.begleiter(haupt) if b["rolle"] == rolle), None)
            if alt:
                w.inhalt[alt["id"]] = inhalt
                w.knoten[alt["id"]]["version"] = w.knoten[alt["id"]].get("version", 1) + 1
                return alt["id"]
            k = w._neu("datei", w._begleiter_name(haupt, zusatz), w.knoten[haupt]["parent_id"], inhalt)
            w.knoten[k] |= {"haupt_id": haupt, "rolle": rolle}
            return k

        async def auszug(_s, haupt, inhalt):
            return await begleiter_setzen(_s, haupt, "auszug", ".auszug.zip", inhalt, "application/zip")

        async def begleiter_anhaengen(_s, haupt, rolle, k, zusatz):
            w._rolle_frei(haupt, rolle)
            name = w._begleiter_name(haupt, zusatz)
            w.knoten[k] |= {"parent_id": w.knoten[haupt]["parent_id"], "name": name, "haupt_id": haupt, "rolle": rolle}
            return w.ansicht(k)

        async def begleiter_schreiben(_s, haupt, rolle, zusatz, quelle: Path):
            w._rolle_frei(haupt, rolle)
            k = w._neu("datei", w._begleiter_name(haupt, zusatz), w.knoten[haupt]["parent_id"], quelle.read_bytes(), haupt_id=None)
            w.knoten[k] |= {"haupt_id": haupt, "rolle": rolle}
            return w.ansicht(k)

        async def papierkorb(_s, k):
            if k not in w.knoten or w.knoten[k]["geloescht"]:
                return False
            w.knoten[k]["geloescht"] = True
            for b in w.knoten.values():
                if b["haupt_id"] == k:
                    b["geloescht"] = True
            return True

        async def rufe(_s, art, weg, **_w):
            if art == "DELETE" and weg.startswith("/api/v1/ablage/knoten/"):
                if not await papierkorb(_s, weg.rsplit("/", 1)[-1]):
                    raise WolkeFehler("Nicht gefunden", 404)
                return None
            raise AssertionError(f"Die Attrappe kennt {art} {weg} nicht")

        def holen(_s, k, ziel: Path):
            ziel.write_bytes(w.inhalt[k])

        async def upload_anlegen(_s, name, ordner_, groesse, sha256):
            u = f"u{next(w._nr)}"
            w.uploads[u] = {"name": name, "ordner": ordner_, "groesse": groesse, "daten": b""}
            return {"id": u}

        async def upload_stand(_s, u):
            return {"empfangen": len(w.uploads[u]["daten"])}

        async def upload_teil(_s, u, versatz, strom, laenge):
            up = w.uploads[u]
            async for stueck in strom:
                up["daten"] += stueck
            antwort = {"empfangen": len(up["daten"])}
            if len(up["daten"]) >= up["groesse"]:
                antwort["knoten"] = w.ansicht(w._neu("datei", up["name"], up["ordner"], up["daten"]))
            return antwort

        async def upload_abbrechen(_s, u):
            w.uploads.pop(u, None)

        monkeypatch.setattr(Wolke, "bereit", property(lambda _s: True))
        for name, tun in {"ordner": ordner, "kinder": kinder, "knoten": knoten, "datei_schreiben": datei_schreiben, "umziehen": umziehen,
                          "felder": felder, "auszug_schreiben": auszug, "begleiter_anhaengen": begleiter_anhaengen,
                          "begleiter": begleiter_lesen, "inhalt": inhalt, "inhalt_ersetzen": inhalt_ersetzen, "gibt_es": gibt_es,
                          "begleiter_setzen": begleiter_setzen,
                          "begleiter_schreiben": begleiter_schreiben, "papierkorb": papierkorb, "rufe": rufe, "holen": holen,
                          "upload_anlegen": upload_anlegen, "upload_stand": upload_stand, "upload_teil": upload_teil,
                          "upload_abbrechen": upload_abbrechen}.items():
            monkeypatch.setattr(Wolke, name, tun)

        def original_holen(pruefsumme):
            """Wie ablage/originale.py (Name aus `ablage_datei`), aber aus der Attrappe und der Datenbank des Tests, nie aus der
            des Betriebs."""
            with closing(sqlite3.connect(db.db_path)) as v:
                z = v.execute("SELECT knoten, name FROM ablage_datei WHERE hash = ?", (pruefsumme,)).fetchone()
            if z is None or z[0] not in w.inhalt:
                return None
            k = z[0]
            ziel = settings.zwischen_dir / "original" / pruefsumme / Path(z[1]).name
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(w.inhalt[k])
            return ziel

        monkeypatch.setattr(originale, "holen", original_holen)
