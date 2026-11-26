"""Wie ein Profil hinausgeht (BF-78): `GET /api/familie/ich` mit Fähigkeiten, Darstellung und Lesehilfen der Stufe samt der Wahl
der Eltern, Lesezeitstand, Katze und dem, was die Eltern sehen; ein Profil für die Liste (mit Geburtsjahr und Einstellungen
nur für die, die es ändern dürfen); die Stufen aus stufen.json für die Oberfläche."""

from __future__ import annotations

from backend.app.familie import lesezeit, profile, rechte
from backend.app.familie.modelle import (
    Ich, Katze, Lesezeitvorgabe, Profil, ProfilEintrag, Profileinstellungen, Stufenangabe, Stufenansicht, Stufenvorgaben, Zugangsangaben,
)
from backend.app.familie.stufen import Darstellung, Lesehilfen, Stufe, stufenbuch


def _stufe(p: Profil) -> Stufe | None:
    return stufenbuch().stufe(p.stufe) if p.kind and p.stufe and stufenbuch().hat_stufe(p.stufe) else None


def lesehilfen(p: Profil) -> Lesehilfen | None:
    if (s := _stufe(p)) is None:
        return None
    return s.lesehilfen.model_copy(update=p.einstellungen.lesehilfen.model_dump(exclude_none=True))


def darstellung(p: Profil) -> Darstellung | None:
    """Die Darstellung der Stufe; die Schriftwahl der Eltern (klein, mittel, groß) ändert die Größe."""
    if (s := _stufe(p)) is None:
        return None
    faktor = stufenbuch().gestaltung.schriftgroessen[lesehilfen(p).schrift]
    return s.darstellung.model_copy(update={"groesse_px": round(s.darstellung.groesse_px * faktor)})


def katze(p: Profil) -> Katze:
    k, s = p.einstellungen.katze, _stufe(p)
    if s is None:
        return Katze(an=False, name=k.name, schnurren=False)
    return Katze(an=True if k.an is None else k.an, name=k.name, schnurren=k.schnurren, name_eingabe=s.katze_name)


def einstellungen(p: Profil) -> Profileinstellungen | None:
    """Was für ein Kind wirkt; Erwachsene haben keine Lesehilfen und keine Lesezeit."""
    hilfen, zeit = lesehilfen(p), lesezeit.wirksam(p)
    return Profileinstellungen(lesehilfen=hilfen, lesezeit=zeit, katze=katze(p)) if hilfen and zeit else None


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
               lesehilfen=lesehilfen(p), lesezeit=await lesezeit.stand(p), katze=katze(p), einblick=s.einblick if s else [])


def stufenansicht() -> Stufenansicht:
    sb = stufenbuch()
    stufen = [Stufenangabe(schluessel=s.schluessel, name=s.name, alter=s.alter, alter_von=s.ab_alter, alter_bis=sb.alter_bis(s),
                           faehigkeiten=s.faehigkeiten, einblick=s.einblick, darstellung=s.darstellung, lesezeichen_je_buch=s.lesezeichen_je_buch,
                           vorgaben=Stufenvorgaben(lesehilfen=s.lesehilfen, lesezeit=lesezeit.vorgabe_fuer(s.ab_alter),
                                                   katze=Katze(an=True, name="", schnurren=False, name_eingabe=s.katze_name)))
              for s in sb.stufen]
    return Stufenansicht(
        stufen=stufen,
        lesezeit=[Lesezeitvorgabe(alter_von=v.alter_von, alter_bis=v.alter_bis, minuten=v.minuten, an=v.an) for v in sb.lesezeit.nach_alter],
        rollen={name: r.faehigkeiten for name, r in sb.rollen.items()}, faehigkeiten=sb.faehigkeiten,
        zugang=Zugangsangaben(**sb.zugang.model_dump(include={"pin_stellen_von", "pin_stellen_bis", "bild_pin_anzahl", "bilder"})),
        katze_vorschlaege=sb.katze.vorschlaege, katze_nennung=sb.katze.nennung)
