"""Lesezeit je Kind (BF-78): der Leser meldet im Takt, wie lange gelesen oder vorgelesen wurde; gezählt wird je Tag (Ortszeit).

Was gilt, wählen die Eltern je Kind (`einstellungen.lesezeit`); ohne Wahl gilt die Vorgabe nach dem Alter aus stufen.json
(Minuten am Tag, Ruhezeit ab einer Stunde vor dem Schlafen bis zum Aufstehen). Der Server bricht nichts ab: er sagt, wie viel
heute noch bleibt, ab wann der sanfte Hinweis kommt und ob gerade Ruhezeit ist; die Oberfläche hält am Satzende an.
Die Uhr lässt sich für Tests stellen (`uhr.stellen`)."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from backend.app.core.database import db
from backend.app.familie.modelle import Lesezeitmeldung, Lesezeitregel, Lesezeitstand, Profil
from backend.app.familie.profile import alter
from backend.app.familie.stufen import stufenbuch


class Uhr:
    def __init__(self) -> None:
        self._gestellt: datetime | None = None

    def jetzt(self) -> datetime:
        return self._gestellt or datetime.now()

    def stellen(self, zeitpunkt: datetime | None) -> None:
        self._gestellt = zeitpunkt


uhr = Uhr()


def _uhrzeit(text: str) -> time:
    stunde, minute = text.split(":")
    return time(int(stunde), int(minute))


def _frueher(text: str, minuten: int) -> str:
    return (datetime.combine(datetime.min, _uhrzeit(text)) - timedelta(minutes=minuten)).strftime("%H:%M")


def vorgabe_fuer(jahre: int) -> Lesezeitregel:
    """Die Vorgabe der Leitlinie für dieses Alter (stufen.json, `lesezeit`)."""
    sb = stufenbuch()
    v = sb.lesezeit_fuer(jahre)
    return Lesezeitregel(an=v.an, minuten=v.minuten, ruhe_an=True, ruhe_von=_frueher(v.schlafen, sb.lesezeit.ruhe_vor_schlafen_min),
                         ruhe_bis=sb.lesezeit.aufstehen, vorlesen_zaehlt=sb.lesezeit.vorlesen_zaehlt)


def vorgabe(p: Profil) -> Lesezeitregel:
    """Nach dem Alter; ohne Geburtsjahr nach dem Alter, ab dem die Stufe gilt."""
    jahre = alter(p.geburtsjahr, uhr.jetzt().date())
    if jahre is None:
        jahre = stufenbuch().stufe(p.stufe).ab_alter if p.stufe else 0
    return vorgabe_fuer(jahre)


def wirksam(p: Profil) -> Lesezeitregel | None:
    """Was für dieses Profil gilt; Erwachsene haben keine Lesezeit."""
    if not p.kind:
        return None
    return p.einstellungen.lesezeit or vorgabe(p)


def ruhe_bis(r: Lesezeitregel, jetzt: datetime) -> str | None:
    """Ist jetzt Ruhezeit, bis wann (HH:MM); eine Ruhezeit mit `bis` vor `von` geht über Mitternacht."""
    if not r.ruhe_an:
        return None
    t, von, bis = jetzt.time(), _uhrzeit(r.ruhe_von), _uhrzeit(r.ruhe_bis)
    return r.ruhe_bis if ((von <= t < bis) if von < bis else (t >= von or t < bis)) else None


async def _heute(profil_id: str) -> tuple[int, int]:
    z = await db.fetch_one("SELECT sekunden, vorlesen_sekunden FROM lesezeit WHERE profil_id = ? AND tag = ?",
                           (profil_id, uhr.jetzt().date().isoformat()))
    return (z["sekunden"], z["vorlesen_sekunden"]) if z else (0, 0)


async def stand(p: Profil) -> Lesezeitstand:
    w = wirksam(p)
    gelesen, vorgelesen = await _heute(p.id)
    if w is None or not (w.an or w.ruhe_an):
        return Lesezeitstand(an=False, heute_s=gelesen + vorgelesen, grenze_s=None, rest_s=None, hinweis_ab_s=None, ruht=False, ruhe_bis=None)
    heute = gelesen + (vorgelesen if w.vorlesen_zaehlt else 0)
    grenze = w.minuten * 60 if w.an else None
    hinweis = max(0, grenze - stufenbuch().lesezeit.hinweis_vor_ende_min * 60) if grenze else None
    bis = ruhe_bis(w, uhr.jetzt())
    return Lesezeitstand(an=True, heute_s=heute, grenze_s=grenze, rest_s=max(0, grenze - heute) if grenze else None, hinweis_ab_s=hinweis,
                         ruht=bis is not None, ruhe_bis=bis)


async def melden(p: Profil, m: Lesezeitmeldung) -> Lesezeitstand:
    """Zählt die gemeldete Zeit dazu, höchstens einen Takt auf einmal."""
    s = min(m.sekunden, stufenbuch().lesezeit.takt_hoechstens_s)
    spalte = "vorlesen_sekunden" if m.vorlesen else "sekunden"
    await db.execute(f"""INSERT INTO lesezeit (profil_id, tag, {spalte}) VALUES (?, ?, ?)
                         ON CONFLICT(profil_id, tag) DO UPDATE SET {spalte} = {spalte} + excluded.{spalte}""",
                     (p.id, uhr.jetzt().date().isoformat(), s))
    return await stand(p)
