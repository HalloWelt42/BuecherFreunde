"""Umzug mit Einmalcode (BF-82): vom alten Gerät auf ein neues, direkt über eine gesicherte Verbindung.

Altes Gerät: "Umzug vorbereiten" legt eine frische Sicherung an (auch in der Kellerwolke, wenn eingeschaltet) und gibt einen
Einmalcode aus, gültig `UMZUG_CODE_GILT_MIN` Minuten, für einen Umzug, mit `UMZUG_VERSUCHE` Versuchen; gemerkt ist nur seine
Prüfsumme. Das neue Gerät löst ihn einmal ein (`einloesen`) und bekommt dafür eine Sitzung (`UMZUG_SITZUNG_STUNDEN`), mit der es
die Sicherung und, ohne Kellerwolke, die Originale holt. Mit dem Code gehen die Schlüssel für Kellerwolke und Leitstelle und die
Adressen der Anschlüsse über dieselbe Verbindung; das alte Gerät behält alles und bleibt unverändert, bis man es abschaltet.

Neues Gerät: `verbinden` mit Adresse (nur https, `UMZUG_NUR_HTTPS`) und Code holt das Paket und die Sicherung (geprüft mit ihrer
Prüfsumme), legt die Schlüssel nur in den Schlüsselbund, die Sitzung ebenso (Art `umzug`), spielt die Sicherung ein und wendet
die Anschlüsse an. Liegen die Originale in der Kellerwolke, prüft gleich ein Auftrag, ob sie erreichbar sind; sonst wählt man
"Originale kopieren" (einrichtung/kopieren.py) oder "Ort übernehmen" (nur prüfen, mit Prüfsummen)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from backend.app.ablage import sicherungen as wolke_sicherungen
from backend.app.ablage.antwort import auf_dem_geraet
from backend.app.ablage.wolke import _pruefung, wolke
from backend.app.core import schluessel
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.einrichtung import anschluesse, wiederherstellen, zustand
from backend.app.einrichtung.kopieren import QUELLE, kopieren
from backend.app.einrichtung.modelle import Originalort, Umzugsergebnis, Umzugspaket, Umzugsstand, UmzugVorbereitet
from backend.app.einrichtung.pruefung import pruefung
from backend.app.einrichtung.zustand import Einrichtungsfehler, jetzt
from backend.app.services import sicherung
from backend.app.services.storage import compute_hash

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"          # ohne 0, O, 1, I: gut abzulesen
ZEICHEN = 8
KOPF = "X-Umzug-Sitzung"
WEITERGABE = (schluessel.Art.KELLERWOLKE, schluessel.Art.LEITSTELLE)


def _summe(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", code.upper())


def _zeit(dauer: timedelta) -> str:
    return (datetime.now(UTC) + dauer).strftime("%Y-%m-%dT%H:%M:%SZ")


# -- altes Gerät --------------------------------------------------------------------------------------------------------

async def vorbereiten() -> UmzugVorbereitet:
    """Frische Sicherung und neuer Code; ein früher vorbereiteter Umzug gilt danach nicht mehr."""
    lauf = await asyncio.to_thread(sicherung.sichern, sicherung.Anlass.HAND)
    if lauf.neu:
        await wolke_sicherungen.ablegen(lauf.datei)
    code = "".join(secrets.choice(ALPHABET) for _ in range(ZEICHEN))
    gilt_bis = _zeit(timedelta(minutes=settings.umzug_code_gilt_min))
    await db.execute("INSERT OR REPLACE INTO umzug(id, code, gilt_bis, versuche_frei, sicherung, angelegt_am) VALUES (1, ?, ?, ?, ?, ?)",
                     (_summe(code), gilt_bis, settings.umzug_versuche, lauf.datei.name, jetzt()))
    await db.commit()
    return UmzugVorbereitet(code=f"{code[:4]}-{code[4:]}", gilt_bis=gilt_bis, sicherung=lauf.datei.name, groesse=lauf.datei.stat().st_size)


async def stand() -> Umzugsstand:
    z = await db.fetch_one("SELECT * FROM umzug WHERE id = 1")
    if z is None:
        return Umzugsstand(vorbereitet=False)
    return Umzugsstand(vorbereitet=True, gilt_bis=z["gilt_bis"], versuche_frei=z["versuche_frei"], sicherung=z["sicherung"],
                       eingeloest_am=z["eingeloest_am"], sitzung_bis=z["sitzung_bis"], gesperrt=z["versuche_frei"] <= 0)


async def beenden() -> Umzugsstand:
    """Code und Sitzung gelten nicht mehr; die Sicherung bleibt im Sicherungsordner."""
    await db.execute("DELETE FROM umzug")
    await db.commit()
    return await stand()


async def _fehlversuch() -> None:
    """In einer eigenen Aufgabe, also außerhalb der Einheit der Anfrage: ein abgewiesener Versuch zählt, obwohl die Antwort 403
    ist und die Anfrage zurückgerollt wird (core/database.py, Einheiten)."""
    async def zaehlen() -> None:
        await db.execute("UPDATE umzug SET versuche_frei = versuche_frei - 1 WHERE id = 1 AND versuche_frei > 0")
        await db.commit()

    await asyncio.create_task(zaehlen())


def _paket_daten(datei: Path) -> tuple[int, str]:
    return datei.stat().st_size, compute_hash(datei)


async def einloesen(code: str) -> Umzugspaket:
    """Nur einmal, nur bis zum Ablauf, nur mit wenigen Versuchen; jeder Fehler 403 mit Grund."""
    z = await db.fetch_one("SELECT * FROM umzug WHERE id = 1")
    if z is None:
        raise Einrichtungsfehler("Auf diesem Gerät ist kein Umzug vorbereitet", 403)
    if z["versuche_frei"] <= 0:
        raise Einrichtungsfehler("Zu viele falsche Codes; bitte den Umzug auf dem alten Gerät neu vorbereiten", 403)
    if z["eingeloest_am"]:
        raise Einrichtungsfehler("Dieser Code ist schon eingelöst", 403)
    if jetzt() > z["gilt_bis"]:
        raise Einrichtungsfehler("Dieser Code ist abgelaufen; bitte den Umzug neu vorbereiten", 403)
    if not hmac.compare_digest(_summe(_norm(code)), z["code"]):
        await _fehlversuch()
        raise Einrichtungsfehler("Der Code stimmt nicht", 403)
    datei = settings.backup_dir / z["sicherung"]
    if not datei.is_file():
        raise Einrichtungsfehler("Die Sicherung des Umzugs fehlt; bitte neu vorbereiten", 409)
    sitzung, bis = secrets.token_urlsafe(32), _zeit(timedelta(hours=settings.umzug_sitzung_stunden))
    await db.execute("UPDATE umzug SET eingeloest_am = ?, sitzung = ?, sitzung_bis = ? WHERE id = 1", (jetzt(), _summe(sitzung), bis))
    await db.commit()
    groesse, sha = await asyncio.to_thread(_paket_daten, datei)
    zahl = await db.fetch_one("SELECT COUNT(*) AS n, COALESCE(SUM(file_size), 0) AS groesse FROM books")
    return Umzugspaket(sitzung=sitzung, sitzung_bis=bis, sicherung=z["sicherung"], groesse=groesse, sha256=sha,
                       schluessel={a.value: w for a in WEITERGABE if (w := schluessel.lesen(a))},
                       anschluesse={art: wert for art, b in anschluesse.ARTEN.items() if (wert := getattr(settings, b.feld))},
                       originale=Originalort(ort="kellerwolke" if wolke.bereit else "geraet", anzahl=zahl["n"], groesse=zahl["groesse"]))


async def sitzung_pruefen(wert: str) -> dict:
    z = await db.fetch_one("SELECT * FROM umzug WHERE id = 1")
    if not wert or z is None or not z["sitzung"] or not hmac.compare_digest(_summe(wert), z["sitzung"]) or jetzt() > (z["sitzung_bis"] or ""):
        raise Einrichtungsfehler("Keine gültige Sitzung für den Umzug", 403)
    return z


async def sicherungsdatei(wert: str) -> Path:
    z = await sitzung_pruefen(wert)
    datei = settings.backup_dir / z["sicherung"]
    if not datei.is_file():
        raise Einrichtungsfehler("Die Sicherung des Umzugs fehlt", 404)
    return datei


async def originale(wert: str) -> list[dict]:
    """Die Originale, die auf diesem Gerät liegen (ohne Kellerwolke), zum Kopieren."""
    await sitzung_pruefen(wert)
    aus = []
    for b in await db.fetch_all("SELECT hash, file_name, file_size FROM books ORDER BY id"):
        if await asyncio.to_thread(auf_dem_geraet, b["hash"]) is not None:
            aus.append({"hash": b["hash"], "name": b["file_name"], "groesse": b["file_size"]})
    return aus


async def originaldatei(wert: str, file_hash: str) -> Path:
    await sitzung_pruefen(wert)
    if not await db.fetch_one("SELECT 1 FROM books WHERE hash = ?", (file_hash,)):
        raise Einrichtungsfehler("Nicht gefunden", 404)
    datei = await asyncio.to_thread(auf_dem_geraet, file_hash)
    if datei is None:
        raise Einrichtungsfehler("Dieses Original liegt nicht auf dem Gerät", 404)
    return datei


# -- neues Gerät --------------------------------------------------------------------------------------------------------

def client(adresse: str) -> httpx.AsyncClient:
    """Die Verbindung zum alten Gerät: geprüftes https mit der Zertifikatsstelle des Hauses (KELLERWOLKE_CA), sonst der üblichen."""
    return httpx.AsyncClient(base_url=adresse, verify=_pruefung(), timeout=httpx.Timeout(60.0, connect=5.0))


def _grund(r: httpx.Response) -> str:
    try:
        d = r.json().get("detail")
    except (ValueError, AttributeError):
        d = None
    return d if isinstance(d, str) else f"Das alte Gerät meldet {r.status_code}"


async def _holen(c: httpx.AsyncClient, paket: Umzugspaket, ziel: Path) -> None:
    summe = hashlib.sha256()
    async with c.stream("GET", "/api/umzug/sicherung", headers={KOPF: paket.sitzung}) as r:
        if r.status_code >= 400:
            await r.aread()
            raise Einrichtungsfehler(f"Sicherung: {_grund(r)}", 502)
        with ziel.open("wb") as f:
            async for stueck in r.aiter_bytes(1 << 20):
                summe.update(stueck)
                f.write(stueck)
    if summe.hexdigest() != paket.sha256:
        raise Einrichtungsfehler("Die Sicherung kam nicht vollständig an (Prüfsumme)", 502)


async def verbinden(adresse: str, code: str) -> Umzugsergebnis:
    """Holt Paket und Sicherung (gestreamt, mit Prüfsumme), legt die Schlüssel in die Schlüsseldatei und beginnt den Auftrag
    "Sicherung einspielen"; die Adressen der Anschlüsse und die Adresse des alten Geräts schreibt er nach dem Tausch."""
    z = await zustand.nur_neu()
    if z["ausgangslage"] != "umzug":
        raise Einrichtungsfehler("Erst die Ausgangslage Umzug wählen")
    if not await zustand.bestand_leer():
        raise Einrichtungsfehler("Der Bestand ist nicht leer; ein Umzug überschreibt nie Bücher")
    if await zustand.konto_da():
        raise Einrichtungsfehler("Es gibt schon ein Konto; der Umzug bringt das Konto des alten Geräts mit")
    if settings.umzug_nur_https and not adresse.startswith("https://"):
        raise Einrichtungsfehler("Adresse: nur über https, damit Sicherung und Schlüssel geschützt reisen", 422)
    datei = wiederherstellen.ablage() / "sicherung.zip"
    datei.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with client(adresse) as c:
            r = await c.post("/api/umzug/einloesen", json={"code": code})
            if r.status_code >= 400:
                raise Einrichtungsfehler(f"Altes Gerät: {_grund(r)}", 403 if r.status_code == 403 else 502)
            paket = Umzugspaket.model_validate(r.json())
            await _holen(c, paket, datei)
    except httpx.HTTPError as f:
        raise Einrichtungsfehler(f"Das alte Gerät antwortet nicht ({type(f).__name__})", 502) from f
    for art, wert in paket.schluessel.items():
        schluessel.eintragen(schluessel.Art(art), wert)
    schluessel.eintragen(schluessel.Art.UMZUG, paket.sitzung)
    s = await wiederherstellen.einspielen.beginnen(quelle="umzug", kennung=paket.sicherung, name=paket.sicherung, ersetzen=False,
                                                   anschluesse=paket.anschluesse, einstellungen={QUELLE: adresse})
    return Umzugsergebnis(sicherung=paket.sicherung, einstellungen=sorted(paket.anschluesse), schluessel=sorted(paket.schluessel),
                          originale=paket.originale, einspielen=s)


async def originale_waehlen(weg: str):
    z = await zustand.nur_neu()
    if z["ausgangslage"] != "umzug":
        raise Einrichtungsfehler("Originale wählt man nur beim Umzug")
    if wolke.bereit:
        raise Einrichtungsfehler("Mit Kellerwolke bleiben die Originale, wo sie sind")
    if not await db.fetch_one("SELECT 1 FROM einrichtung_schritt WHERE schritt = 'verbinden' AND stand = 'erledigt'"):
        raise Einrichtungsfehler("Erst mit dem alten Gerät verbinden und die Sicherung einspielen")
    if weg == "kopieren":
        s = await kopieren.beginnen()
        await zustand.vermerken("originale", text="Originale werden vom alten Gerät kopiert, mit Prüfsummen")
    else:
        s = await pruefung.beginnen(pruefsummen=True)
        await zustand.vermerken("originale", text="Ort übernommen; jedes Original wird mit seiner Prüfsumme geprüft")
    return s
