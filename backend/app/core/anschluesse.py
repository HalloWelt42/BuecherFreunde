"""Was an diese Installation angeschlossen ist: eine Stelle für Server und Oberfläche. Jeder Anschluss ist freiwillig; fehlt er,
läuft die App weiter, nur die Fähigkeit fehlt und wird nicht gezeigt."""

from __future__ import annotations

from pydantic import BaseModel

from backend.app.ablage.wolke import wolke
from backend.app.core.config import settings
from backend.app.services import nachschlagen


class Anschluesse(BaseModel):
    ablage: str                       # "kellerwolke" oder "geraet"
    anmeldung: str                    # "kellerwolke" oder "eigen"
    bedeutung: bool                   # Suche nach Bedeutung (Fundus)
    assistent: str                    # Adresse oder leer
    nachschlag: str                   # Adresse des Lexikons oder leer
    nachschlag_art: str               # "nachschlag" (Hausdienst), "netz" (öffentliches Lexikon) oder leer
    ki: bool                          # Sprachmodell für Einordnung und Vorschläge
    vorlesen: bool                    # Sprechdienst; die Stimmen des Geräts gehen immer
    ausfuehren: bool                  # Sandbox der Codeschmiede für Codestellen (Taste und Fenster); die Erkennung läuft immer


def anschluesse() -> Anschluesse:
    lexikon = nachschlagen.lexikon()
    return Anschluesse(ablage="kellerwolke" if wolke.bereit else "geraet", anmeldung="kellerwolke" if settings.kellerwolke_url else "eigen",
                       bedeutung=bool(settings.fundus_url), assistent=settings.assistent_url, nachschlag=lexikon.adresse if lexikon else "", nachschlag_art=lexikon.art if lexikon else "", ki=settings.lm_studio_enabled, vorlesen=bool(settings.vorlesen_url),
                       ausfuehren=bool(settings.codeschmiede_url.strip()))
