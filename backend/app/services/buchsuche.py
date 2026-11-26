"""Suche im Text eines Buchs (BF-3): Treffer je Seite mit Ausschnitt und Lage, nie in der Ereignisschleife.

Ein gewöhnlicher Suchbegriff läuft in einem Faden (er wird maskiert und braucht nur einen Durchgang). Ein regulärer
Ausdruck kann sich festrechnen (verschachtelte Wiederholungen); er läuft darum in einem eigenen Prozess mit Zeitgrenze
(`SUCHE_AUSDRUCK_S`) und wird danach beendet, statt die App aufzuhalten. Dieses Modul braucht nur die Standardbibliothek,
damit der Prozess schnell steht; aufgerufen wird er als `python -m backend.app.services.buchsuche` mit den Seiten auf
stdin."""

from __future__ import annotations

import asyncio
import html
import json
import os
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[3]
UMFELD = 80                              # Zeichen vor und nach einem Treffer im Ausschnitt


def suchen(seiten: list[str], q: str, limit: int, ganzes_wort: bool, gross_klein: bool, regex: bool) -> dict:
    """`{treffer: [{seite, kontext, position, prozent}], gesamt, seiten_gesamt, suchbegriff, grund}`; der Buchtext im Ausschnitt
    ist entschärft, nur die Hervorhebung `<mark>` bleibt (BF-5)."""
    leer = {"treffer": [], "gesamt": 0, "seiten_gesamt": len(seiten), "suchbegriff": q, "grund": ""}
    muster = q if regex else re.escape(q)
    if ganzes_wort:
        muster = rf"\b(?:{muster})\b"
    try:
        ausdruck = re.compile(muster, 0 if gross_klein else re.IGNORECASE)
    except re.error as f:
        return leer | {"grund": f"Kein gültiger regulärer Ausdruck: {f}"}
    treffer, gesamt = [], 0
    laenge = sum(len(s) + 1 for s in seiten)
    versatz = 0
    for nr, seite in enumerate(seiten, 1):
        for m in ausdruck.finditer(seite):
            gesamt += 1
            if len(treffer) >= limit or m.end() == m.start():
                continue
            von, bis = max(0, m.start() - UMFELD), min(len(seite), m.end() + UMFELD)
            kontext = seite[von:bis].strip()
            teile, zuletzt = [], 0
            for k in ausdruck.finditer(kontext):
                if k.end() > k.start():
                    teile += [html.escape(kontext[zuletzt:k.start()], quote=False), f"<mark>{html.escape(k.group(), quote=False)}</mark>"]
                    zuletzt = k.end()
            markiert = ("..." if von > 0 else "") + "".join(teile) + html.escape(kontext[zuletzt:], quote=False) + ("..." if bis < len(seite) else "")
            treffer.append({"seite": nr, "kontext": markiert, "position": m.start(),
                            "prozent": round((versatz + m.start()) / laenge * 100, 1) if laenge else 0})
        versatz += len(seite) + 1
    return leer | {"treffer": treffer, "gesamt": gesamt}


async def suche(seiten: list[str], q: str, limit: int, ganzes_wort: bool, gross_klein: bool, regex: bool, zeitgrenze_s: float) -> dict:
    if not regex:
        return await asyncio.to_thread(suchen, seiten, q, limit, ganzes_wort, gross_klein, regex)
    prozess = await asyncio.create_subprocess_exec(
        sys.executable, "-m", __name__, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        cwd=WURZEL, env={**os.environ, "PYTHONPATH": str(WURZEL)})
    auftrag = json.dumps({"seiten": seiten, "q": q, "limit": limit, "ganzes_wort": ganzes_wort, "gross_klein": gross_klein}).encode()
    try:
        aus, fehler = await asyncio.wait_for(prozess.communicate(auftrag), zeitgrenze_s)
    except TimeoutError:
        prozess.kill()
        await prozess.wait()
        return {"treffer": [], "gesamt": 0, "seiten_gesamt": len(seiten), "suchbegriff": q,
                "grund": f"Der Ausdruck brauchte länger als {zeitgrenze_s:g} s und wurde abgebrochen; enger fassen hilft"}
    if prozess.returncode != 0:
        raise RuntimeError(f"Suche im Buch ging nicht: {fehler.decode(errors='replace')[-300:]}")
    return json.loads(aus)


if __name__ == "__main__":
    a = json.loads(sys.stdin.buffer.read())
    json.dump(suchen(a["seiten"], a["q"], a["limit"], a["ganzes_wort"], a["gross_klein"], True), sys.stdout, ensure_ascii=False)
