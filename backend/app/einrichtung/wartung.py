"""Was die Schritte ändern (BF-82), an einer Stelle: Anschluss, Katalog, neues Profil, Stimme der Familie.

Auf einer neuen Installation gilt eine Änderung sofort. Unter Wartung (der Assistent wieder geöffnet) wird sie nur vorgemerkt:
als Zeile in `einrichtung_aenderung` mit einem Satz, was sie tut, ein neuer Schlüssel vorgemerkt im Schlüsselbund. Erst
`uebernehmen` mit dem `stand` der Liste wendet die angehakten an; die übrigen fallen weg. Entfernt oder ersetzt wird dabei nur,
was die Liste ausdrücklich nennt, gelöscht wird nichts."""

from __future__ import annotations

import hashlib
import json
import uuid

from backend.app.core import schluessel
from backend.app.core.database import db
from backend.app.einrichtung import anschluesse, katalog_schritt, zustand
from backend.app.einrichtung.modelle import Aenderung, Aenderungen, Uebernommen, Vorgemerkt
from backend.app.einrichtung.zustand import Einrichtungsfehler, jetzt
from backend.app.familie import ansagen, profile
from backend.app.familie.ansagelauf import ansagelauf
from backend.app.familie.modelle import Profil, ProfilNeu


async def oeffnen() -> None:
    """Nur auf einer eingerichteten Installation; ändert selbst nichts."""
    m = await zustand.modus()
    if m == "neu":
        raise Einrichtungsfehler("Die Ersteinrichtung ist noch offen")
    await db.execute("INSERT INTO einrichtung(id, neu, modus) VALUES (1, 0, 'wartung') ON CONFLICT(id) DO UPDATE SET modus = 'wartung', "
                     "geaendert_am = ?", (jetzt(),))
    await db.commit()


async def schliessen() -> None:
    """Ohne Übernehmen: alles Vorgemerkte fällt weg, auch vorgemerkte Schlüssel."""
    if await zustand.modus() != "wartung":
        return
    await db.execute("DELETE FROM einrichtung_aenderung")
    await db.execute("UPDATE einrichtung SET modus = 'aus', geaendert_am = ? WHERE id = 1", (jetzt(),))
    await db.commit()
    schluessel.verwerfen_vorgemerkt()


async def _anwenden(art: str, daten: dict, von: Profil | None) -> None:
    if art == "anschluss":
        if daten.get("schluessel_neu"):
            schluessel.uebernehmen(anschluesse.ARTEN[daten["anschluss"]].schluessel)
        await anschluesse.anwenden_eintrag(daten["anschluss"], daten["adresse"], None)
    elif art == "katalog":
        await katalog_schritt.anwenden(daten["wahl"])
    elif art == "profil":
        if von is None:
            raise Einrichtungsfehler("Ein Profil legt nur an, wer angemeldet ist", 403)
        await profile.anlegen(ProfilNeu.model_validate(daten), von)
        ansagelauf.anstossen()
    elif art == "stimme":
        await ansagen.familienstimme_setzen(daten["stimme"])
        ansagelauf.anstossen()


async def aendern(schritt: str, art: str, ziel: str, was: str, daten: dict, *, alt: str = "", neu: str = "",
                  neuer_schluessel: tuple[schluessel.Art, str] | None = None, von: Profil | None = None) -> Vorgemerkt:
    """Die eine Stelle, an der ein Schritt etwas ändert: sofort (neue Installation) oder vorgemerkt (Wartung)."""
    m = await zustand.modus()
    if m == "wartung":
        if schritt not in zustand.schrittbuch().wartung:
            raise Einrichtungsfehler("Diesen Schritt gibt es unter Wartung nicht", 404)
        if neuer_schluessel:
            schluessel.vormerken(*neuer_schluessel)
        await db.execute("DELETE FROM einrichtung_aenderung WHERE art = ? AND ziel = ?", (art, ziel))
        a = Aenderung(id=str(uuid.uuid4()), schritt=schritt, art=art, was=was, alt=alt, neu=neu)
        await db.execute("INSERT INTO einrichtung_aenderung(id, schritt, art, ziel, was, alt, neu, daten) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (a.id, schritt, art, ziel, was, alt, neu, json.dumps(daten | {"schluessel_neu": bool(neuer_schluessel)})))
        await db.commit()
        return Vorgemerkt(angewandt=False, aenderung=a)
    await zustand.nur_neu()
    if neuer_schluessel:
        schluessel.eintragen(*neuer_schluessel)
    await _anwenden(art, daten | {"schluessel_neu": False}, von)
    return Vorgemerkt(angewandt=True)


def _stand(zeilen: list[dict]) -> str:
    return hashlib.sha256(json.dumps([[z["id"], z["was"], z["daten"]] for z in zeilen], sort_keys=True).encode()).hexdigest()[:16]


async def _zeilen() -> list[dict]:
    return await db.fetch_all("SELECT * FROM einrichtung_aenderung ORDER BY rowid")          # in der Folge des Vormerkens


def _aenderung(z: dict) -> Aenderung:
    return Aenderung(id=z["id"], schritt=z["schritt"], art=z["art"], was=z["was"], alt=z["alt"], neu=z["neu"])


async def aenderungen() -> Aenderungen:
    if await zustand.modus() != "wartung":
        raise Einrichtungsfehler("Der Assistent ist nicht unter Wartung geöffnet")
    zeilen = await _zeilen()
    geaendert = {z["schritt"] for z in zeilen}
    unveraendert = [zustand.schrittbuch().schritte[s].name for s in zustand.schrittbuch().wartung if s not in geaendert and s != "abschluss"]
    return Aenderungen(aenderungen=[_aenderung(z) for z in zeilen], unveraendert=unveraendert, stand=_stand(zeilen))


async def uebernehmen(stand: str, ids: list[str], von: Profil) -> Uebernommen:
    """Wendet nur die genannten an, nur mit dem `stand` der Liste (sonst 409); danach ist der Assistent geschlossen."""
    zeilen = await _zeilen()
    if await zustand.modus() != "wartung":
        raise Einrichtungsfehler("Der Assistent ist nicht unter Wartung geöffnet")
    if stand != _stand(zeilen):
        raise Einrichtungsfehler("Die Liste der Änderungen hat sich geändert, bitte neu ansehen")
    if fremd := set(ids) - {z["id"] for z in zeilen}:
        raise Einrichtungsfehler(f"Unbekannte Änderung: {', '.join(sorted(fremd))}", 404)
    gewaehlt = [z for z in zeilen if z["id"] in ids]
    for z in gewaehlt:
        await _anwenden(z["art"], json.loads(z["daten"]), von)
    await schliessen()
    return Uebernommen(uebernommen=[_aenderung(z) for z in gewaehlt], verworfen=len(zeilen) - len(gewaehlt))


# -- die Schritte, die etwas ändern -----------------------------------------------------------------------------------------

async def anschluss(art: str, adresse: str, neuer_schluessel: str | None) -> Vorgemerkt:
    b = anschluesse.ARTEN[art]
    teile = [f"Adresse {adresse}"] + (["neuer Schlüssel"] if neuer_schluessel else [])
    return await aendern("anschluesse", "anschluss", art, f"{b.name}: {' und '.join(teile)}", {"anschluss": art, "adresse": adresse},
                         alt=(await anschluesse.eintrag(art)).adresse, neu=adresse,
                         neuer_schluessel=(b.schluessel, neuer_schluessel) if neuer_schluessel and b.schluessel else None)


async def katalog(wahl: str) -> Vorgemerkt:
    return await aendern("katalog", "katalog", "katalog", f"Katalog: {katalog_schritt.NAMEN[wahl]}", {"wahl": wahl}, neu=katalog_schritt.NAMEN[wahl])


async def profil(neu: ProfilNeu, von: Profil | None) -> Vorgemerkt:
    rolle = {"verwaltung": "Verwaltung", "erwachsen": "Erwachsen", "kind": "Kind"}[neu.rolle]
    return await aendern("familie", "profil", str(uuid.uuid4()), f"Neues Profil {neu.name} ({rolle})", neu.model_dump(mode="json"),
                         neu=neu.name, von=von)


async def stimme(wert: str) -> Vorgemerkt:
    return await aendern("familie", "stimme", "stimme", f"Stimme der Familie: {wert or 'keine'}", {"stimme": wert},
                         alt=await ansagen.familienstimme(), neu=wert)
