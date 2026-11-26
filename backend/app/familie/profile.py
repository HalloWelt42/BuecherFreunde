"""Profile (BF-78): lesen, anlegen, ändern, PIN setzen, löschen erst nach den Folgen. Wer was darf, steht in familie/rechte.py;
das letzte Profil Verwaltung bleibt immer."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date

from backend.app.core.database import db
from backend.app.familie import pin, rechte
from backend.app.familie.fehler import Fehlt, Konflikt, NichtErlaubt, Unpassend
from backend.app.familie.modelle import (
    Einstellungen, EinstellungenEingabe, Loeschfolgen, PinSetzen, Profil, ProfilAenderung, ProfilEintrag, ProfilNeu,
)
from backend.app.familie.stufen import Rollenname, stufenbuch

SPALTEN = """id, name, zeichen, farbe, rolle, stufe, pin != '' AS hat_pin, bild_pin != '' AS hat_bild_pin, geburtsjahr, einstellungen,
             sortierung, angelegt_am, name_vom_konto"""
FEHLT = "Profil nicht gefunden"
ORDNUNG = "ORDER BY sortierung, angelegt_am, id"


def aus_zeile(z: dict) -> Profil:
    return Profil(**{**z, "hat_pin": bool(z["hat_pin"]), "hat_bild_pin": bool(z["hat_bild_pin"]), "name_vom_konto": bool(z["name_vom_konto"]),
                     "einstellungen": Einstellungen.model_validate_json(z["einstellungen"] or "{}")})


def eintrag(p: Profil) -> ProfilEintrag:
    """Das Profil, wie es die Profilwahl zeigt, ohne Geburtsjahr und Einstellungen (die fügt familie/ich.py an, wo sie hingehören)."""
    return ProfilEintrag(id=p.id, name=p.name, zeichen=p.zeichen, farbe=p.farbe, rolle=p.rolle, stufe=p.stufe, hat_pin=p.hat_pin,
                         hat_bild_pin=p.hat_bild_pin)


def einstellungen_mit(bisher: Einstellungen, neu: EinstellungenEingabe) -> Einstellungen:
    """Jeder genannte Teil ersetzt den gespeicherten; die übrigen bleiben."""
    return bisher.model_copy(update={teil: getattr(neu, teil) for teil in neu.model_fields_set if getattr(neu, teil) is not None})


def alter(geburtsjahr: int | None, heute: date | None = None) -> int | None:
    """Alter am Ende dieses Jahres; ohne Geburtstag geht es nicht genauer."""
    return (heute or date.today()).year - geburtsjahr if geburtsjahr else None


def stufe_vorschlag(geburtsjahr: int | None) -> str | None:
    a = alter(geburtsjahr)
    return stufenbuch().vorschlag(a).schluessel if a is not None else None


async def alle() -> list[Profil]:
    return [aus_zeile(z) for z in await db.fetch_all(f"SELECT {SPALTEN} FROM profil {ORDNUNG}")]


async def holen(pid: str) -> Profil | None:
    z = await db.fetch_one(f"SELECT {SPALTEN} FROM profil WHERE id = ?", (pid,))
    return aus_zeile(z) if z else None


async def noetig(pid: str) -> Profil:
    p = await holen(pid)
    if p is None:
        raise Fehlt(FEHLT)
    return p


async def braucht_wahl() -> bool:
    """Ohne Wahl geht es nur mit genau einem Profil ohne PIN und ohne Bild-PIN; dann verhält sich die App wie vor BF-78."""
    z = await db.fetch_one("SELECT COUNT(*) AS n, COALESCE(SUM(pin != '' OR bild_pin != ''), 0) AS geschuetzt FROM profil")
    return z["n"] != 1 or z["geschuetzt"] > 0


async def einziges() -> Profil:
    z = await db.fetch_one(f"SELECT {SPALTEN} FROM profil {ORDNUNG} LIMIT 1")
    if z is None:
        raise Fehlt("Es gibt noch kein Profil")
    return aus_zeile(z)


async def name_vom_konto(p: Profil, name: str) -> Profil:
    """Das erste Profil bekommt beim ersten Anmelden den Namen des Kontos, mit dem das Gerät angemeldet ist."""
    name = name.strip()[:40]
    if not p.name_vom_konto or not name:
        return p
    await db.execute("UPDATE profil SET name = ?, name_vom_konto = 0 WHERE id = ? AND name_vom_konto = 1", (name, p.id))
    await db.commit()                    # vor dem Weg selbst: hält keine Sperre über die ganze Anfrage
    return p.model_copy(update={"name": name, "name_vom_konto": False})


async def _name_frei(name: str, ausser: str | None = None) -> None:
    if await db.fetch_one("SELECT 1 FROM profil WHERE name = ? COLLATE NOCASE AND id IS NOT ?", (name, ausser)):
        raise Konflikt("Ein Profil mit diesem Namen gibt es schon")


def _stufe(rolle: Rollenname, stufe: str | None, geburtsjahr: int | None) -> str | None:
    """Nur Kinder haben eine Stufe; ohne Angabe gilt der Vorschlag aus dem Geburtsjahr."""
    if rolle != "kind":
        if stufe:
            raise Unpassend("Stufe: nur für Kinder")
        return None
    if stufe or (stufe := stufe_vorschlag(geburtsjahr)):
        return stufe
    raise Unpassend("Stufe: fehlt; ohne Geburtsjahr gibt es keinen Vorschlag")


async def _verwaltung_bleibt(ziel: Profil) -> None:
    if ziel.rolle == "verwaltung" and (await db.fetch_one("SELECT COUNT(*) AS n FROM profil WHERE rolle = 'verwaltung'"))["n"] <= 1:
        raise Konflikt("Das letzte Profil Verwaltung bleibt")


async def anlegen(neu: ProfilNeu, von: Profil) -> Profil:
    if not rechte.darf_anlegen(von, neu.rolle):
        raise NichtErlaubt("Neue Profile legt die Verwaltung an; Erwachsene legen nur Kinder an")
    await _name_frei(neu.name)
    stufe = _stufe(neu.rolle, neu.stufe, neu.geburtsjahr)
    pid = str(uuid.uuid4())
    await db.execute("""INSERT INTO profil (id, name, zeichen, farbe, rolle, geburtsjahr, stufe, einstellungen, sortierung)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, (SELECT COALESCE(MAX(sortierung), -1) + 1 FROM profil))""",
                     (pid, neu.name, neu.zeichen, neu.farbe, neu.rolle, neu.geburtsjahr, stufe,
                      einstellungen_mit(Einstellungen(), neu.einstellungen).model_dump_json()))
    return await noetig(pid)


async def aendern(pid: str, a: ProfilAenderung, von: Profil) -> Profil:
    ziel = await noetig(pid)
    gesetzt = a.model_fields_set
    if not rechte.darf_aendern(von, ziel, a.rolle if "rolle" in gesetzt else None):
        raise NichtErlaubt("Dieses Profil darfst du hier nicht ändern")
    rolle: Rollenname = a.rolle if "rolle" in gesetzt and a.rolle else ziel.rolle
    if rolle != ziel.rolle:
        await _verwaltung_bleibt(ziel)
    werte: dict[str, object] = {}
    if "name" in gesetzt and a.name:
        await _name_frei(a.name, pid)
        werte |= {"name": a.name, "name_vom_konto": 0}
    for feld in ("zeichen", "farbe"):
        if feld in gesetzt and getattr(a, feld) is not None:
            werte[feld] = getattr(a, feld)
    geburtsjahr = a.geburtsjahr if "geburtsjahr" in gesetzt else ziel.geburtsjahr
    stufe = a.stufe if "stufe" in gesetzt else (ziel.stufe if rolle == "kind" else None)
    werte |= {"rolle": rolle, "geburtsjahr": geburtsjahr, "stufe": _stufe(rolle, stufe, geburtsjahr)}
    if "einstellungen" in gesetzt and a.einstellungen is not None:
        werte["einstellungen"] = einstellungen_mit(ziel.einstellungen, a.einstellungen).model_dump_json()
    await db.execute(f"UPDATE profil SET {', '.join(f'{k} = ?' for k in werte)} WHERE id = ?", (*werte.values(), pid))
    return await noetig(pid)


async def katze_benennen(p: Profil, name: str) -> Profil:
    e = p.einstellungen.model_copy(update={"katze": p.einstellungen.katze.model_copy(update={"name": name})})
    await db.execute("UPDATE profil SET einstellungen = ? WHERE id = ?", (e.model_dump_json(), p.id))
    return await noetig(p.id)


async def pin_setzen(pid: str, eingabe: PinSetzen, von: Profil) -> Profil:
    """PIN oder Bild-PIN, je nur eine; setzt sie jemand anders, enden die Sitzungen dieses Profils."""
    ziel = await noetig(pid)
    if not rechte.darf_pin_setzen(von, ziel):
        raise NichtErlaubt("Diese PIN setzt die Verwaltung zurück")
    wert = await pin.wert(eingabe.pin) if eingabe.pin else ""
    bild = await pin.wert(pin.bilder_text(eingabe.bild_pin)) if eingabe.bild_pin else ""
    await db.execute("UPDATE profil SET pin = ?, bild_pin = ? WHERE id = ?", (wert, bild, pid))
    if von.id != pid:
        await db.execute("DELETE FROM profil_sitzung WHERE profil_id = ?", (pid,))
    pin.versuche.gelungen(pid)
    return await noetig(pid)


async def pin_vergessen(pid: str) -> Profil:
    """Nach erneuter Anmeldung mit dem Konto des Geräts: die PIN eines Profils Verwaltung fällt weg."""
    ziel = await noetig(pid)
    if ziel.rolle != "verwaltung":
        raise NichtErlaubt("So lässt sich nur die PIN der Verwaltung zurücksetzen; andere setzt die Verwaltung zurück")
    await db.execute("UPDATE profil SET pin = '', bild_pin = '' WHERE id = ?", (pid,))
    await db.execute("DELETE FROM profil_sitzung WHERE profil_id = ?", (pid,))
    pin.versuche.gelungen(pid)
    return await noetig(pid)


# -- Löschen ---------------------------------------------------------------------------------------------------------------------

ZAEHLUNGEN = {
    "notizen": "SELECT COUNT(*) AS n FROM book_notes WHERE profil_id = ?",
    "markierungen": "SELECT COUNT(*) AS n FROM book_highlights WHERE profil_id = ?",
    "etiketten": "SELECT COUNT(*) AS n FROM book_labels WHERE profil_id = ?",
    "lesestaende": "SELECT COUNT(*) AS n FROM user_book_data WHERE profil_id = ?",
    "vorlesestellen": "SELECT COUNT(*) AS n FROM vorlesestelle WHERE profil_id = ?",
    "fassungen_gelesen": "SELECT COUNT(*) AS n FROM fassung_lesestand WHERE profil_id = ?",
    "freigaben": "SELECT COUNT(*) AS n FROM freigabe WHERE profil_id = ?",
    "private_buecher": "SELECT COUNT(*) AS n FROM buch_privat WHERE profil_id = ?",
    "lesezeit_tage": "SELECT COUNT(*) AS n FROM lesezeit WHERE profil_id = ?",
    "geraete": "SELECT COUNT(*) AS n FROM geraet_bindung WHERE profil_id = ?",
}


async def loeschfolgen(pid: str) -> Loeschfolgen:
    ziel = await noetig(pid)
    zahlen = {k: (await db.fetch_one(sql, (pid,)))["n"] for k, sql in ZAEHLUNGEN.items()}
    stand = hashlib.sha256(json.dumps([pid, zahlen], sort_keys=True).encode()).hexdigest()[:16]
    return Loeschfolgen(profil=eintrag(ziel), stand=stand, **zahlen)


async def loeschen(pid: str, stand: str, von: Profil) -> None:
    if not rechte.darf(von, "profile"):
        raise NichtErlaubt("Profile löscht die Verwaltung")
    ziel = await noetig(pid)
    await _verwaltung_bleibt(ziel)
    if (await loeschfolgen(pid)).stand != stand:
        raise Konflikt("Die Folgen haben sich geändert; bitte neu ansehen")
    await db.execute("DELETE FROM profil WHERE id = ?", (pid,))
    pin.versuche.gelungen(pid)
