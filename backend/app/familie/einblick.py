"""Einblick der Eltern (BF-78), abgestuft nach der Stufe des Kindes und für das Kind sichtbar: bis Klasse 4 Titel, Lesezeit
und Fortschritt; ab 10 nur Titel und grober Fortschritt; ab 14 nur, was das Kind teilt. Notizen und Markierungen zeigt der
Einblick nie. Was eine Stufe zeigt, steht in stufen.json (`einblick`)."""

from __future__ import annotations

from backend.app.core.database import db
from backend.app.familie import lesestand, lesezeit
from backend.app.familie.modelle import Buchzeile, Einblicksantwort, Einblickseintrag, Profil
from backend.app.familie.sichtbar import Sicht
from backend.app.familie.stufen import stufenbuch

HOECHSTENS = 200
BUCHSPALTEN = "b.id, b.title, b.author, COALESCE(b.typ, '') AS typ, b.year, COALESCE(b.page_count, 0) AS page_count, b.alter_von, b.alter_bis, b.alter_quelle"


def grob(anteil: float) -> float:
    """In wenigen Schritten (stufen.json, `fortschritt_grob_stufen`), etwa 0, 0,25, 0,5, 0,75, 1."""
    schritte = stufenbuch().gestaltung.fortschritt_grob_stufen
    return round(anteil * schritte) / schritte


def _eintrag(z: dict, sichtbar: list[str]) -> Einblickseintrag:
    """Fertig ist ein Buch nach der Regel in familie/lesestand.py; dann ist auch der Fortschritt voll."""
    fertig = z["fertig_am"] is not None
    anteil = 1.0 if fertig else lesestand.anteil(z["reading_position"], z["page_count"])
    genau = "fortschritt" in sichtbar
    seite = lesestand.werte(z["reading_position"]).get("page") if genau else None
    return Einblickseintrag(buch=Buchzeile(**{k: z[k] for k in Buchzeile.model_fields}),
                            fortschritt=anteil if genau else grob(anteil) if "grober_fortschritt" in sichtbar else None,
                            seite=int(seite) if isinstance(seite, int | float) else None, seiten=(z["page_count"] or None) if genau else None,
                            fertig=fertig, zuletzt=z["last_read_at"] if "zuletzt" in sichtbar else None)


async def einblick(kind: Profil) -> Einblicksantwort:
    sichtbar = stufenbuch().stufe(kind.stufe).einblick
    sicht, werte = Sicht.von(kind).bedingung("b.id")
    nur_geteilt = "AND u.geteilt = 1" if "geteiltes" in sichtbar else ""
    zeilen = await db.fetch_all(f"""SELECT {BUCHSPALTEN}, u.reading_position, u.last_read_at, u.fertig_am FROM user_book_data u
                                    JOIN books b ON b.id = u.book_id
                                    WHERE u.profil_id = ? AND (COALESCE(u.reading_position, '') != '' OR u.last_read_at IS NOT NULL)
                                    {nur_geteilt} AND {sicht}
                                    ORDER BY u.last_read_at DESC, b.title COLLATE NOCASE LIMIT ?""", (kind.id, *werte, HOECHSTENS))
    heute = (await lesezeit.stand(kind)).heute_s if "lesezeit" in sichtbar else None
    return Einblicksantwort(sichtbar=sichtbar, lesezeit_heute_s=heute, eintraege=[_eintrag(z, sichtbar) for z in zeilen])
