"""Nachschlagen der Lücken (BF-75): einmaliges neues Fragen nach einer Abkürzung."""

from __future__ import annotations


async def test_fragen_unter_einer_abkuerzung_werden_einmal_neu_gestellt(test_db):
    from backend.app.luecken import speicher
    from backend.app.luecken.dienst import abkuerzung
    sid = (await test_db.execute("INSERT INTO collections (name) VALUES ('Leuchtfeuerkai')")).lastrowid
    await test_db.execute("INSERT INTO reihe_sprache (sammlung_id, sprache, wahl, quelle, gefragt, stand, grund) "
                          "VALUES (?, 'de', 'quelle', 'dnb', 'LFK', 'fertig', 'Die Quelle kennt die Reihe nicht')", (sid,))
    await test_db.execute("INSERT INTO reihe_sprache (sammlung_id, sprache, wahl, quelle, gefragt, stand, grund) "
                          "VALUES (?, 'en', 'quelle', 'k10plus', 'Lighthouse Quay', 'fertig', 'Die Quelle kennt die Reihe nicht')", (sid,))
    assert await speicher.abkuerzungen_neu_fragen(abkuerzung) == 1
    staende = {z["sprache"]: z["stand"] for z in await test_db.fetch_all("SELECT sprache, stand FROM reihe_sprache WHERE sammlung_id = ?", (sid,))}
    assert staende == {"de": "offen", "en": "fertig"}                       # nur die Abkürzung, ein ausgeschriebener Name nicht
    await test_db.execute("UPDATE reihe_sprache SET stand = 'fertig' WHERE sammlung_id = ?", (sid,))
    assert await speicher.abkuerzungen_neu_fragen(abkuerzung) == 0         # nie wieder
