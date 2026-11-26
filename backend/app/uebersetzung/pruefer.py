"""Die zweite KI als Prüfer (BF-71, nach Sonnenlese lektorat.py): nach den festen Prüfungen bekommt eine eigene Anfrage, nach
Möglichkeit mit einem anderen Modell, Original und Übersetzung je Block und urteilt Satz für Satz nur über den Inhalt: in
Ordnung, oder ein Mangel mit Art (Sinn, ausgelassen, hinzugefügt, Englisch stehen geblieben), Grund und Stelle. Der Prüfer
selbst ändert nie etwas.

Begriffe, Rechtschreibung, Zeichen und Anrede prüfen die festen Prüfungen. Der Prüfer bekommt die Begriffsliste darum nicht,
und ein Urteil anderer Art (Art "anderes", oder ein Grund, der sich auf eine Begriffsliste beruft) gilt nicht: es wird
verworfen und gezählt (`Urteil.verworfen`), der Block gilt als in Ordnung. Dasselbe gilt für Befunde aus der Zeit, als der
Prüfer auch über Begriffe und Grammatik urteilte (`gilt`).

Mehrfachprüfung (`urteilen`): Jeder Einwand geht vor der Nacharbeit an eine zweite, unabhängige Anfrage (`bestaetigen_lassen`,
eigene Anweisung, das Prüfmodell), die Original, Übersetzung, Art und Stelle bekommt, nicht die Begründung des ersten
Prüfers, und nur entscheidet, ob an der Stelle ein echter Mangel ist. Die Einwände einer Portion gehen zusammen hinaus.
Nur ein bestätigter Einwand gilt (`Befund.bestaetigung` trägt den Grund der zweiten Prüfung) und schickt den Block zur
Nacharbeit; ein nicht bestätigter wird verworfen und gezählt. Ein Einwand "englisch", an dessen Stelle nichts Englisches
aus dem Original steht, das nicht englisch bleiben darf (Begriffsliste, eingeführte Fachwörter, pruefen.py), wird ohne
Anfrage verworfen: die Begriffsliste ist die eine Wahrheit darüber, was englisch bleibt.

Wie beim Übersetzen: passt eine Antwort nicht, wird halbiert. Urteilt der Prüfer auch über einen einzelnen Block nicht
brauchbar, gilt das als Befund (Art "pruefer"), und der Block wird nie ungeprüft eingesetzt; antwortet die zweite Prüfung
zu einem einzelnen Einwand nicht brauchbar, bleibt der Einwand stehen."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from pydantic import BaseModel

from backend.app.uebersetzung import anweisungen, marken
from backend.app.uebersetzung.modelle import KI_ARTEN, Anfrage, Befund, Block, Unbrauchbar
from backend.app.uebersetzung.pruefen import englisch_aus_dem_original
from backend.app.uebersetzung.uebersetzen import Auftrag

UNBEURTEILT = "Der Prüfer hat zu diesem Block nicht brauchbar geantwortet"
OHNE_ZWEITE = "Die zweite Prüfung hat nicht brauchbar geantwortet; der Einwand bleibt"
#: ein Grund, der sich auf eine Liste beruft, ist ein Urteil über Begriffe, auch wenn der Prüfer es anders nennt
BERUFT_SICH_AUF_LISTE = re.compile(r"Begriffsliste|Glossar|Liste der Begriffe", re.I)


class Urteil(BaseModel):
    """Was der Prüfer zu einem Block sagt: ein Mangel (None: in Ordnung) und wie viele Einwände verworfen sind."""
    mangel: Befund | None = None
    verworfen: int = 0


class Entscheidung(BaseModel):
    """Was die zweite Prüfung zu einem Einwand sagt."""
    berechtigt: bool
    grund: str


def von_der_art(b: Befund) -> bool:
    """Ob ein Einwand des Prüfers von der Art ist, über die er urteilt: Sinn, Ausgelassenes, Hinzugefügtes, Englisch, ohne
    Berufung auf eine Begriffsliste."""
    return b.art in KI_ARTEN and not BERUFT_SICH_AUF_LISTE.search(b.text)


def gilt(b: Befund) -> bool:
    """Ob ein Befund zählt: Befunde der festen Prüfungen immer, ebenso ein Prüfer, der nicht brauchbar antwortete; ein Einwand
    des Prüfers nur, wenn er von der Art ist, über die der Prüfer urteilt, und die zweite Prüfung ihn bestätigt hat."""
    if b.quelle != "ki" or b.art == "pruefer":
        return True
    return von_der_art(b) and bool(b.bestaetigung)


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
    """Kennung -> Urteil des ersten Prüfers (in Ordnung, Mangel, oder kein brauchbares Urteil als Mangel der Art "pruefer")."""
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


def entscheidungen_aus(roh: object, anzahl: int) -> list[Entscheidung]:
    """Je Einwand eine Entscheidung; wirft Unbrauchbar, wenn Form oder Anzahl nicht stimmen."""
    liste = roh.get("entscheidungen") if isinstance(roh, dict) else None
    if not isinstance(liste, list) or len(liste) != anzahl:
        raise Unbrauchbar(f"Die Antwort hat nicht genau {anzahl} Entscheidungen")
    if not all(isinstance(e, dict) and isinstance(e.get("berechtigt"), bool) for e in liste):
        raise Unbrauchbar("Eine Entscheidung hat nicht die verlangte Form")
    return [Entscheidung(berechtigt=e["berechtigt"], grund=" ".join(str(e.get("grund") or "").split())[:300]) for e in liste]


async def bestaetigen_lassen(anfrage: Anfrage, faelle: Sequence[tuple[Block, str, Befund]], auftrag: Auftrag) -> dict[str, Entscheidung]:
    """Kennung -> Entscheidung der zweiten Prüfung zu je einem Einwand (Block, Übersetzung, Einwand). Die Begründung des ersten
    Prüfers geht nicht mit. Ohne brauchbare Antwort zu einem einzelnen Einwand bleibt er stehen."""
    if not faelle:
        return {}
    daten = {"kapitel": auftrag.kapitel,
             "faelle": [{"original": marken.fuer_modell(b.vorlage), "deutsch": marken.fuer_modell(d), "art": e.art,
                         "stelle": e.stelle} for b, d, e in faelle]}
    try:
        roh = await anfrage(anweisungen.bestaetigen(len(faelle)), json.dumps(daten, ensure_ascii=False), schema_name="bestaetigung",
                            schema=anweisungen.schema_entscheidungen(len(faelle)), titel=auftrag.titel, modell=auftrag.modell)
        return {b.kennung: e for (b, _, _), e in zip(faelle, entscheidungen_aus(roh, len(faelle)))}
    except Unbrauchbar:
        if len(faelle) == 1:
            return {faelle[0][0].kennung: Entscheidung(berechtigt=True, grund=OHNE_ZWEITE)}
        mitte = len(faelle) // 2
        return await bestaetigen_lassen(anfrage, faelle[:mitte], auftrag) | await bestaetigen_lassen(anfrage, faelle[mitte:], auftrag)


def ohne_anlass(b: Befund, original: str, auftrag: Auftrag) -> bool:
    """Ein Einwand "englisch", an dessen Stelle nichts Englisches aus dem Original steht, das übersetzt werden muss."""
    return b.art == "englisch" and not englisch_aus_dem_original(b.stelle, original, auftrag.begriffe)


async def urteilen(anfrage: Anfrage, paare: Sequence[tuple[Block, str]], pruefauftrag: Auftrag,
                   bestaetigung: Auftrag) -> dict[str, Urteil]:
    """Kennung -> Urteil nach der Mehrfachprüfung: der erste Prüfer, dann die zweite Prüfung über jeden seiner Einwände (siehe
    oben). Ein Mangel, der gilt, trägt die Bestätigung; ein verworfener Einwand zählt in `verworfen`."""
    urteile = await pruefen_lassen(anfrage, paare, pruefauftrag)
    je = {b.kennung: (b, d) for b, d in paare}
    faelle = []
    for kennung, u in list(urteile.items()):
        if u.mangel is None or u.mangel.art == "pruefer":
            continue
        if ohne_anlass(u.mangel, je[kennung][0].vorlage, pruefauftrag):
            urteile[kennung] = Urteil(verworfen=u.verworfen + 1)
        else:
            faelle.append((*je[kennung], u.mangel))
    for kennung, e in (await bestaetigen_lassen(anfrage, faelle, bestaetigung)).items():
        u = urteile[kennung]
        assert u.mangel is not None
        urteile[kennung] = (Urteil(mangel=u.mangel.model_copy(update={"bestaetigung": e.grund or "bestätigt"}), verworfen=u.verworfen)
                            if e.berechtigt else Urteil(verworfen=u.verworfen + 1))
    return urteile
