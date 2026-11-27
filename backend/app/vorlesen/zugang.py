"""Der Weg zur Vertonung: Aufrufe über den Verbund des Appkerns (`appkern.verbund.Verbund`), angemeldet mit dem App-Zugang der
Kellerwolke dieser App (Kopf Authorization). BücherFreunde baut nicht auf dem Gerüst des Appkerns (`appkern.app.Geruest`); der
Verbund braucht von ihm nur drei Dinge, und die reicht `Gerueststelle` aus der eigenen Einrichtung: den App-Schlüssel aus dem
Schlüsselbund, die Zertifikatsstelle der Kellerwolke und die Prüfung der Zertifikate damit. Ändert sich Schlüssel oder
Zertifikatsstelle, baut der Verbund seine Verbindung selbst neu.

Die Adresse steht in `VERTONUNG_URL` oder, in der App eingetragen, unter den Anschlüssen (einrichtung/anschluesse.py)."""

from __future__ import annotations

import ssl

from appkern.verbund import Verbund, VerbundFehler
from appkern.vorlesen import VorlesenFehler, fehler_aus
from pydantic import SecretStr

from backend.app.ablage.wolke import _pruefung
from backend.app.core import schluessel
from backend.app.core.config import settings


class _Stand:
    """Was der Verbund aus den Einstellungen des Gerüsts liest, hier aus denen der App."""

    @property
    def kellerwolke_schluessel(self) -> SecretStr:
        return SecretStr(schluessel.lesen(schluessel.Art.KELLERWOLKE))

    @property
    def ca_datei(self) -> str:
        return settings.kellerwolke_ca


class _Einstellungen:
    stand = _Stand()


class Gerueststelle:
    """Steht für das Gerüst, soweit der Verbund es braucht; mehr kann sie nicht."""

    einstellungen = _Einstellungen()

    def tls_pruefung(self) -> ssl.SSLContext | bool:
        return _pruefung()                    # dieselbe Prüfung wie zur Kellerwolke: dieselbe Hausstelle


OHNE_ZUGANG = "Ohne App-Zugang der Kellerwolke kennt die Vertonung BücherFreunde nicht (Anschlüsse, Kellerwolke)"
NICHT_EINGERICHTET = "Es ist keine Vertonung angeschlossen (Anschlüsse, Vertonung)"

verbund = Verbund(Gerueststelle())        # type: ignore[arg-type] - nutzt vom Gerüst nur, was Gerueststelle hat


def adresse() -> str:
    return settings.vertonung_url.strip().rstrip("/")


def bereit() -> bool:
    """Eingetragen sind Adresse und App-Zugang der Kellerwolke; ob die Vertonung gerade antwortet, sagen die Verbindungen."""
    return bool(adresse() and schluessel.lesen(schluessel.Art.KELLERWOLKE))


def fehler(f: VerbundFehler) -> VorlesenFehler:
    """Ein Fehler des Verbunds als Grund für die Person, wie im Baustein des Appkerns (`appkern.vorlesen.fehler_aus`: nie 401,
    sonst meldete die Oberfläche ab); was dort nur "nicht eingerichtet" heißt, sagt hier, was fehlt (der Verbund sagt es, wenn
    Adresse oder App-Schlüssel fehlen; die Adresse nennt jeder Aufruf hier)."""
    if f.status is None and f.meldung == "nicht eingerichtet":
        return VorlesenFehler(NICHT_EINGERICHTET if schluessel.lesen(schluessel.Art.KELLERWOLKE) else OHNE_ZUGANG, 503)
    return fehler_aus(f)


def vorab_pruefen() -> None:
    """Vor einem Aufruf: ist die Vertonung eingetragen? Sonst ein `VorlesenFehler` mit dem, was fehlt."""
    if not adresse():
        raise VorlesenFehler(NICHT_EINGERICHTET, 503)
    if not bereit():
        raise VorlesenFehler(OHNE_ZUGANG, 503)
