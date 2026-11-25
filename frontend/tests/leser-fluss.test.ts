// Die Blätterschicht, mit nachgebautem Umbruch: jede Zeile fasst ein paar Zeichen, ein Schirm ein paar Zeilen
import { Blaetterfluss, type Spaltensatz, type Umbruch } from "../src/lib/leser/fluss/blaettern";
import { Scrollfluss, type Scrollflaeche } from "../src/lib/leser/fluss/scrollen";
import { Textmass, type Anker, type Rechteck } from "../src/lib/leser/fluss/textmass";

const SCHRITT = 300;
const ZEILE = 20;

/** Ein Text in Absätzen, umbrochen in Zeilen zu `jeZeile` Zeichen, je Absatz eine neue Zeile */
class Satz implements Spaltensatz {
  wurzel = document.createElement("div");
  schirm = 0;
  mass: Textmass;

  constructor(absaetze: string[], public jeZeile: number, public jeSchirm: number) {
    for (const t of absaetze) this.wurzel.append(this.absatz(t));
    this.mass = new Textmass(this.wurzel, (a) => this.messe(a));
  }

  absatz(text: string): HTMLElement {
    const p = document.createElement("p");
    p.textContent = text;
    return p;
  }

  #zeileVon(a: Anker): number {
    let zeile = 0;
    for (const p of this.wurzel.children) {
      const t = p.firstChild as Text;
      if (t === a.knoten) return zeile + Math.floor(a.versatz / this.jeZeile);
      zeile += Math.ceil(t.data.length / this.jeZeile);
    }
    return zeile;
  }

  get zeilen(): number {
    return [...this.wurzel.children].reduce((n, p) => n + Math.ceil(p.textContent!.length / this.jeZeile), 0);
  }

  /** Im Satz: Spalten nebeneinander */
  messe(a: Anker): Rechteck {
    const zeile = this.#zeileVon(a);
    const links = Math.floor(zeile / this.jeSchirm) * SCHRITT + (a.versatz % this.jeZeile) * 5;
    const oben = (zeile % this.jeSchirm) * ZEILE;
    return { links, oben, rechts: links + 5, unten: oben + ZEILE };
  }

  richteEin(): Umbruch | null {
    return { schritt: SCHRITT, schirme: Math.max(1, Math.ceil(this.zeilen / this.jeSchirm)) };
  }
  zeige(schirm: number): void {
    this.schirm = schirm;
  }
  lageVon(e: Element): Rechteck | null {
    return this.messe({ knoten: e.firstChild!, versatz: 0 });
  }
}

const absaetze = (n: number, laenge = 90) => Array.from({ length: n }, (_, i) => `${i}`.padEnd(laenge, "x"));
const satz = (n = 10) => {
  const s = new Satz(absaetze(n), 10, 6);
  const bewegt = vi.fn();
  return { s, bewegt, f: new Blaetterfluss(s, s.mass, bewegt) };
};
const wo = (a: Anker | null) => (a ? `${a.knoten.textContent!.match(/^\d+/)}:${a.versatz}` : "");

describe("Geblättert", () => {
  it("zählt die Schirme und bleibt in ihren Grenzen", () => {
    const { s, f } = satz();
    expect(f.schirme).toBe(15);
    expect(f.amAnfang).toBe(true);
    expect(f.zurueck()).toBe(false);
    f.zuAnteil(1);
    expect([s.schirm, f.amEnde, f.vor(), f.anteil]).toEqual([14, true, false, 1]);
    f.zuAnteil(0);
    expect([s.schirm, f.anteil]).toEqual([0, 0]);
  });

  it("geht einen Schirm vor und zurück und meldet jede Bewegung", () => {
    const { s, f, bewegt } = satz();
    expect([f.vor(), f.vor(), s.schirm]).toEqual([true, true, 2]);
    expect(wo(f.stelle())).toBe("1:30");
    expect([f.zurueck(), s.schirm]).toEqual([true, 1]);
    expect(bewegt).toHaveBeenCalledTimes(3);
    expect([f.davor, f.danach]).toEqual([1, 13]);
  });

  it("springt auf den Schirm, der die Stelle trägt", () => {
    const { s, f } = satz();
    f.zu(s.wurzel.children[4]);
    expect(s.schirm).toBe(6);
    expect(wo(f.halt())).toBe("4:0");
    expect([f.erreicht(s.wurzel.children[4]), f.erreicht(s.wurzel.children[5])]).toEqual([true, false]);
  });

  it("hält die Stelle bei anderer Schrift und ist nach hin und zurück wieder auf demselben Schirm", () => {
    const { s, f } = satz();
    f.zuAnteil(0.5);
    const [schirm, halt] = [s.schirm, wo(f.halt())];
    s.jeZeile = 5;
    s.jeSchirm = 3;
    f.neu();
    expect(s.messe(f.halt()!).links).toBeGreaterThanOrEqual(s.schirm * SCHRITT);
    expect(s.messe(f.halt()!).links).toBeLessThan((s.schirm + 1) * SCHRITT);
    s.jeZeile = 10;
    s.jeSchirm = 6;
    f.neu();
    expect([s.schirm, wo(f.halt())]).toEqual([schirm, halt]);
  });

  it("bleibt beim Nachladen vorn auf derselben Stelle, auch wenn noch nie geblättert wurde", () => {
    const { s, f } = satz();
    f.halteFest();
    const vorher = wo(f.stelle());
    s.wurzel.prepend(s.absatz("neu".padEnd(120, "n")), s.absatz("neuer".padEnd(60, "n")));
    s.mass.veraltet();
    f.neu();
    expect([s.schirm, f.schirme]).toEqual([3, 18]);
    expect(wo(f.stelle())).toBe(vorher);
    expect(f.zurueck()).toBe(true);
  });

  it("bleibt beim Nachladen hinten stehen und kann danach weiter", () => {
    const { s, f } = satz(2);
    f.zuAnteil(1);
    const schirm = s.schirm;
    s.wurzel.append(s.absatz("mehr".padEnd(120, "m")));
    s.mass.veraltet();
    f.neu();
    expect(s.schirm).toBe(schirm);
    expect([f.amEnde, f.vor()]).toEqual([false, true]);
  });

  it("tut nichts, solange die Fläche keine Größe hat", () => {
    const { s, f } = satz();
    f.zuAnteil(0.5);
    const schirm = s.schirm;
    s.richteEin = () => null;
    f.neu();
    expect(s.schirm).toBe(schirm);
  });
});

/** Dieselben Zeilen untereinander auf einer scrollbaren Fläche */
class Flaeche implements Scrollflaeche {
  #stand = 0;
  #tun = () => {};
  readonly hoehe = 6 * ZEILE;
  readonly verdeckt = 0;
  constructor(private s: Satz) {
    s.mass = new Textmass(s.wurzel, (a) => this.lage(a));
  }
  lage(a: Anker): Rechteck {
    const r = this.s.messe(a);
    const oben = (r.links - (r.links % SCHRITT)) / SCHRITT * this.s.jeSchirm * ZEILE + r.oben;
    return { links: 0, oben, rechts: 5, unten: oben + ZEILE };
  }
  get stand(): number {
    return this.#stand;
  }
  set stand(wert: number) {
    const neu = Math.max(0, Math.min(this.inhalt - this.hoehe, wert));
    if (neu === this.#stand) return;
    this.#stand = neu;
    this.#tun();
  }
  get inhalt(): number {
    return this.s.zeilen * ZEILE;
  }
  lageVon(e: Element): Rechteck {
    return this.lage({ knoten: e.firstChild!, versatz: 0 });
  }
  beiBewegung(tun: () => void): () => void {
    this.#tun = tun;
    return () => (this.#tun = () => {});
  }
}

const rolle = () => {
  const s = new Satz(absaetze(10), 10, 6);
  const flaeche = new Flaeche(s);
  return { s, flaeche, f: new Scrollfluss(flaeche, s.mass, vi.fn()) };
};

describe("Gescrollt", () => {
  it("kennt Anfang, Ende und die oberste Stelle", () => {
    const { f, flaeche } = rolle();
    expect([f.amAnfang, f.anteil]).toEqual([true, 0]);
    flaeche.stand = 45 * ZEILE;
    expect(wo(f.stelle())).toBe("5:0");
    flaeche.stand = 10000;
    expect([f.amEnde, f.anteil, f.vor()]).toEqual([true, 1, false]);
  });

  it("hält die oberste Stelle beim Nachladen vorn", () => {
    const { s, f, flaeche } = rolle();
    flaeche.stand = 30 * ZEILE + 7;
    const [vorher, versatz] = [wo(f.stelle()), flaeche.lage(f.stelle()!).oben - flaeche.stand];
    f.halteFest();
    s.wurzel.prepend(s.absatz("neu".padEnd(200, "n")));
    s.mass.veraltet();
    f.neu();
    expect(wo(f.stelle())).toBe(vorher);
    expect(flaeche.lage(f.stelle()!).oben - flaeche.stand).toBe(versatz);
  });

  it("rührt den Stand nicht an, wenn nichts verrutscht ist", () => {
    const { f, flaeche } = rolle();
    flaeche.stand = 333;
    f.neu();
    expect(flaeche.stand).toBe(333);
  });
});

describe("Textmaß", () => {
  it("zählt Zeichen und Abbildungen, überspringt Tasten und Leerraum", () => {
    const d = document.createElement("div");
    d.innerHTML = "<p>abcde</p>  <p><button>nicht</button><img></p><p>fghi</p>";
    const m = new Textmass(d, () => ({ links: 0, oben: 0, rechts: 1, unten: 1 }));
    expect(m.laenge).toBe(10);
    expect(m.beiAnteil(0.5)).toMatchObject({ knoten: d.querySelector("img"), versatz: 0 });
    expect(m.anteil({ knoten: d.lastChild!.firstChild!, versatz: 2 })).toBeCloseTo(0.8);
    expect(m.anteil({ knoten: d.querySelector("button")!, versatz: 0 })).toBe(0.5);
  });

  it("merkt Umbauten, ohne dass jemand sie meldet", () => {
    const d = document.createElement("div");
    d.textContent = "abc";
    const m = new Textmass(d, () => null);
    expect(m.laenge).toBe(3);
    d.append("defg");
    expect(m.laenge).toBe(7);
  });
});
