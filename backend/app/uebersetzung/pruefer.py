"""Die zweite KI als Prüfer (BF-71, nach Sonnenlese lektorat.py): nach den festen Prüfungen bekommt eine eigene Anfrage, nach
Möglichkeit mit einem anderen Modell, Original und Übersetzung je Block und urteilt Satz für Satz: in Ordnung, oder ein
Mangel mit Art (Sinn, ausgelassen, hinzugefügt, Begriff, Grammatik), Grund und Stelle. Ein Mangel schickt den Block zur
Nacharbeit; der Prüfer selbst ändert nie etwas.

Wie beim Übersetzen: passt die Antwort nicht, wird halbiert; urteilt der Prüfer auch über einen einzelnen Block nicht
brauchbar, gilt das als Befund (Art "pruefer"), und der Block wird nie ungeprüft eingesetzt."""

from __future__ import annotations

import json
from collections.abc import Sequence

from backend.app.uebersetzung import anweisungen
from backend.app.uebersetzung.modelle import KI_ARTEN, Anfrage, Befund, Block, Unbrauchbar
from backend.app.uebersetzung.uebersetzen import Auftrag, begriffsangaben

UNBEURTEILT = "Der Prüfer hat zu diesem Block nicht brauchbar geantwortet"


def urteile_aus(roh: object, anzahl: int) -> list[Befund | None]:
    """Je Paar None (in Ordnung) oder ein Befund; wirft Unbrauchbar, wenn Form oder Anzahl nicht stimmen."""
    urteile = roh.get("urteile") if isinstance(roh, dict) else None
    if not isinstance(urteile, list) or len(urteile) != anzahl:
        raise Unbrauchbar(f"Die Antwort hat nicht genau {anzahl} Urteile")
    aus: list[Befund | None] = []
    for u in urteile:
        if not isinstance(u, dict) or not isinstance(u.get("in_ordnung"), bool):
            raise Unbrauchbar("Ein Urteil hat nicht die verlangte Form")
        if u["in_ordnung"]:
            aus.append(None)
            continue
        art = u.get("art") if u.get("art") in KI_ARTEN else "sinn"
        grund = " ".join(str(u.get("grund") or "").split())[:300] or "Der Prüfer nennt einen Mangel ohne Grund"
        aus.append(Befund(art=art, quelle="ki", text=grund, stelle=" ".join(str(u.get("stelle") or "").split())[:300]))
    return aus


async def pruefen_lassen(anfrage: Anfrage, paare: Sequence[tuple[Block, str]], auftrag: Auftrag) -> dict[str, Befund | None]:
    """Kennung -> None (in Ordnung) oder Befund (Mangel, oder kein brauchbares Urteil)."""
    if not paare:
        return {}
    daten = {"kapitel": auftrag.kapitel, **begriffsangaben(auftrag.begriffe, [b.vorlage for b, _ in paare]),
             "paare": [{"original": b.vorlage, "deutsch": d} for b, d in paare]}
    try:
        roh = await anfrage(anweisungen.pruefen(len(paare)), json.dumps(daten, ensure_ascii=False), schema_name="pruefung",
                            schema=anweisungen.schema_urteile(len(paare)), titel=auftrag.titel, modell=auftrag.modell)
        return {b.kennung: u for (b, _), u in zip(paare, urteile_aus(roh, len(paare)))}
    except Unbrauchbar:
        if len(paare) == 1:
            return {paare[0][0].kennung: Befund(art="pruefer", quelle="ki", text=UNBEURTEILT)}
        mitte = len(paare) // 2
        return await pruefen_lassen(anfrage, paare[:mitte], auftrag) | await pruefen_lassen(anfrage, paare[mitte:], auftrag)
