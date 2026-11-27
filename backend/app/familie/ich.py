"""Wie ein Profil hinausgeht (BF-78): `GET /api/familie/ich` mit Fähigkeiten, Darstellung und Lesehilfen der Stufe samt der Wahl
der Eltern, Lesezeitstand, Katze, dem, was die Eltern sehen, und der Gestaltung des Kinderbereichs (BF-88); ein Profil für die
Liste (mit Geburtsjahr und Einstellungen nur für die, die es ändern dürfen); die Stufen aus stufen.json für die Oberfläche. Dazu,
mit welcher Stimme und welchen Werten das Profil vorgelesen bekommt (BF-14)."""

from __future__ import annotations

from backend.app.familie import ansagen, lesezeit, profile, rechte
from backend.app.familie.fehler import NichtErlaubt
from backend.app.familie.modelle import (
    Ich, Katze, Lesezeitvorgabe, Profil, ProfilEintrag, Profileinstellungen, Stufenangabe, Stufenansicht, Stufenvorgaben, Zugangsangaben,
)
from backend.app.vorlesen.modelle import Vorlesestand
from backend.app.familie.stufen import Darstellung, Gestaltungsart, Lesehilfen, Leseschrift, Stufe, Uhrart, stufenbuch


def _stufe(p: Profil) -> Stufe | None:
    return stufenbuch().stufe(p.stufe) if p.kind and p.stufe and stufenbuch().hat_stufe(p.stufe) else None


def lesehilfen(p: Profil) -> Lesehilfen | None:
    if (s := _stufe(p)) is None:
        return None
    return s.lesehilfen.model_copy(update=p.einstellungen.lesehilfen.model_dump(exclude_none=True))


def darstellung(p: Profil) -> Darstellung | None:
    """Die Darstellung der Stufe; die Schriftwahl (klein, mittel, groß) ändert die Größe, die Leseschrift normal Schriftart und
    Abstände (stufen.json, `gestaltung.normalschrift`). Die Kinderschrift ist die Darstellung der Stufe selbst."""
    if (s := _stufe(p)) is None:
        return None
    hilfen, gestaltung = lesehilfen(p), stufenbuch().gestaltung
    neu: dict[str, object] = {"groesse_px": round(s.darstellung.groesse_px * gestaltung.schriftgroessen[hilfen.schrift])}
    if hilfen.schrift_wahl == "normal":
        neu |= gestaltung.normalschrift.model_dump()
    return s.darstellung.model_copy(update=neu)


def katze(p: Profil) -> Katze:
    k, s = p.einstellungen.katze, _stufe(p)
    if s is None:
        return Katze(an=False, name=k.name, schnurren=False)
    return Katze(an=s.katze_an if k.an is None else k.an, name=k.name, schnurren=k.schnurren, name_eingabe=s.katze_name)


def gestaltung(p: Profil) -> Gestaltungsart | None:
    """Klein oder groß: die Wahl der Eltern, sonst die Stufe. Eine Stufe ohne Gestaltung (Jugend) liest in der Oberfläche der App,
    dort gilt keine Wahl."""
    if (s := _stufe(p)) is None or s.gestaltung is None:
        return None
    return p.einstellungen.gestaltung or s.gestaltung


def uhr(p: Profil) -> Uhrart | None:
    """Die Uhr im Kopf der Gestaltung groß: Zeiger oder Zahl, die Wahl der Eltern, sonst die Stufe."""
    if (s := _stufe(p)) is None:
        return None
    return p.einstellungen.uhr or s.uhr


def einstellungen(p: Profil) -> Profileinstellungen | None:
    """Was für ein Kind wirkt; Erwachsene haben keine Lesehilfen und keine Lesezeit."""
    hilfen, zeit, art = lesehilfen(p), lesezeit.wirksam(p), uhr(p)
    if not (hilfen and zeit and art):
        return None
    return Profileinstellungen(lesehilfen=hilfen, lesezeit=zeit, katze=katze(p), gestaltung=gestaltung(p), uhr=art,
                               vorlesen=p.einstellungen.vorlesen)


async def vorlesen(p: Profil) -> Vorlesestand:
    """Stimme und Werte fürs Vorlesen: ein Kind hört die Wahl der Eltern (sonst die Stimme der Familie), dieselbe wie für seine
    Ansagen; ein Erwachsener wählt im Leser selbst (leer: die Stimme ab Werk der Vertonung)."""
    wahl = p.einstellungen.vorlesen
    stimme = await ansagen.stimme_fuer(p) if p.kind else (wahl.stimme or "")
    return Vorlesestand(stimme=stimme, werte=wahl.werte, eigene_wahl=p.erwachsen)


def eintrag(p: Profil, mit_angaben: bool = False) -> ProfilEintrag:
    grund = profile.eintrag(p)
    return grund.model_copy(update={"geburtsjahr": p.geburtsjahr, "einstellungen": einstellungen(p)}) if mit_angaben else grund


def eintrag_fuer(p: Profil, betrachter: Profil | None) -> ProfilEintrag:
    """Geburtsjahr und Einstellungen sieht, wer das Profil ändern darf, und das Profil selbst."""
    darf = betrachter is not None and (betrachter.id == p.id or rechte.darf_aendern(betrachter, p, None))
    return eintrag(p, mit_angaben=darf)


async def ich(p: Profil) -> Ich:
    s = _stufe(p)
    return Ich(profil=eintrag(p, mit_angaben=True), faehigkeiten=sorted(rechte.faehigkeiten(p)), darstellung=darstellung(p) or {},
               lesehilfen=lesehilfen(p), lesezeit=await lesezeit.stand(p), katze=katze(p), einblick=s.einblick if s else [],
               gestaltung=gestaltung(p), uhr=uhr(p), vorlesen=await vorlesen(p))


async def schrift_waehlen(p: Profil, wahl: Leseschrift) -> Ich:
    """Das Kind schaltet beim Lesen zwischen normal und Kinderschrift; nur in der Gestaltung groß, sonst wählen die Eltern."""
    if gestaltung(p) != "gross":
        raise NichtErlaubt("Die Schrift wählen hier die Eltern")
    return await ich(await profile.schrift_waehlen(p, wahl))


def stufenansicht() -> Stufenansicht:
    sb = stufenbuch()
    stufen = [Stufenangabe(schluessel=s.schluessel, name=s.name, alter=s.alter, alter_von=s.ab_alter, alter_bis=sb.alter_bis(s),
                           faehigkeiten=s.faehigkeiten, einblick=s.einblick, darstellung=s.darstellung, lesezeichen_je_buch=s.lesezeichen_je_buch,
                           vorgaben=Stufenvorgaben(lesehilfen=s.lesehilfen, lesezeit=lesezeit.vorgabe_fuer(s.ab_alter),
                                                   katze=Katze(an=s.katze_an, name="", schnurren=False, name_eingabe=s.katze_name),
                                                   gestaltung=s.gestaltung, uhr=s.uhr))
              for s in sb.stufen]
    return Stufenansicht(
        stufen=stufen,
        lesezeit=[Lesezeitvorgabe(alter_von=v.alter_von, alter_bis=v.alter_bis, minuten=v.minuten, an=v.an) for v in sb.lesezeit.nach_alter],
        rollen={name: r.faehigkeiten for name, r in sb.rollen.items()}, faehigkeiten=sb.faehigkeiten,
        zugang=Zugangsangaben(**sb.zugang.model_dump(include={"pin_stellen_von", "pin_stellen_bis", "bild_pin_anzahl", "bilder"})),
        katze_vorschlaege=sb.katze.vorschlaege, katze_nennung=sb.katze.nennung)
