// BF-43: das Suchfeld als Schnellfilter der offenen Liste
import { fireEvent, render, screen } from "@testing-library/svelte";
import { flushSync } from "svelte";
import { regalfilter } from "../src/ansichten/bibliothek/schnellfilter";
import { autorenansicht, autorenfilter } from "../src/ansichten/autoren/liste.svelte";
import Suchfeld from "../src/lib/schale/Suchfeld.svelte";
import { vonGesamt } from "../src/lib/format";
import { navigate, route } from "../src/lib/router.svelte";
import { buecher } from "../src/lib/stand/buecher.svelte";
import { filter } from "../src/lib/stand/filter.svelte";
import { FILTER_WARTE_MS, schnellfilter, type Filterziel } from "../src/lib/stand/schnellfilter.svelte";

/** Ein Ziel wie das einer Ansicht, das mitschreibt, was es filtern soll */
function probeziel(anfang = "") {
  const gefiltert: string[] = [];
  let wort = $state(anfang);
  const ziel: Filterziel = {
    get wort() {
      return wort;
    },
    hinweis: "Titel, Autor, ISBN oder Etikett",
    treffer: 12,
    gesamt: 340,
    filtere(neu) {
      gefiltert.push(neu);
      wort = neu;
    },
  };
  return { ziel, gefiltert };
}

function aufArt(art: "suchen" | "filtern") {
  if (schnellfilter.art !== art) schnellfilter.schalte();
}

let ab: (() => void) | undefined;

beforeEach(() => {
  navigate("/", true);
  aufArt("suchen");
});

afterEach(() => {
  ab?.();
  ab = undefined;
  vi.useRealTimers();
});

describe("Schnellfilter: Stand", () => {
  it("filtert nur, wenn gewünscht und die Ansicht eine Liste anbietet", () => {
    const { ziel } = probeziel();
    aufArt("filtern");
    expect(schnellfilter.filtert).toBe(false);
    ab = schnellfilter.biete(ziel);
    expect(schnellfilter.filtert).toBe(true);
    ab();
    ab = undefined;
    expect(schnellfilter.ziel).toBe(null);
  });

  it("merkt die Art je Gerät", () => {
    aufArt("filtern");
    expect(localStorage.getItem("suchfeld.art")).toBe("filtern");
    schnellfilter.schalte();
    expect(localStorage.getItem("suchfeld.art")).toBe("suchen");
  });

  it("fragt beim Tippen erst nach einer Pause, mit dem letzten Wort", () => {
    vi.useFakeTimers();
    const { ziel, gefiltert } = probeziel();
    ab = schnellfilter.biete(ziel);
    for (const w of ["t", "to", "tol", "tolk "]) {
      schnellfilter.tippe(w);
      vi.advanceTimersByTime(80);
    }
    expect(gefiltert).toEqual([]);
    vi.advanceTimersByTime(FILTER_WARTE_MS);
    expect(gefiltert).toEqual(["tolk"]);
    // Dasselbe Wort noch einmal lädt nichts neu
    schnellfilter.tippe("tolk");
    vi.advanceTimersByTime(FILTER_WARTE_MS);
    expect(gefiltert).toEqual(["tolk"]);
  });

  it("verwirft das Warten beim Wechsel der Ansicht", () => {
    vi.useFakeTimers();
    const erste = probeziel();
    ab = schnellfilter.biete(erste.ziel);
    schnellfilter.tippe("kafka");
    ab();
    const zweite = probeziel();
    ab = schnellfilter.biete(zweite.ziel);
    vi.advanceTimersByTime(FILTER_WARTE_MS * 2);
    expect(erste.gefiltert).toEqual([]);
    expect(zweite.gefiltert).toEqual([]);
  });

  it("leert sofort und vergisst Getipptes", () => {
    vi.useFakeTimers();
    const { ziel, gefiltert } = probeziel("tolkien");
    ab = schnellfilter.biete(ziel);
    schnellfilter.tippe("tolkie");
    schnellfilter.leere(ziel);
    vi.advanceTimersByTime(FILTER_WARTE_MS);
    expect(gefiltert).toEqual([""]);
  });

  it("zählt deutsch", () => {
    expect(vonGesamt(12, 4734)).toBe("12 von 4.734");
  });
});

describe("Schnellfilter der Bibliothek", () => {
  it("steht als q in der Adresse bei den übrigen Filtern", () => {
    navigate("/?is_favorite=true", true);
    regalfilter.filtere("tolk");
    expect(route.path).toBe("/");
    expect(filter.wert("q")).toBe("tolk");
    expect(filter.wert("is_favorite")).toBe("true");
    expect(filter.aktiv).toBe(true);
  });

  it("grenzt nur ein: allein zählt er nicht als Filter der Ansicht (Alle bleibt Alle)", () => {
    navigate("/?q=tolk", true);
    expect(filter.aktiv).toBe(false);
    expect(filter.kennung).toBe("q=tolk");
  });

  it("macht beim Tippen einen Schritt im Verlauf, nicht einen je Wort", () => {
    const vorher = history.length;
    regalfilter.filtere("t");
    regalfilter.filtere("tolk");
    regalfilter.filtere("tolkien");
    expect(history.length).toBe(vorher + 1);
    expect(filter.wert("q")).toBe("tolkien");
  });

  it("fragt den Server mit suche und zählt ohne", async () => {
    const aufrufe: string[] = [];
    globalThis.fetch = vi.fn((weg: string) => {
      aufrufe.push(String(weg));
      return Promise.resolve(new Response(JSON.stringify({ buecher: [], gesamt: 12, gesamt_ohne_suche: 340, seite: 1, pro_seite: 48, seiten_gesamt: 1 })));
    }) as unknown as typeof fetch;
    navigate("/?q=tolk%20hob", true);
    await buecher.laden();
    expect(aufrufe.some((a) => a.includes("suche=tolk+hob"))).toBe(true);
    expect([regalfilter.treffer, regalfilter.gesamt]).toEqual([12, 340]);
  });

  it("gilt nur dort: andere Ansichten kennen kein q", () => {
    navigate("/?q=tolk", true);
    navigate("/authors");
    expect(filter.wert("q")).toBe("");
    expect(autorenfilter.wort).toBe(autorenansicht.suche.trim());
  });
});

describe("Suchfeld als Schnellfilter", () => {
  const feld = () => screen.getByRole("searchbox") as HTMLInputElement;
  const umschalter = () => screen.getByRole("button", { name: "Liste filtern" });

  it("ohne Liste ist die Taste gesperrt und das Feld sucht", async () => {
    render(Suchfeld, { props: { id: "s" } });
    expect((umschalter() as HTMLButtonElement).disabled).toBe(true);
    await fireEvent.input(feld(), { target: { value: "kafka" } });
    await fireEvent.submit(feld().form!);
    expect(route.path).toBe("/search");
  });

  it("schaltet um, zeigt den Zustand und nimmt das Getippte als Filter", async () => {
    const { ziel, gefiltert } = probeziel();
    ab = schnellfilter.biete(ziel);
    render(Suchfeld, { props: { id: "s" } });
    await fireEvent.input(feld(), { target: { value: "tolkien" } });
    await fireEvent.click(umschalter());
    expect(umschalter().getAttribute("aria-pressed")).toBe("true");
    expect(gefiltert).toEqual(["tolkien"]);
    expect(feld().placeholder).toBe("Titel, Autor, ISBN oder Etikett");
    expect(screen.getByRole("status").textContent).toBe("12 von 340");
  });

  it("filtert beim Tippen ohne Vorschläge vom Server und ohne Anfrage je Taste", async () => {
    vi.useFakeTimers();
    const { ziel, gefiltert } = probeziel();
    ab = schnellfilter.biete(ziel);
    aufArt("filtern");
    render(Suchfeld, { props: { id: "s" } });
    for (const w of ["h", "ho", "hob", "hobb"]) {
      await fireEvent.input(feld(), { target: { value: w } });
      vi.advanceTimersByTime(100);
    }
    expect(gefiltert).toEqual([]);
    vi.advanceTimersByTime(FILTER_WARTE_MS);
    expect(gefiltert).toEqual(["hobb"]);
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("Enter oder die Zeile in den Vorschlägen sucht in allen Büchern", async () => {
    const { ziel, gefiltert } = probeziel();
    ab = schnellfilter.biete(ziel);
    aufArt("filtern");
    render(Suchfeld, { props: { id: "s" } });
    await fireEvent.focus(feld());
    await fireEvent.input(feld(), { target: { value: "hobbit" } });
    expect(screen.getByText("In allen Büchern suchen")).toBeTruthy();
    await fireEvent.keyDown(feld(), { key: "ArrowDown" });
    await fireEvent.submit(feld().form!);
    expect(route.path).toBe("/search");
    expect((route.params as Record<string, string>).q).toBe("hobbit");
    // Die Ansicht behält, was getippt war
    expect(gefiltert).toEqual(["hobbit"]);
  });

  it("Escape leert und verlässt das Feld", async () => {
    const { ziel, gefiltert } = probeziel("tolk");
    ab = schnellfilter.biete(ziel);
    aufArt("filtern");
    render(Suchfeld, { props: { id: "s" } });
    flushSync();
    expect(feld().value).toBe("tolk");
    feld().focus();
    await fireEvent.keyDown(feld(), { key: "Escape" });
    expect(feld().value).toBe("");
    expect(gefiltert).toEqual([""]);
    expect(document.activeElement).not.toBe(feld());
  });

  it("zeigt je Ansicht ihr eigenes Wort", async () => {
    const regal = probeziel("tolk");
    const autoren = probeziel("");
    aufArt("filtern");
    ab = schnellfilter.biete(regal.ziel);
    render(Suchfeld, { props: { id: "s" } });
    flushSync();
    expect(feld().value).toBe("tolk");
    ab();
    ab = schnellfilter.biete(autoren.ziel);
    flushSync();
    expect(feld().value).toBe("");
    ab();
    ab = schnellfilter.biete(regal.ziel);
    flushSync();
    expect(feld().value).toBe("tolk");
  });
});
