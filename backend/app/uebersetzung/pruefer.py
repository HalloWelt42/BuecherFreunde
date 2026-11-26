"""Die zweite KI als Prüfer (BF-71, nach Sonnenlese lektorat.py): nach den festen Prüfungen bekommt eine eigene Anfrage, nach
Möglichkeit mit einem anderen Modell, Original und Übersetzung je Block und urteilt Satz für Satz nur über den Inhalt: in
Ordnung, oder ein Mangel mit Art (Sinn, ausgelassen, hinzugefügt), Grund und Stelle. Ein Mangel schickt den Block zur
Nacharbeit; der Prüfer selbst ändert nie etwas.

Begriffe, Rechtschreibung, Zeichen und Anrede prüfen die festen Prüfungen. Der Prüfer bekommt die Begriffsliste darum nicht,
und ein Urteil anderer Art (Art "anderes", oder ein Grund, der sich auf eine Begriffsliste beruft) gilt nicht: es wird
verworfen und gezählt (`Urteil.verworfen`), der Block gilt als in Ordnung. Dasselbe gilt für Befunde aus der Zeit, als der
Prüfer auch über Begriffe und Grammatik urteilte (`gilt`).

Wie beim Übersetzen: passt die Antwort nicht, wird halbiert; urteilt der Prüfer auch über einen einzelnen Block nicht
brauchbar, gilt das als Befund (Art "pruefer"), und der Block wird nie ungeprüft eingesetzt."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from pydantic import BaseModel

from backend.app.uebersetzung import anweisungen, marken
from backend.app.uebersetzung.modelle import KI_ARTEN, Anfrage, Befund, Block, Unbrauchbar
from backend.app.uebersetzung.uebersetzen import Auftrag

UNBEURTEILT = "Der Prüfer hat zu diesem Block nicht brauchbar geantwortet"
#: ein Grund, der sich auf eine Liste beruft, ist ein Urteil über Begriffe, auch wenn der Prüfer es anders nennt
BERUFT_SICH_AUF_LISTE = re.compile(r"Begriffsliste|Glossar|Liste der Begriffe", re.I)


class Urteil(BaseModel):
    """Was der Prüfer zu einem Block sagt: ein Mangel (None: in Ordnung) und wie viele Einwände anderer Art verworfen sind."""
    mangel: Befund | None = None
    verworfen: int = 0


def gilt(b: Befund) -> bool:
    """Ob ein Befund des Prüfers zählt: nur Sinn, Ausgelassenes und Hinzugefügtes, ohne Berufung auf eine Begriffsliste, und
    ein Prüfer, der nicht brauchbar antwortete. Befunde der festen Prüfungen zählen immer."""
    if b.quelle != "ki" or b.art == "pruefer":
        return True
    return b.art in KI_ARTEN and not BERUFT_SICH_AUF_LISTE.search(b.text)


def urteile_aus(roh: object, anzahl: int) -> list[Urteil]:
    """Je Paar ein Urteil; wirft Unbrauchbar, wenn Form oder Anzahl nicht stimmen."""
    urteile = roh.get("urteile") if isinstance(roh, dict) else None
    if not isinstance(urteile, list) or len(urteile) != anzahl:
        raise Unbrauchbar(f"Die Antwort hat nicht genau {anzahl} Urteile")
    aus: list[Urteil] = []
    for u in urteile:
        if not isinstance(u, dict) or not isinstance(u.get("in_ordnung"), bool):
            raise Unbrauchbar("Ein Urteil hat nicht die verlangte Form")
        if u["in_ordnung"]:
            aus.append(Urteil())
            continue
        art = u.get("art") or "sinn"                 # ein Mangel ohne Art ist einer am Sinn
        art = art if art in KI_ARTEN else anweisungen.ANDERES
        grund = " ".join(str(u.get("grund") or "").split())[:300] or "Der Prüfer nennt einen Mangel ohne Grund"
        if art == anweisungen.ANDERES or BERUFT_SICH_AUF_LISTE.search(grund):
            aus.append(Urteil(verworfen=1))
            continue
        aus.append(Urteil(mangel=Befund(art=art, quelle="ki", text=grund, stelle=" ".join(str(u.get("stelle") or "").split())[:300])))
    return aus


async def pruefen_lassen(anfrage: Anfrage, paare: Sequence[tuple[Block, str]], auftrag: Auftrag) -> dict[str, Urteil]:
    """Kennung -> Urteil (in Ordnung, Mangel, oder kein brauchbares Urteil als Mangel der Art "pruefer")."""
    if not paare:
        return {}
    daten = {"kapitel": auftrag.kapitel,
             "paare": [{"original": marken.fuer_modell(b.vorlage), "deutsch": marken.fuer_modell(d)} for b, d in paare]}
    try:
        roh = await anfrage(anweisungen.pruefen(len(paare)), json.dumps(daten, ensure_ascii=False), schema_name="pruefung",
                            schema=anweisungen.schema_urteile(len(paare)), titel=auftrag.titel, modell=auftrag.modell)
        return {b.kennung: u for (b, _), u in zip(paare, urteile_aus(roh, len(paare)))}
    except Unbrauchbar:
        if len(paare) == 1:
            return {paare[0][0].kennung: Urteil(mangel=Befund(art="pruefer", quelle="ki", text=UNBEURTEILT))}
        mitte = len(paare) // 2
        return await pruefen_lassen(anfrage, paare[:mitte], auftrag) | await pruefen_lassen(anfrage, paare[mitte:], auftrag)
