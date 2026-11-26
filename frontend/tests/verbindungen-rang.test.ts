import { nachRang } from "../src/lib/stand/verbindungen.svelte";
import type { Verbindung } from "../src/lib/typen";

const v = (kennung: string): Verbindung => ({ kennung, name: kennung, stand: "gut", text: "" }) as Verbindung;

describe("Reihenfolge der Verbindungen (BF-64)", () => {
  it("ordnet nach Bedeutung, wie auch immer der Server sie liefert", () => {
    const liste = ["nachschlag", "kellerwolke", "fundus", "assistent", "codeschmiede", "leitstelle"].map(v);
    expect(nachRang(liste).map((x) => x.kennung)).toEqual(["kellerwolke", "leitstelle", "fundus", "codeschmiede", "assistent", "nachschlag"]);
  });

  it("stellt Unbekanntes in seiner Reihenfolge ans Ende", () => {
    expect(nachRang(["neu2", "fundus", "neu1", "kellerwolke"].map(v)).map((x) => x.kennung)).toEqual(["kellerwolke", "fundus", "neu2", "neu1"]);
  });
});
