// BF-106: Beim Vorlesen folgt die gescrollte Ansicht der gelesenen Zeile wie eine gedämpfte Feder: gleichmäßig, ohne Ruck
// und ohne Überschwingen, auch wenn die Zeile mitten in der Bewegung weiterrückt.
import { feder, Mitlauf } from "../src/lib/leser/mitlauf";

describe("Feder", () => {
  it("kommt an, ohne über das Ziel zu schwingen", () => {
    let [lage, tempo] = [0, 0];
    const lagen: number[] = [];
    for (let i = 0; i < 240; i++) {
      [lage, tempo] = feder(lage, tempo, 100, 1 / 60);
      lagen.push(lage);
    }
    expect(Math.max(...lagen)).toBeLessThanOrEqual(100.0001);
    expect(lagen.every((l, i) => i === 0 || l >= lagen[i - 1])).toBe(true);
    expect(lagen.at(-1)!).toBeGreaterThan(99.5);
  });
});

describe("Mitlauf", () => {
  let bilder: FrameRequestCallback[] = [];
  let uhr = 0;
  const bild = () => {
    uhr += 1000 / 60;
    const jetzt = bilder;
    bilder = [];
    for (const b of jetzt) b(uhr);
  };
  beforeEach(() => {
    bilder = [];
    uhr = 0;
    vi.stubGlobal("requestAnimationFrame", (b: FrameRequestCallback) => (bilder.push(b), bilder.length));
    vi.stubGlobal("cancelAnimationFrame", () => (bilder = []));
    vi.spyOn(performance, "now").mockImplementation(() => uhr);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("gleitet Zeile um Zeile ohne Sprung und kommt an", () => {
    const bahn = { stand: 0, hoehe: 1000 };
    const m = new Mitlauf(bahn);
    m.folge(600, 630, false);                                   // unter der Mitte: 150 Pixel nachführen
    const staende: number[] = [];
    for (let i = 0; i < 30; i++) {
      bild();
      staende.push(bahn.stand);
    }
    m.folge(600 - bahn.stand + 30, 660 - bahn.stand, false);    // die nächste Zeile, mitten in der Bewegung
    for (let i = 0; i < 180; i++) {
      bild();
      staende.push(bahn.stand);
    }
    const schritte = staende.map((s, i) => (i ? s - staende[i - 1] : s));
    expect(Math.max(...schritte)).toBeLessThan(15);              // je Bild nur wenige Pixel, kein Springen
    expect(Math.min(...schritte)).toBeGreaterThanOrEqual(-0.001); // nie zurück
    expect(bahn.stand).toBeCloseTo(180, 0);
  });

  it("ausdrücklich hin oder von weit her ohne Übergang; wer selbst scrollt, hat Vorrang", () => {
    const bahn = { stand: 0, hoehe: 1000 };
    const m = new Mitlauf(bahn);
    m.folge(5000, 5030, false);                                  // weit draußen
    expect(bahn.stand).toBe(5000 - 300);
    m.folge(700, 730, false);
    bild();
    m.vorrang();
    const da = bahn.stand;
    for (let i = 0; i < 60; i++) bild();
    expect(bahn.stand).toBe(da);
  });
});
