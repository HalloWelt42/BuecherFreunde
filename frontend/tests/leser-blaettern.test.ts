// Blättern: Gesten, Rad, Tasten, Textstücke
import { blaettergesten, radschritt, type Blaettergriffe } from "../src/lib/leser/blaettergesten";
import { blaettertaste } from "../src/lib/leser/blaettertasten";
import { kapitelrand } from "../src/lib/leser/epub/kapitelrand";
import { Textseiten, type Textantwort } from "../src/lib/leser/pdf/textseiten.svelte";
import { ansichtFuer, artVon, einpassen, nachbarn } from "../src/lib/leser/pdf/zoom";
import { inBloecke } from "../src/lib/leser/text/bloecke";

const griffe = (mehr: Partial<Pick<Blaettergriffe, "gilt" | "belegt" | "schiebt">> = {}) => ({ gilt: () => true, vor: vi.fn(), zurueck: vi.fn(), mitte: vi.fn(), belegt: () => false, ...mehr });

function finger(ziel: EventTarget, art: string, x: number, y: number) {
  const e = new Event(art, { bubbles: true, cancelable: true }) as Event & Record<string, unknown>;
  const p = { clientX: x, clientY: y };
  Object.assign(e, { touches: art === "touchend" ? [] : [p], changedTouches: [p] });
  ziel.dispatchEvent(e);
  return e;
}
function zug(ziel: EventTarget, von: [number, number], bis: [number, number]) {
  finger(ziel, "touchstart", ...von);
  finger(ziel, "touchmove", ...bis);
  finger(ziel, "touchend", ...bis);
}
const flaeche = (html = "") => {
  const f = document.createElement("div");
  f.innerHTML = html;
  document.body.replaceChildren(f);
  return f;
};
const RAHMEN = { rahmen: () => ({ left: 100, width: 400 }) };

describe("Blättern mit dem Finger", () => {
  it("wischt vor und zurück, senkrecht nicht", () => {
    const [f, tun] = [flaeche(), griffe()];
    blaettergesten(f, RAHMEN, tun);
    zug(f, [300, 100], [200, 110]);
    zug(f, [200, 100], [300, 90]);
    zug(f, [300, 300], [290, 100]);
    expect([tun.vor.mock.calls.length, tun.zurueck.mock.calls.length, tun.mitte.mock.calls.length]).toEqual([1, 1, 0]);
  });

  it("tippt an den Rändern und in der Mitte, auch aus einem verschobenen Rahmen", () => {
    const [f, tun] = [flaeche(), griffe()];
    blaettergesten(f, { ...RAHMEN, versatz: () => -1000 }, tun);
    for (const x of [1120, 1300, 1480]) zug(f, [x, 50], [x, 50]);
    expect([tun.zurueck.mock.calls.length, tun.mitte.mock.calls.length, tun.vor.mock.calls.length]).toEqual([1, 1, 1]);
  });

  it("lässt Tasten und Links und ein offenes Feld vor", () => {
    const belegt = vi.fn(() => true);
    const [f, tun] = [flaeche('<a href="#x"><b>hin</b></a>'), griffe({ belegt })];
    blaettergesten(f, RAHMEN, tun);
    zug(f.querySelector("b")!, [480, 50], [480, 50]);
    expect(belegt).not.toHaveBeenCalled();
    zug(f, [480, 50], [480, 50]);
    expect(belegt).toHaveBeenCalledOnce();
    expect(tun.vor).not.toHaveBeenCalled();
  });

  it("schiebt eine vergrößerte Seite, statt zu blättern", () => {
    const [f, tun] = [flaeche(), griffe({ schiebt: (_achse, richtung) => richtung > 0 })];
    blaettergesten(f, RAHMEN, tun);
    zug(f, [300, 100], [100, 100]);
    zug(f, [100, 100], [300, 100]);
    expect([tun.vor.mock.calls.length, tun.zurueck.mock.calls.length]).toEqual([0, 1]);
  });

  it("rührt beim Scrollen nichts an", () => {
    const [f, tun] = [flaeche(), griffe({ gilt: () => false })];
    blaettergesten(f, RAHMEN, tun);
    expect(finger(f, "touchmove", 10, 10).defaultPrevented).toBe(false);
    zug(f, [300, 100], [100, 100]);
    expect(tun.vor).not.toHaveBeenCalled();
  });
});

const rad = (dy: number, zeit: number, dx = 0) => {
  const e = new WheelEvent("wheel", { deltaY: dy, deltaX: dx, cancelable: true });
  Object.defineProperty(e, "timeStamp", { value: zeit });
  return e;
};

describe("Rad", () => {
  it("macht einen Schritt je Dreh, der Nachlauf zählt nicht", () => {
    const tun = griffe();
    const dreh = radschritt(tun);
    for (let n = 0; n < 12; n++) dreh(rad(60 - n * 4, n * 30));
    expect(tun.vor).toHaveBeenCalledTimes(1);
    dreh(rad(40, 900));
    dreh(rad(-40, 1200));
    expect([tun.vor.mock.calls.length, tun.zurueck.mock.calls.length]).toEqual([2, 1]);
  });

  it("ein kräftiger neuer Schub im Nachlauf zählt", () => {
    const tun = griffe();
    const dreh = radschritt(tun);
    for (let n = 0; n < 15; n++) dreh(rad(60 - n * 4, n * 30));
    dreh(rad(80, 460));
    expect(tun.vor).toHaveBeenCalledTimes(2);
  });

  it("lässt die Fläche erst selbst schieben und blättert nicht im selben Schwung", () => {
    let platz = true;
    const tun = griffe({ schiebt: () => platz });
    const dreh = radschritt(tun);
    const e = rad(50, 0);
    dreh(e);
    expect(e.defaultPrevented).toBe(false);
    platz = false;
    dreh(rad(45, 30));
    expect(tun.vor).not.toHaveBeenCalled();
    dreh(rad(45, 400));
    expect(tun.vor).toHaveBeenCalledOnce();
  });
});

describe("Kapitelende beim Scrollen", () => {
  it("geht nur weiter, wer schon am Rand steht", () => {
    const f = flaeche();
    const weiter = vi.fn();
    let unten = false;
    kapitelrand(f, { gilt: () => true, amRand: (r) => r > 0 && unten, weiter });
    zug(f, [10, 400], [10, 200]);
    expect(weiter).not.toHaveBeenCalled();
    unten = true;
    zug(f, [10, 400], [10, 200]);
    expect(weiter).toHaveBeenCalledWith(1);
  });
});

describe("Tasten", () => {
  const druecke = (key: string, art: "blaettern" | "scrollen", mehr: object = {}, o: KeyboardEventInit = {}) => {
    const tun = { vor: vi.fn(), zurueck: vi.fn(), anfang: vi.fn(), ende: vi.fn(), ...mehr };
    const e = new KeyboardEvent("keydown", { key, cancelable: true, ...o });
    const hat = blaettertaste(e, art, tun);
    const gerufen = Object.entries(tun).filter(([, f]) => (f as ReturnType<typeof vi.fn>)?.mock?.calls.length).map(([n]) => n);
    return [hat, e.defaultPrevented, ...gerufen];
  };

  it("blättert mit Pfeilen, Bild- und Leertaste", () => {
    for (const k of ["ArrowRight", "ArrowDown", "PageDown", " "]) expect(druecke(k, "blaettern")).toEqual([true, true, "vor"]);
    for (const k of ["ArrowLeft", "ArrowUp", "PageUp"]) expect(druecke(k, "blaettern")).toEqual([true, true, "zurueck"]);
    expect(druecke(" ", "blaettern", {}, { shiftKey: true })).toEqual([true, true, "zurueck"]);
    expect(druecke("End", "blaettern")).toEqual([true, true, "ende"]);
  });

  it("lässt beim Scrollen der Fläche, was sie selbst kann", () => {
    for (const k of ["ArrowDown", "ArrowUp", " "]) expect(druecke(k, "scrollen")).toEqual([false, false]);
    expect(druecke("ArrowDown", "scrollen", { zeileVor: vi.fn() })).toEqual([true, true, "zeileVor"]);
    expect(druecke("PageDown", "scrollen")).toEqual([true, true, "vor"]);
  });

  it("rührt Tastenkürzel des Browsers und Tasten ohne Griff nicht an", () => {
    expect(druecke("ArrowLeft", "blaettern", {}, { altKey: true })).toEqual([false, false]);
    expect(druecke("+", "blaettern")).toEqual([false, false]);
  });
});

describe("Textblöcke", () => {
  it("verlieren kein Zeichen und enden nie mit einer Leerzeile", () => {
    const text = Array.from({ length: 900 }, (_, n) => (n % 7 === 6 ? "" : `Zeile ${n}`)).join("\n");
    const bloecke = inBloecke(text);
    expect(bloecke.length).toBeGreaterThan(10);
    expect(bloecke.join("\n")).toBe(text);
    for (const b of bloecke.slice(0, -1)) expect(b.split("\n").at(-1)!.trim()).not.toBe("");
  });

  it("teilen auch Text ohne jede Leerzeile", () => {
    const text = Array.from({ length: 1300 }, (_, n) => `Zeile ${n}`).join("\n");
    expect(inBloecke(text).length).toBe(4);
    expect(inBloecke("kurz")).toEqual(["kurz"]);
  });
});

describe("Textseiten", () => {
  const antwort = (ab: number, anzahl: number): Textantwort => ({ gesamt: 20, seiten: Array.from({ length: anzahl }, (_, n) => ab + n).filter((n) => n <= 20).map((nr) => ({ nr, gedruckt: "", bausteine: [{ art: "absatz", text: "x", titel: "", inhalt: [], bild: null, verhaeltnis: null, breite_em: null }] })) });

  it("holen hinten und vorn nach, ohne eine Seite doppelt zu zeigen", async () => {
    const t = new Textseiten(1, async (tun) => void tun(), async (_b, ab, n) => antwort(ab, n));
    await t.neu(10);
    expect([t.erste, t.letzte, t.mitVorn, t.mitHinten]).toEqual([10, 15, true, true]);
    await t.oben();
    await t.unten();
    expect(t.seiten.map((s) => s.nr)).toEqual(Array.from({ length: 17 }, (_, n) => n + 4));
    await t.oben();
    expect([t.erste, t.letzte, t.mitVorn, t.mitHinten]).toEqual([1, 20, false, false]);
    expect(await t.unten()).toBe(false);
  });

  it("erkennen Seiten nur aus Bildern als Scan, auch wenn die Seitenbilder als Bausteine kommen", async () => {
    const bild = { art: "bild" as const, text: "", titel: "", inhalt: [], bild: 0, verhaeltnis: 0.7, breite_em: null };
    const mit = (bausteine: Textantwort["seiten"][number]["bausteine"]) => new Textseiten(1, async (tun) => void tun(), async () => ({ gesamt: 2, seiten: [{ nr: 1, gedruckt: "", bausteine: [bild] }, { nr: 2, gedruckt: "", bausteine }] }));
    const scan = mit([bild]);
    await scan.neu(1);
    const kasten = mit([{ ...bild, art: "kasten", inhalt: [{ ...bild, art: "absatz", text: "Text im Kasten" }] }]);
    await kasten.neu(1);
    expect([scan.ohneText, kasten.ohneText]).toEqual([true, false]);
  });

  it("melden einen Fehler und lassen den Text stehen", async () => {
    const t = new Textseiten(1, async (tun) => void tun(), async (_b, ab, n) => (ab > 10 ? Promise.reject(new Error("weg")) : antwort(ab, n)));
    await t.neu(5);
    expect(await t.unten()).toBe(false);
    expect([t.fehler, t.letzte]).toEqual(["weg", 10]);
  });
});

describe("Ansichten eines PDF", () => {
  it("gehören zu einer Art und haben ihre Vorgabe", () => {
    expect([artVon("doppel"), artVon("breite")]).toEqual(["blaettern", "scrollen"]);
    expect([ansichtFuer("blaettern", true), ansichtFuer("scrollen", true), ansichtFuer("scrollen", false)]).toEqual(["einzeln", "breite", "scroll"]);
  });

  it("zeichnen die Nachbarbögen vor", () => {
    expect(nachbarn("einzeln", 1, 3)).toEqual([[2]]);
    expect(nachbarn("doppel", 4, 9)).toEqual([[5, 6], [1, 2]]);
    expect(nachbarn("doppel", 9, 9)).toEqual([[7, 8]]);
  });

  it("füllen im Querformat am Telefon die Breite", () => {
    const seite = { breite: 500, hoehe: 700 };
    expect(einpassen("einzeln", seite, { breite: 800, hoehe: 300 })).toBe(1.6);
    expect(einpassen("einzeln", seite, { breite: 800, hoehe: 700 })).toBe(1);
  });
});

describe("Marken am Rand", () => {
  it("liest Seite, Anteil und Stelle aus allen Arten von Einträgen", async () => {
    const { randeintraege } = await import("../src/lib/leser/randmarken");
    const m = { id: 1, book_id: 1, cfi_range: "page:12", color: "#EF5350", text_snippet: "Ein Satz", label_name: "", label_note: "", created_at: "" };
    const n = { id: 2, book_id: 1, content: "Notiz", page_reference: "62%", cfi_reference: null, created_at: "", updated_at: "" };
    const e = { id: 3, book_id: 1, name: "Wichtig", note: "", color: "#4FC3F7", created_at: "", page_reference: "S.40", position_percent: 33 };
    const ohne = { ...n, id: 4, page_reference: "" };
    const aus = randeintraege([m], [n, ohne], [e]);
    expect(aus.map((x) => [x.schluessel, x.seite, x.prozent, x.ort])).toEqual([["m1", 12, null, "Seite 12"], ["n2", null, 62, "62 %"], ["e3", 40, 33, "Seite 40"]]);
  });

  it("legt schmale Marken auf feste Plätze, nie übereinander und nie über breite", async () => {
    const { legeFest } = await import("../src/lib/leser/randmarken");
    const g = legeFest([0, 0.01, 0.02, 0.5, 1].map((anteil, eintrag) => ({ anteil, eintrag })), 300, 26, 4, [[140, 186]]);
    const ys = g.map((x) => x.y);
    expect(ys[0]).toBe(0);
    for (let i = 1; i < ys.length; i++) expect(ys[i] - ys[i - 1]).toBeGreaterThanOrEqual(30);
    expect(g.every((x) => x.y + 26 <= 140 - 4 || x.y >= 186 + 4)).toBe(true);
    expect(g.flatMap((x) => x.eintraege).sort()).toEqual([0, 1, 2, 3, 4]);
  });

  it("fasst bei zu vielen zusammen, statt zu stapeln", async () => {
    const { legeFest } = await import("../src/lib/leser/randmarken");
    const g = legeFest(Array.from({ length: 40 }, (_, n) => ({ anteil: n / 40, eintrag: n })), 120, 26, 4);
    expect(g.length).toBe(4);
    expect(g.reduce((s, x) => s + x.eintraege.length, 0)).toBe(40);
  });

  // Reicht der Platz nicht, fassen Marken sich zusammen; nie liegt eine über einer anderen (BF-48)
  const MASS = { oben: 134, unten: 834, breit: 46, schmal: 26, abstand: 4 };
  const kollisionen = (r: { hier: { y: number }[]; fern: { y: number }[] }) => {
    const alle = [...r.hier.map((g) => [g.y, g.y + MASS.breit]), ...r.fern.map((g) => [g.y, g.y + MASS.schmal])].sort((a, b) => a[0] - b[0]);
    return alle.filter((a, i) => i > 0 && a[0] < alle[i - 1][1] + MASS.abstand).length;
  };
  const zufall = (saat: number) => () => ((saat = (saat * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);

  it("fasst zu viele breite Marken je Platz zusammen, statt sie oben zu stapeln", async () => {
    const { legeAnStelle } = await import("../src/lib/leser/randmarken");
    // 122 Einträge über dem Bereich und 30 darin, wie im Markdown-Buch der Grenzprobe
    const eintraege = [...Array.from({ length: 122 }, (_, n) => ({ y: -n, eintrag: n })), ...Array.from({ length: 30 }, (_, n) => ({ y: 140 + n * 23, eintrag: 200 + n }))];
    const g = legeAnStelle(eintraege, MASS.oben, MASS.unten, MASS.breit, MASS.abstand);
    expect(g.length).toBeLessThanOrEqual(14);
    expect(kollisionen({ hier: g, fern: [] })).toBe(0);
    expect(g.every((x) => x.y >= MASS.oben && x.y + MASS.breit <= MASS.unten)).toBe(true);
    expect(g.flatMap((x) => x.eintraege).sort((a, b) => a - b)).toEqual(eintraege.map((e) => e.eintrag).sort((a, b) => a - b));
    expect(g[0].eintraege.length).toBeGreaterThan(100);
  });

  it("legt schmale Marken nie auf gesperrte Plätze, auch wenn keiner frei ist", async () => {
    const { legeFest } = await import("../src/lib/leser/randmarken");
    expect(legeFest([{ anteil: 0.3, eintrag: 1 }], 300, 26, 4, [[0, 300]])).toEqual([]);
  });

  it("lässt breiten Marken, die alles füllen, einen Platz für die schmalen frei, auf der Seite, wo diese meist liegen", async () => {
    const { legeRand } = await import("../src/lib/leser/randmarken");
    const hier = Array.from({ length: 40 }, (_, n) => ({ y: 134 + n * 18, eintrag: `h${n}` }));
    for (const [anteile, unten] of [[[0.9, 0.95, 0.99], true], [[0.01, 0.2, 0.7], false]] as const) {
      const fern = anteile.map((anteil, n) => ({ anteil, eintrag: `f${n}` }));
      const r = legeRand(hier, fern, MASS);
      expect(kollisionen(r)).toBe(0);
      expect(r.fern.length).toBeGreaterThan(0);
      expect(r.fern.flatMap((g) => g.eintraege).sort()).toEqual(fern.map((f) => f.eintrag).sort());
      expect(r.hier.flatMap((g) => g.eintraege).length).toBe(40);
      const [breit, schmal] = [r.hier.map((g) => g.y), r.fern.map((g) => g.y)];
      expect(unten ? Math.min(...schmal) > Math.max(...breit) : Math.max(...schmal) < Math.min(...breit)).toBe(true);
    }
  });

  it("legt bei wenigen Marken alles wie zuvor und bei beliebig vielen nie übereinander", async () => {
    const { legeAnStelle, legeFest, legeRand } = await import("../src/lib/leser/randmarken");
    const hier = [{ y: 300, eintrag: 1 }, { y: 310, eintrag: 2 }];
    const fern = [{ anteil: 0.1, eintrag: 3 }, { anteil: 0.6, eintrag: 4 }];
    const nah = legeAnStelle(hier, MASS.oben, MASS.unten, MASS.breit, MASS.abstand);
    const gesperrt = nah.map((g): [number, number] => [g.y - MASS.oben, g.y - MASS.oben + MASS.breit]);
    const fest = legeFest(fern, MASS.unten - MASS.oben - MASS.schmal, MASS.schmal, MASS.abstand, gesperrt).map((g) => ({ ...g, y: g.y + MASS.oben }));
    expect(legeRand(hier, fern, MASS)).toEqual({ hier: nah, fern: fest });
    const z = zufall(47);
    for (let lauf = 0; lauf < 200; lauf++) {
      const h = Array.from({ length: Math.floor(z() * 300) }, (_, n) => ({ y: z() * 1200 - 200, eintrag: n }));
      const f = Array.from({ length: Math.floor(z() * 3000) }, (_, n) => ({ anteil: z(), eintrag: -n - 1 }));
      const r = legeRand(h, f, MASS);
      expect(kollisionen(r)).toBe(0);
      expect(r.hier.reduce((s, g) => s + g.eintraege.length, 0)).toBe(h.length);
      expect(r.fern.reduce((s, g) => s + g.eintraege.length, 0)).toBe(f.length);
    }
  });

  it("stellt breite Marken an ihre Stelle, im sichtbaren Bereich und untereinander", async () => {
    const { legeAnStelle } = await import("../src/lib/leser/randmarken");
    const g = legeAnStelle([{ y: 100, eintrag: "a" }, { y: 110, eintrag: "b" }, { y: -50, eintrag: "c" }, { y: 990, eintrag: "d" }], 0, 500, 46, 4);
    expect(g.map((x) => [x.y, x.eintraege.join("")])).toEqual([[0, "c"], [100, "a"], [150, "b"], [454, "d"]]);
  });
});
