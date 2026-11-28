// Markieren mit einem Rechteck auf gescannten Seiten (BF-123): Stelle, Ziehen, Lesung
import { alsLage, bereichAus, bereichZwischen, stelleVon } from "../src/lib/leser/pdf/bereich";
import { bereichszug } from "../src/lib/leser/pdf/bereichszug";
import { Bereichsauswahl, istBereich, Lesung, NACHFRAGE_MS } from "../src/lib/leser/pdf/lesung.svelte";
import type { Lesestand } from "../src/lib/api/highlights";

describe("Stelle eines Rechtecks", () => {
  it("geht hin und zurück, wie der Server sie schreibt", () => {
    const b = { x0: 0.1, y0: 0.2, x1: 0.5, y1: 0.35 };
    expect(stelleVon(12, b)).toBe("page:12:bereich:0.1000,0.2000,0.5000,0.3500");
    expect(bereichAus("page:12:bereich:0.1000,0.2000,0.5000,0.3500")).toEqual({ seite: 12, bereich: b });
  });

  it("lehnt ab, was kein Rechteck ist", () => {
    for (const s of ["page:12", "page:3:bereich:0.5,0.2,0.4,0.3", "page:0:bereich:0.1,0.1,0.2,0.2", "page:2:bereich:1.5,0.1,1.7,0.2", "epubcfi(/6/4)"]) expect(bereichAus(s)).toBeNull();
  });

  it("rechnet zwischen zwei Punkten in Anteile der Seite, klemmt am Rand, zu klein ist ein Klick", () => {
    const seite = { left: 100, top: 50, width: 400, height: 800 };
    expect(bereichZwischen(seite, { x: 300, y: 450 }, { x: 140, y: 130 })).toEqual({ x0: 0.1, y0: 0.1, x1: 0.5, y1: 0.5 });
    expect(bereichZwischen(seite, { x: 50, y: 0 }, { x: 900, y: 2000 })).toEqual({ x0: 0, y0: 0, x1: 1, y1: 1 });
    expect(bereichZwischen(seite, { x: 200, y: 200 }, { x: 202, y: 260 })).toBeNull();
    expect(alsLage({ x0: 0.1, y0: 0.2, x1: 0.5, y1: 0.35 })).toEqual({ left: "10%", top: "20%", width: "40%", height: "15%" });
  });
});

describe("Rechteck ziehen", () => {
  const ziehe = (ziel: EventTarget, art: string, x: number, y: number, pointerType = "mouse") =>
    ziel.dispatchEvent(new PointerEvent(art, { bubbles: true, button: 0, pointerId: 1, pointerType, clientX: x, clientY: y }));

  function seiten() {
    const f = document.createElement("div");
    f.innerHTML = '<div class="pdfseite" data-seite="3"><a href="#x">Link</a></div>';
    document.body.replaceChildren(f);
    const seite = f.querySelector<HTMLElement>(".pdfseite")!;
    seite.getBoundingClientRect = () => ({ left: 0, top: 0, width: 500, height: 1000, right: 500, bottom: 1000, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;
    return { f, seite };
  }

  it("meldet das Rechteck beim Ziehen und am Ende", () => {
    const { f, seite } = seiten();
    const zieht = vi.fn();
    const fertig = vi.fn();
    bereichszug(f, { darf: () => true, zieht, fertig });
    ziehe(seite, "pointerdown", 50, 100);
    ziehe(f, "pointermove", 250, 300);
    ziehe(f, "pointerup", 250, 300);
    expect(zieht.mock.calls[0][0]).toEqual({ seite: 3, lage: { x0: 0.1, y0: 0.1, x1: 0.5, y1: 0.3 } });
    expect(zieht.mock.calls.at(-1)?.[0]).toBeNull();
    expect(fertig).toHaveBeenCalledWith(3, { x0: 0.1, y0: 0.1, x1: 0.5, y1: 0.3 }, expect.anything());
  });

  it("lässt Links vor, und ohne Erlaubnis rollt der Finger", () => {
    const { f, seite } = seiten();
    const fertig = vi.fn();
    bereichszug(f, { darf: (e) => e.pointerType === "mouse", zieht: () => {}, fertig });
    ziehe(seite.querySelector("a")!, "pointerdown", 50, 100);
    ziehe(f, "pointerup", 250, 300);
    ziehe(seite, "pointerdown", 50, 100, "touch");
    ziehe(f, "pointerup", 250, 300, "touch");
    ziehe(seite, "pointerdown", 50, 100);
    ziehe(f, "pointerup", 52, 102);                          // zu klein: ein Klick
    expect(fertig).not.toHaveBeenCalled();
  });
});

describe("Lesung eines Rechtecks", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("fragt nach, bis der Text da ist, und die Auswahl trägt ihn", async () => {
    const antworten: Lesestand[] = [{ id: 7, stand: "offen", text: "", grund: "" }, { id: 7, stand: "fertig", text: "Wolken über dem Deich", grund: "" }];
    const lesestand = vi.fn(async () => antworten.shift()!);
    const l = new Lesung(4, "page:1:bereich:0.1000,0.1000,0.5000,0.2000", { liesBereich: async () => ({ id: 7, stand: "offen", text: "", grund: "" }), lesestand });
    const a = new Bereichsauswahl(1, { x0: 0.1, y0: 0.1, x1: 0.5, y1: 0.2 }, 10, 20, 30, "S. 1", l);
    await vi.advanceTimersByTimeAsync(0);
    expect([l.id, l.stand, a.text, istBereich(a), a.cfi]).toEqual([7, "offen", "", true, "page:1:bereich:0.1000,0.1000,0.5000,0.2000"]);
    await vi.advanceTimersByTimeAsync(NACHFRAGE_MS * 2);
    expect([l.stand, a.text, lesestand.mock.calls.length]).toEqual(["fertig", "Wolken über dem Deich", 2]);
    await vi.advanceTimersByTimeAsync(NACHFRAGE_MS * 3);
    expect(lesestand).toHaveBeenCalledTimes(2);              // fertig: keine Nachfrage mehr
  });

  it("hört auf, wenn das Menü zu ist, und nennt einen Fehler als Satz", async () => {
    const lesestand = vi.fn(async () => ({ id: 8, stand: "offen" as const, text: "", grund: "" }));
    const l = new Lesung(4, "page:1:bereich:0.1000,0.1000,0.5000,0.2000", { liesBereich: async () => ({ id: 8, stand: "offen", text: "", grund: "" }), lesestand });
    await vi.advanceTimersByTimeAsync(0);
    l.beende();
    await vi.advanceTimersByTimeAsync(NACHFRAGE_MS * 3);
    expect(lesestand).not.toHaveBeenCalled();
    const kaputt = new Lesung(4, "page:1:bereich:0.1000,0.1000,0.5000,0.2000", { liesBereich: async () => { throw new Error("Die Bibliothek antwortet nicht"); }, lesestand });
    await vi.advanceTimersByTimeAsync(0);
    expect([kaputt.stand, kaputt.grund]).toEqual(["fehler", "Die Bibliothek antwortet nicht"]);
  });
});
