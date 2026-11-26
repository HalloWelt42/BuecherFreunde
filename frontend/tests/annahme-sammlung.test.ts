// BF-8: Einlesen aus Ordnern und gemeinfreie Übernahme sind Einträge der einen Annahme, als Auftrag zusammengefasst
import { EINLESEN, EINZELN, ERLEDIGT, GEMEINFREI, WARTEND, gehoertZu, inArbeit, sammle } from "../src/lib/annahme/sammlung";
import type { AnnahmeEintrag } from "../src/lib/annahme/typen";

function eintrag(ueber: Partial<AnnahmeEintrag>): AnnahmeEintrag {
  return { id: 1, name: "Buch.pdf", groesse: 1000, sha256: "", empfangen: 1000, teil_groesse: 4, stand: "liest", schritt: 2, anteil: 1, text: "Wartet auf das Lesen", buch_id: null, quelle: "ordner", angelegt_am: "", geaendert_am: "", ...ueber };
}

const liste: AnnahmeEintrag[] = [
  eintrag({ id: 9, quelle: "hochladen", stand: "laedt" }),
  eintrag({ id: 3, stand: "fertig", buch_id: 30, text: "Fertig" }),
  eintrag({ id: 4, stand: "da", buch_id: 12, text: "Gibt es schon" }),
  eintrag({ id: 5, stand: "kaputt", text: "Leer" }),
  eintrag({ id: 6, stand: "angaben", text: "Angaben werden ergänzt" }),
  eintrag({ id: 7 }),
  eintrag({ id: 8, quelle: "extern" }),
  eintrag({ id: 10, quelle: "gemeinfrei", name: "Faust.epub", text: "Wartet auf das Holen", groesse: 0, empfangen: 0 }),
  eintrag({ id: 2, quelle: "gemeinfrei", stand: "fertig", buch_id: 40 }),
];

describe("Aufträge aus der Annahme", () => {
  it("die Annahme arbeitet nach Nummer: der kleinste beim Server läuft, der Rest wartet", () => {
    expect(inArbeit(liste)).toBe(6);
    const s = sammle(liste, EINLESEN);
    expect(s.aktuell?.id).toBe(6);
    expect([s.gesamt, s.imRegal, s.da, s.gescheitert, s.wartend, s.erledigt]).toEqual([6, 1, 1, 1, 2, 3]);
    expect(s.laeuft).toBe(true);
    expect(s.eintraege.map((e) => e.id)).toEqual([3, 4, 5, 6, 7, 8]);
  });

  it("gemeinfrei wartet, solange die Annahme an einem anderen Eintrag arbeitet", () => {
    const g = sammle(liste, GEMEINFREI);
    expect(g.aktuell).toBe(null);
    expect([g.gesamt, g.imRegal, g.wartend]).toEqual([2, 1, 1]);
    expect(g.laeuft).toBe(true);
  });

  it("zählt mit den Zahlen des Servers alle Einträge, auch über die gelieferten hinaus", () => {
    const zahlen = { ordner: { gesamt: 900, laeuft: 600, fertig: 250, da: 30, gescheitert: 20 }, extern: { gesamt: 4, laeuft: 1, fertig: 3, da: 0, gescheitert: 0 } };
    const s = sammle(liste, EINLESEN, zahlen);
    expect([s.gesamt, s.imRegal, s.da, s.gescheitert, s.erledigt, s.wartend, s.weitere]).toEqual([904, 253, 30, 20, 303, 600, 898]);
    expect(s.aktuell?.id).toBe(6);
  });

  it("räumt am Server nach Stand auf: Erledigtes oder Wartendes", () => {
    expect(ERLEDIGT).toEqual(["wissen", "fertig", "ohne_text", "da", "fehler", "kaputt", "format"]);
    expect(WARTEND).toEqual(["liest"]);
  });

  it("einzeln bleiben Hochladen und Eingangsordner, auch ältere Einträge ohne Quelle", () => {
    expect(gehoertZu(eintrag({ quelle: "eingangsordner" }), EINZELN)).toBe(true);
    expect(gehoertZu({ ...eintrag({}), quelle: undefined } as unknown as AnnahmeEintrag, EINZELN)).toBe(true);
    expect(gehoertZu(eintrag({}), EINZELN)).toBe(false);
  });

  it("fertig, wenn nichts mehr ansteht", () => {
    const s = sammle([eintrag({ id: 1, stand: "fertig" }), eintrag({ id: 2, stand: "fehler" })], EINLESEN);
    expect(s.laeuft).toBe(false);
    expect(s.erledigt).toBe(2);
  });
});
