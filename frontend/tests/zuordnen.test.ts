// Zuordnen in zwei Spalten (BF-67): Reihenfolge beim Ziehen, Ziele Sammlung und Regal, Haken. Nur erfundene Titel und Namen.
import { gleich, neueNummern, ordne, vergibtNeu } from "../src/ansichten/zuordnen/reihenfolge";
import { regalziel, sammlungsziel, zielAus } from "../src/ansichten/zuordnen/ziel";
import { titelliste, Zuordnung } from "../src/ansichten/zuordnen/zuordnung.svelte";
import type { Buch } from "../src/lib/typen";

function buch(id: number, title: string, mehr: Partial<Buch> = {}): Buch {
  return {
    id, hash: "", title, author: "Jorin Sandvik", publisher: "", file_format: "epub", file_size: 1, cover_path: "", page_count: 0, year: null, isbn: "", typ: "", gattung: "",
    umschlag: "titelseite", umschlag_schlicht: false, umschlag_wahl: "", sammlung_id: null, band_nummer: "", is_favorite: false, is_to_read: false, rating: 0,
    reading_position: "", last_read_at: null, categories: [], sammlung: null, created_at: "", updated_at: "", ...mehr,
  };
}

describe("Reihenfolge beim Ziehen", () => {
  it("stellt Gezogenes vor das Ziel, mehrere zusammen in ihrer Folge", () => {
    expect(ordne([1, 2, 3, 4, 5], [4], 2)).toEqual([1, 4, 2, 3, 5]);
    expect(ordne([1, 2, 3, 4, 5], [1], null)).toEqual([2, 3, 4, 5, 1]);
    expect(ordne([1, 2, 3, 4, 5], [2, 4], 1)).toEqual([2, 4, 1, 3, 5]);
    expect(ordne([1, 2, 3, 4, 5], [5, 1], 3)).toEqual([2, 5, 1, 3, 4]);
  });

  it("nimmt Neue aus dem Bestand an der Stelle auf", () => {
    expect(ordne([1, 2, 3], [9, 8], 2)).toEqual([1, 9, 8, 2, 3]);
    expect(ordne([1, 2, 3], [9], null)).toEqual([1, 2, 3, 9]);
  });

  it("landet auf sich selbst vor dem nächsten nicht gezogenen", () => {
    expect(ordne([1, 2, 3, 4], [2, 3], 2)).toEqual([1, 2, 3, 4]);
    expect(ordne([1, 2, 3, 4], [3, 4], 4)).toEqual([1, 2, 3, 4]);
    expect(gleich(ordne([1, 2, 3], [2], 3), [1, 2, 3])).toBe(true);
  });

  it("fragt vor dem Durchzählen nur, wenn Nummern verloren gehen", () => {
    const b = (id: number, band_nummer: string) => ({ id, title: `Titel ${id}`, band_nummer });
    expect(vergibtNeu([b(1, "1"), b(2, "2"), b(3, "3")])).toBe(false);
    expect(vergibtNeu([b(1, "1"), b(2, "12")])).toBe(true);
    expect(vergibtNeu([b(1, "1"), b(2, "")])).toBe(true);
    expect(neueNummern([b(1, "1"), b(2, "12"), b(3, "13")], [1, 3, 2])).toEqual([
      { titel: "Titel 3", alt: "13", neu: "2" },
      { titel: "Titel 2", alt: "12", neu: "3" },
    ]);
  });
});

describe("Zuordnen", () => {
  it("kennt Sammlung und Regal aus der Adresse", () => {
    expect(zielAus("sammlung", "7")?.art).toBe("sammlung");
    expect(zielAus("regal", "3")?.art).toBe("regal");
    expect(zielAus("etwas", "3")).toBeNull();
    expect(zielAus("regal", "x")).toBeNull();
  });

  it("ordnet nur in der Sammlung um, heraus geht aus beiden", () => {
    const sammlung = new Zuordnung(sammlungsziel(7));
    const regal = new Zuordnung(regalziel(3));
    expect(sammlung.nimmt("drin", "drin")).toBe(true);
    expect(regal.nimmt("drin", "drin")).toBe(false);
    expect(regal.nimmt("uebrig", "drin")).toBe(true);
    expect(regal.nimmt("drin", "uebrig")).toBe(true);
    expect(regal.nimmt("uebrig", "uebrig")).toBe(false);
  });

  it("zieht angehakte zusammen, sonst nur das eine", () => {
    const z = new Zuordnung(regalziel(3));
    z.drin.liste = [buch(1, "a"), buch(2, "b"), buch(3, "c")];
    z.hakeAn("drin", 3, true);
    z.hakeAn("drin", 1, true);
    expect(z.gezogene("drin", 3)).toEqual([1, 3]);
    expect(z.gezogene("drin", 2)).toEqual([2]);
  });

  it("zeigt im Bestand einer Sammlung nicht, was schon drin ist", () => {
    const z = new Zuordnung(sammlungsziel(7));
    z.uebrig.liste = [buch(1, "a", { sammlung_id: 7 }), buch(2, "b"), buch(3, "c", { sammlung_id: 9 })];
    expect(z.rechts.map((b) => b.id)).toEqual([2, 3]);
  });

  it("nennt Folgen, wenn Bücher eine andere Sammlung verlassen", () => {
    const ziel = sammlungsziel(7);
    expect(ziel.folgenDazu([buch(2, "b")])).toEqual([]);
    expect(ziel.folgenDazu([buch(3, "c", { sammlung_id: 9, sammlung: { id: 9, name: "Glutreihe" } })])[0]).toBe("1 Buch verlässt die Sammlung Glutreihe samt Bandnummer.");
    expect(regalziel(3).folgenDazu([buch(3, "c", { sammlung_id: 9 })])).toEqual([]);
    expect(ziel.folgenHeraus(1)[0]).toBe("Das Buch verliert die Sammlung und seine Bandnummer.");
    expect(regalziel(3).folgenHeraus(2)[1]).toBe("Die Bücher selbst bleiben in der Bibliothek.");
  });

  it("kürzt lange Titellisten", () => {
    const b = (n: number) => ({ title: `T${n}` });
    expect(titelliste([b(1), b(2)])).toBe("T1, T2");
    expect(titelliste([1, 2, 3, 4, 5, 6, 7].map(b))).toBe("T1, T2, T3, T4, T5 und 2 weitere");
  });
});
