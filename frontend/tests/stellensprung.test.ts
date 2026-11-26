import { NAHE, NOCH_DORT, ordne, ziel } from "../src/lib/leser/stellensprung";
import type { Randeintrag } from "../src/lib/leser/randmarken";

const e = (schluessel: string, anteil: number | null): Randeintrag & { a: number | null } => ({
  schluessel, art: "Notiz", farbe: "#FFD54A", text: schluessel, ort: "", seite: null, prozent: null, cfi: "", quelle: {} as never, a: anteil,
});
const stellen = (...liste: [string, number | null][]) => ordne(liste.map(([s, a]) => e(s, a)), (x) => (x as ReturnType<typeof e>).a);
const name = (s: ReturnType<typeof ziel>) => s?.eintrag.schluessel ?? null;

describe("Vorige und nächste Stelle (BF-63)", () => {
  it("ordnet nach dem Anteil und lässt Stellen ohne Anteil weg", () => {
    expect(stellen(["c", 0.8], ["a", 0.1], ["x", null], ["b", 0.5]).map((s) => s.eintrag.schluessel)).toEqual(["a", "b", "c"]);
  });

  it("findet vom Stand aus die nächste und die vorige", () => {
    const s = stellen(["a", 0.1], ["b", 0.5], ["c", 0.8]);
    expect(name(ziel(s, 0.3, "", 1))).toBe("b");
    expect(name(ziel(s, 0.3, "", -1))).toBe("a");
    expect(name(ziel(s, 0.9, "", 1))).toBeNull();
    expect(name(ziel(s, 0.05, "", -1))).toBeNull();
  });

  it("eine Stelle genau am Stand ist hier, nicht davor oder danach", () => {
    const s = stellen(["a", 0.1], ["b", 0.5], ["c", 0.8]);
    expect(name(ziel(s, 0.5 + NAHE / 2, "", 1))).toBe("c");
    expect(name(ziel(s, 0.5 - NAHE / 2, "", -1))).toBe("a");
  });

  it("geht nach einem Sprung von der Stelle weiter, auch auf derselben Seite", () => {
    const s = stellen(["a", 0.1], ["b1", 0.5], ["b2", 0.5], ["c", 0.8]);
    expect(name(ziel(s, 0.5, "b1", 1))).toBe("b2");
    expect(name(ziel(s, 0.5, "b2", 1))).toBe("c");
    expect(name(ziel(s, 0.5, "b2", -1))).toBe("b1");
    expect(name(ziel(s, 0.5 + NOCH_DORT / 2, "b1", 1))).toBe("b2");
  });

  it("hat man sich weit davon bewegt, gilt wieder der Stand", () => {
    const s = stellen(["a", 0.1], ["b", 0.5], ["c", 0.8]);
    expect(name(ziel(s, 0.7, "a", 1))).toBe("c");
    expect(name(ziel(s, 0.7, "a", -1))).toBe("b");
  });
});
