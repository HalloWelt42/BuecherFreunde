// Bücher und Besonderes nach der Art des Werks (BF-77): Leiste, Filter, Überschrift, Zusammenfassen, Lauf unter Aufträge.
// Nur erfundene Titel.
import { fireEvent, render, screen } from "@testing-library/svelte";
import { titelDerFilter } from "../src/ansichten/bibliothek/titel";
import Leiste from "../src/lib/schale/Leiste.svelte";
import { navigate, route } from "../src/lib/router.svelte";
import { auftraege } from "../src/lib/stand/auftraege.svelte";
import { bestand } from "../src/lib/stand/bestand.svelte";
import { buecher } from "../src/lib/stand/buecher.svelte";
import { fasstZusammen } from "../src/lib/stand/eintraege";
import { werkarten, werkartenanteil, werkartentext } from "../src/lib/stand/werkarten.svelte";
import type { Einordnungsstand } from "../src/lib/typen";

const stand = (mehr: Partial<Einordnungsstand>): Einordnungsstand => ({ an: true, bereit: true, laeuft: true, angehalten: false, grund: "", gesamt: 12, nach_regel: 7, durch_ki: 2, offen: 3, ...mehr });

function antworte(daten: (weg: string) => unknown) {
  globalThis.fetch = vi.fn((weg: string) => Promise.resolve(new Response(JSON.stringify(daten(String(weg)))))) as unknown as typeof fetch;
}

/** Der Stand für den Lauf, für alles andere (Zahlen, Regale, Sammlungen, Katalog nach dem Lauf) eine leere Antwort */
const nurStand = (s: () => Einordnungsstand) => (weg: string) => (weg.includes("/api/einordnung") ? s() : /categories|collections/.test(weg) ? [] : {});

beforeEach(() => navigate("/", true));

describe("Bücher und Besonderes", () => {
  it("stehen oben in der Leiste mit ihren Zahlen und filtern nach Art", async () => {
    bestand.zahlen = { ...bestand.zahlen, buecher: 41, besonderes: 9, buecher_gesamt: 50 };
    render(Leiste);
    const besonderes = screen.getByRole("button", { name: /Besonderes/ });
    expect(besonderes.textContent).toContain("9");
    expect(screen.getByRole("button", { name: /Bücher/ }).textContent).toContain("41");
    expect(screen.queryByRole("button", { name: /Dokumente/ })).toBeNull();
    await fireEvent.click(besonderes);
    expect(route.qs).toBe("art=besonderes");
    await fireEvent.click(screen.getByRole("button", { name: /Bücher/ }));
    expect(route.qs).toBe("art=buch");
  });

  it("benennen die Ansicht und fassen große Sammlungen zusammen", () => {
    navigate("/?art=besonderes", true);
    expect(titelDerFilter()).toBe("Besonderes");
    navigate("/?art=buch", true);
    expect(titelDerFilter()).toBe("Bücher");
    navigate("/?hat_isbn=false", true);
    expect(titelDerFilter()).toBe("Ohne ISBN");
    expect(fasstZusammen(["art"])).toBe(true);
    expect(fasstZusammen(["art", "category"])).toBe(true);
  });

  it("fragt die Bücherliste mit der Art an", async () => {
    const wege: string[] = [];
    antworte((weg) => {
      wege.push(weg);
      return { buecher: [], gesamt: 0, seite: 1, pro_seite: 48, seiten_gesamt: 0 };
    });
    navigate("/?art=besonderes", true);
    await buecher.laden();
    expect(wege[0]).toContain("art=besonderes");
    expect(wege[0]).toContain("zusammenfassen=true");
  });
});

describe("Art der Werke bestimmen unter Aufträge", () => {
  afterEach(() => werkarten.halte());

  it("nennt Fortschritt und Zahlen", () => {
    expect(werkartentext(stand({}))).toBe("9 von 12 Werken eingeordnet: 7 nach Regel, 2 durch die KI, 3 offen");
    expect(werkartenanteil(stand({}))).toBeCloseTo(0.75);
    expect(werkartenanteil(stand({ gesamt: 0 }))).toBeNull();
  });

  it("steht unter Aufträge, solange er läuft oder angehalten ist, danach einmal mit dem Ergebnis", async () => {
    let jetzt = stand({});
    antworte(nurStand(() => jetzt));
    werkarten.starte();
    await vi.waitFor(() => expect(auftraege.eigene.find((a) => a.id === "werkarten")?.laeuft).toBe(true));
    werkarten.halte();
    jetzt = stand({ laeuft: false, angehalten: true, grund: "Die Leitstelle lehnt ab" });
    werkarten.starte();
    await vi.waitFor(() => expect(auftraege.eigene.find((a) => a.id === "werkarten")?.pausiert).toBe(true));
    const a = auftraege.eigene.find((x) => x.id === "werkarten")!;
    expect(a.text).toContain("Die Leitstelle lehnt ab");
    expect(a.fortsetzen).toBeTypeOf("function");
    werkarten.halte();
    jetzt = stand({ laeuft: false, offen: 0, durch_ki: 5 });
    werkarten.starte();
    await vi.waitFor(() => expect(auftraege.eigene.find((x) => x.id === "werkarten")?.pausiert).toBe(false));
    expect(auftraege.eigene.find((x) => x.id === "werkarten")?.laeuft).toBe(false);
  });

  it("zeigt nichts, wenn er nicht lief", async () => {
    auftraege.entferne("werkarten");
    antworte(nurStand(() => stand({ laeuft: false })));
    werkarten.starte();
    await vi.waitFor(() => expect(werkarten.stand?.laeuft).toBe(false));
    expect(auftraege.eigene.some((a) => a.id === "werkarten")).toBe(false);
  });
});
