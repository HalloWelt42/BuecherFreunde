"""Sprechen über die Vertonung, nach dem Vertrag des Bausteins `appkern.vorlesen`:

- `zeilen`: der Strom `POST /api/v1/sprechen/strom` Satz für Satz (NDJSON, je Zeile `art` satz, ende oder fehler; `satz` mit
  `nr`, `text` und dem Ton als Base64-WAV in `ton`). Die Vertonung nimmt je Aufruf höchstens 8000 Zeichen; der Text geht darum in
  Teilen an Satzgrenzen (`appkern.vorlesen.teile`) nacheinander hinaus, die Sätze werden über alle Teile durchgezählt. Was vor dem
  ersten Satz scheitert, ist ein `VorlesenFehler` mit Grund und Status, danach kommt eine Zeile `fehler`. Bricht der Leser ab,
  endet die Anfrage und die Vertonung spricht nicht weiter.
- `ton`: ein kurzer Text als eine WAV (`POST /api/v1/sprechen`, bis 2000 Zeichen), für feste Ansagen und die Probe.

Anders als `appkern.vorlesen.Vorlesen.zeilen` nennt jeder Aufruf seine Stimme und seine Werte selbst: BücherFreunde liest je
Profil mit einer eigenen Stimme (die Vorlesestimme eines Erwachsenen, die Wahl der Eltern für ein Kind, die Stimme der Familie),
der Baustein kennt nur eine Stimme je App aus ihren Einstellungen. Die Form der Stimme und der Zeilen kommt aus dem Baustein."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

from appkern.verbund import VerbundFehler
from appkern.vorlesen import STROM, VorlesenFehler, fehlerzeile, stimmwahl, teile

from backend.app.vorlesen import zugang
from backend.app.vorlesen.modelle import Sprechwert

SPRECHEN = "/api/v1/sprechen"


def koerper(stimme: str, werte: Mapping[str, Sprechwert] | None = None) -> dict[str, Any]:
    """Was jeder Aufruf mitschickt: Zahlen und Abkürzungen ausgeschrieben (wie der Baustein), die Werte des Profils, die Stimme."""
    aus: dict[str, Any] = {"ausschreiben": True, **(werte or {})}
    if (wahl := stimmwahl(stimme)) is not None:
        aus["stimme"] = wahl
    return aus


def _zeile(daten: dict[str, Any]) -> bytes:
    return json.dumps(daten, ensure_ascii=False).encode() + b"\n"


async def zeilen(text: str, stimme: str, werte: Mapping[str, Sprechwert] | None = None) -> AsyncIterator[bytes]:
    """Die Zeilen der Vertonung für `text`, je Zeile mit Zeilenende, am Ende eine Zeile `ende`. `stimme`: wie die Vertonung sie
    schreibt, leer für ihre Stimme ab Werk."""
    zugang.vorab_pruefen()
    grund = koerper(stimme, werte)
    nr, dauer_ms = 0, 0
    try:
        for teil in teile(text):
            async with zugang.verbund.strom("POST", zugang.adresse(), STROM, json={**grund, "text": teil}) as antwort:
                async for roh in antwort.aiter_lines():
                    if not roh.strip():
                        continue
                    z = json.loads(roh)
                    if z.get("art") == "satz":
                        yield _zeile({**z, "nr": nr})
                        nr += 1
                        dauer_ms += int(z.get("dauer_ms") or 0)
                    elif z.get("art") == "fehler":
                        yield fehlerzeile(str(z.get("meldung") or "Vorlesen brach ab"))
                        return
        yield _zeile({"art": "ende", "saetze": nr, "dauer_ms": dauer_ms})
    except VerbundFehler as f:
        if not nr:
            raise zugang.fehler(f) from f
        yield fehlerzeile(f"Vorlesen brach ab: {f.meldung}")


async def ton(text: str, stimme: str, werte: Mapping[str, Sprechwert] | None = None) -> bytes:
    """Ein kurzer Text als WAV (16 Bit, 24 kHz mono, wie die Vertonung ihn liefert)."""
    zugang.vorab_pruefen()
    try:
        antwort = await zugang.verbund.anfrage("POST", zugang.adresse(), SPRECHEN, json={**koerper(stimme, werte), "text": text})
    except VerbundFehler as f:
        raise zugang.fehler(f) from f
    if not antwort.content:
        raise VorlesenFehler("Die Vertonung schickte keinen Ton", 502)
    return antwort.content
