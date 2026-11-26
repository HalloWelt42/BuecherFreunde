"""Rechte aus Rolle und Stufe (BF-78): was ein Profil darf, steht in stufen.json; hier wird es nur gelesen. Verwaltung und
Erwachsen haben die Fähigkeiten ihrer Rolle, ein Kind die seiner Stufe.

Profile ändern: die Verwaltung (Fähigkeit `profile`) alle; ein Erwachsener sich selbst und die Kinder der Familie (es gibt
keine engere Zuordnung von Eltern zu Kindern), anlegen nur Kinder; niemand macht sich selbst zur Verwaltung."""

from __future__ import annotations

from backend.app.familie.modelle import Profil
from backend.app.familie.stufen import Rollenname, stufenbuch


def faehigkeiten(p: Profil) -> frozenset[str]:
    sb = stufenbuch()
    if p.kind:
        return frozenset(sb.stufe(p.stufe).faehigkeiten) if p.stufe and sb.hat_stufe(p.stufe) else frozenset()
    return frozenset(sb.rollen[p.rolle].faehigkeiten)


def darf(p: Profil, faehigkeit: str) -> bool:
    return faehigkeit in faehigkeiten(p)


def lesezeichen_je_buch(p: Profil) -> int | None:
    """Wie viele Lesezeichen ein Profil je Buch setzen darf; leer: so viele, wie es will."""
    return stufenbuch().stufe(p.stufe).lesezeichen_je_buch if p.kind and p.stufe else None


def darf_anlegen(von: Profil, rolle: Rollenname) -> bool:
    return darf(von, "profile") or (von.erwachsen and rolle == "kind")


def darf_aendern(von: Profil, ziel: Profil, neue_rolle: Rollenname | None) -> bool:
    if darf(von, "profile"):
        return True
    if not von.erwachsen:
        return False
    if ziel.id == von.id:
        return neue_rolle in (None, ziel.rolle)
    return ziel.kind and neue_rolle in (None, "kind")


def darf_pin_setzen(von: Profil, ziel: Profil) -> bool:
    """Die eigene PIN jeder; fremde die Verwaltung, die eines Kindes auch ein Erwachsener."""
    return von.id == ziel.id or darf(von, "profile") or (von.erwachsen and ziel.kind)


def darf_einsehen(von: Profil, ziel: Profil) -> bool:
    """Freigaben und Einblick eines Kindes: das Kind selbst und Erwachsene, die freigeben dürfen."""
    return von.id == ziel.id or (ziel.kind and darf(von, "freigeben")) or darf(von, "profile")
