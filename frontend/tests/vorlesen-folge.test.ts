// Die Vorlesefolge mit nachgebautem Sprecher und Buch: Reihenfolge, Steuerung, Abriss, Schlafuhr, Mitlesen
import { lageAb, saetzeMitLage, stuecke } from "../src/lib/vorlesen/saetze";
import { mitPause } from "../src/lib/vorlesen/ton";
import { Vorlesefolge, type Folgegriffe } from "../src/lib/vorlesen/folge";
import { Vorlauf } from "../src/lib/vorlesen/vorlauf";
import type { Lesequelle, Satzort, Sprecher, Tonsatz } from "../src/lib/vorlesen/typen";
import { Textkarte } from "../src/lib/leser/textkarte";
import { kapitelUm } from "../src/lib/leser/kapitelgrenzen";

const ruhe = (n = 8) => new Array(n).fill(0).reduce((p) => p.then(() => new Promise((r) => setTimeout(r, 0))), Promise.resolve());

class Probesprecher implements Sprecher {
  tempo = 1;
  gespielt: string[] = [];
  anfragen: string[] = [];
  scheitert = 0;
  #fertig: (() => void) | null = null;
  pausiert = false;
  entsperre() {}
  async *saetze(text: string): AsyncIterable<Tonsatz> {
    this.anfragen.push(text);
    if (this.scheitert > 0) {
      this.scheitert--;
      throw new Error("Der Sprechdienst antwortet nicht");
    }
    for (const s of saetzeMitLage(text)) yield { ...s, ton: null, dauer: 2 };
  }
  spiele(satz: Tonsatz): Promise<void> {
    this.gespielt.push(satz.text);
    return new Promise((r) => (this.#fertig = r));
  }
  /** Der laufende Satz ist zu Ende gesprochen */
  ende() {
    const f = this.#fertig;
    this.#fertig = null;
    f?.();
  }
  pause() {
    this.pausiert = true;
  }
  weiter() {
    this.pausiert = false;
  }
  halt() {
    this.ende();
  }
}

const SEITEN = ["Eins a. Eins b.", "Zwei a. Zwei b. Zwei c.", "Drei a."];

function buch(sichtbar = () => true) {
  const markiert: (Satzort | null)[] = [];
  const gefuehrt: number[] = [];
  const quelle: Lesequelle = {
    anzahl: SEITEN.length, name: (e) => `Seite ${e + 1}`, text: async (e) => SEITEN[e],
    markiere: (o) => void markiert.push(o), fuehre: async (s) => void gefuehrt.push(s.einheit), sichtbar, kapitelende: async () => ({ einheit: 2, zeichen: 0 }),
  };
  return { quelle, markiert, gefuehrt };
}

function folge(o: { von?: [number, number]; bis?: [number, number] | null; sichtbar?: () => boolean } = {}) {
  const b = buch(o.sichtbar);
  const sprecher = new Probesprecher();
  const zustand: string[] = [];
  const griffe: Folgegriffe = { zustand: (z) => zustand.push(z.pausiert ? "pause" : z.wartet ? "wartet" : "spielt"), ende: vi.fn(), gerissen: vi.fn(), eingeschlafen: vi.fn() };
  const [von, bis] = [o.von ?? [0, 0], o.bis === undefined ? null : o.bis];
  const f = new Vorlesefolge(b.quelle, { von: { einheit: von[0], zeichen: von[1] }, bis: bis && { einheit: bis[0], zeichen: bis[1] } }, sprecher, "", new Vorlauf(), griffe, async () => {});
  const spiele = async (n: number) => {
    for (let i = 0; i < n; i++) {
      await ruhe();
      sprecher.ende();
    }
    await ruhe();
  };
  return { f, sprecher, griffe, zustand, spiele, ...b };
}

describe("Vorlesefolge", () => {
  it("liest Satz für Satz über die Seiten hinweg und meldet das Ende", async () => {
    const { sprecher, griffe, spiele, markiert } = folge();
    await spiele(6);
    expect(sprecher.gespielt).toEqual(["Eins a.", "Eins b.", "Zwei a.", "Zwei b.", "Zwei c.", "Drei a."]);
    expect(markiert.at(-1)).toBeNull();
    expect(markiert[2]).toEqual({ einheit: 1, von: 0, bis: 7 });
    expect(griffe.ende).toHaveBeenCalledOnce();
  });

  it("liest nur die Strecke, ab dem Anfang des Satzes", async () => {
    const { sprecher, spiele, griffe } = folge({ von: [1, 10], bis: [2, 0] });
    await spiele(4);
    expect(sprecher.gespielt).toEqual(["Zwei b.", "Zwei c."]);
    expect(griffe.ende).toHaveBeenCalled();
  });

  it("springt Satz und Seite vor und zurück", async () => {
    const { f, sprecher, spiele } = folge();
    await spiele(1);
    f.satzVor();
    await ruhe();
    f.satzZurueck();
    await ruhe();
    expect(sprecher.gespielt).toEqual(["Eins a.", "Eins b.", "Zwei a.", "Eins b."]);
    f.einheitVor();
    await ruhe();
    expect(sprecher.gespielt.at(-1)).toBe("Zwei a.");
    f.einheitZurueck();
    await ruhe();
    expect(sprecher.gespielt.at(-1)).toBe("Eins a.");
  });

  it("hält an und macht am selben Satz weiter", async () => {
    const { f, sprecher, zustand } = folge();
    await ruhe();
    f.pausiere();
    expect([sprecher.pausiert, zustand.at(-1)]).toEqual([true, "pause"]);
    f.weiter();
    expect([sprecher.pausiert, zustand.at(-1), sprecher.gespielt]).toEqual([false, "spielt", ["Eins a."]]);
  });

  it("reißt der Ton ab, steht sie still und setzt an derselben Stelle fort", async () => {
    const { f, sprecher, griffe, spiele } = folge();
    sprecher.scheitert = 9;
    await ruhe(20);
    expect(griffe.gerissen).toHaveBeenCalledWith("Der Sprechdienst antwortet nicht");
    expect(sprecher.anfragen.length).toBe(3);
    sprecher.scheitert = 0;
    f.weiter();
    await spiele(2);
    expect(sprecher.gespielt.slice(0, 2)).toEqual(["Eins a.", "Eins b."]);
  });

  it("schläft am Ende der Seite ein", async () => {
    const { f, sprecher, griffe, spiele } = folge();
    await ruhe();
    await f.setzeSchlaf({ art: "einheit" });
    await spiele(3);
    expect(sprecher.gespielt).toEqual(["Eins a.", "Eins b."]);
    expect(griffe.eingeschlafen).toHaveBeenCalledOnce();
  });

  it("führt die Ansicht nicht zurück, wenn man weggeblättert hat", async () => {
    let sicht = true;
    const { f, gefuehrt, spiele, zustand } = folge({ sichtbar: () => sicht });
    await spiele(1);
    const vorher = gefuehrt.length;
    sicht = false;
    f.bewegt();
    await spiele(1);
    expect(gefuehrt.length).toBe(vorher);
    expect(zustand.length).toBeGreaterThan(0);
    await f.zurStelle();
    expect(gefuehrt.length).toBe(vorher + 1);
  });
});

describe("Sätze und Stücke", () => {
  it("kennen ihre Lage im Text", () => {
    const t = "Ein Satz.  Noch einer!\n\nNeuer Absatz ohne Punkt\nund weiter";
    expect(saetzeMitLage(t).map((s) => [s.text, t.slice(s.von, s.bis)])).toEqual([["Ein Satz.", "Ein Satz."], ["Noch einer!", "Noch einer!"], ["Neuer Absatz ohne Punkt\nund weiter", "Neuer Absatz ohne Punkt\nund weiter"]]);
    expect(stuecke(t, 25).map((s) => s.text)).toEqual(["Ein Satz.  Noch einer!", "Neuer Absatz ohne Punkt\nund weiter"]);
  });

  it("finden einen Satz wieder, auch wenn der Leerraum anders ist", () => {
    const t = "Eins.\n\nZwei   drei.  Vier.";
    expect(lageAb(t, "Zwei drei.", 5)).toEqual([7, 19]);
    expect(lageAb(t, "Vier.", 19)).toEqual([21, 26]);
  });
});

describe("Ton", () => {
  it("hängt Stille an ein WAV und kennt dann seine Dauer", () => {
    const kopf = new Uint8Array(44 + 4800);
    const v = new DataView(kopf.buffer);
    [..."RIFF"].forEach((z, i) => v.setUint8(i, z.charCodeAt(0)));
    [..."WAVEfmt "].forEach((z, i) => v.setUint8(8 + i, z.charCodeAt(0)));
    [..."data"].forEach((z, i) => v.setUint8(36 + i, z.charCodeAt(0)));
    v.setUint32(16, 16, true);
    v.setUint32(24, 24000, true);
    v.setUint32(28, 48000, true);
    v.setUint16(32, 2, true);
    v.setUint32(40, 4800, true);
    const { ton, dauer } = mitPause(kopf.buffer, 0.3);
    expect([dauer, ton.size]).toEqual([0.4, 44 + 4800 + 14400]);
  });
});

describe("Textkarte", () => {
  it("trennt Blöcke durch eine Leerzeile, lässt Code und Tasten aus und findet zurück", () => {
    const d = document.createElement("div");
    d.innerHTML = "<p>Eins <b>zwei</b>.</p><pre>code()</pre><p>Drei<button>x</button>.</p>";
    const k = new Textkarte([d]);
    expect(k.text).toBe("Eins zwei.\n\nDrei.");
    expect(k.bereich(5, 9)?.toString()).toBe("zwei");
    expect(k.zeichenVon(d.querySelector("b")!.firstChild!, 2)).toBe(7);
    expect(k.stelle(10)?.knoten.data).toBe(".");
  });
});

describe("Kapitelgrenzen", () => {
  it("zählen die oberste Ebene mit genug Einträgen", () => {
    const k = [0, 1, 1, 1, 0, 1].map((tiefe, n) => ({ titel: `K${n}`, tiefe, ziel: n }));
    expect(kapitelUm(k, 2)).toEqual([2, 3]);
    expect(kapitelUm(k, 5)).toEqual([5, null]);
  });
});
