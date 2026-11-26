const anfrage = vi.hoisted(() => vi.fn(() => Promise.resolve({})));
vi.mock("../src/lib/api/client", () => ({ anfrage }));
vi.mock("../src/lib/stand/buecher.svelte", () => ({ buecher: { aktualisiere: vi.fn() } }));
vi.mock("../src/lib/stand/wahl.svelte", () => ({ wahl: { aktualisiere: vi.fn() } }));

import { buchort, Positionsspeicher } from "../src/lib/leser/position";
import { Verzoegert } from "../src/lib/leser/verzoegert";

describe("Lesestelle merken", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    anfrage.mockClear();
    history.replaceState(null, "", "/book/4/read");
  });
  afterEach(() => vi.useRealTimers());

  it("schickt nach der Ruhe genau einmal, mit der letzten Stelle", () => {
    const s = new Positionsspeicher(buchort(4), "pdf");
    s.merke({ page: 2 }, { page: 2 });
    s.merke({ page: 3 }, { page: 3 });
    expect(location.search).toBe("?page=3");
    vi.advanceTimersByTime(1600);
    expect(anfrage).toHaveBeenCalledTimes(1);
    expect(anfrage).toHaveBeenCalledWith("/api/books/4/leseposition", expect.objectContaining({ method: "PATCH", keepalive: true, body: JSON.stringify({ position: 'pdf:{"page":3}' }) }));
  });

  it("schickt beim Verlassen sofort und danach nichts doppelt", () => {
    const s = new Positionsspeicher(buchort(4), "txt");
    const ende = s.starte();
    s.merke({ scrollPct: 12 });
    ende();
    expect(anfrage).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(5000);
    expect(anfrage).toHaveBeenCalledTimes(1);
  });

  it("schickt beim Schließen der Seite", () => {
    const s = new Positionsspeicher(buchort(4), "epub");
    s.starte();
    s.merke({ cfi: "epubcfi(/6)" });
    dispatchEvent(new Event("pagehide"));
    expect(anfrage).toHaveBeenCalledTimes(1);
  });

  it("führt die Adresse nur im eigenen Leser nach", () => {
    history.replaceState(null, "", "/book/4");
    new Positionsspeicher(buchort(4), "pdf").merke({ page: 9 }, { page: 9 });
    expect(location.pathname + location.search).toBe("/book/4");
  });
});

describe("Verzögertes Speichern je Feld", () => {
  it("ruft je Feld einmal und beim Ende sofort", () => {
    vi.useFakeTimers();
    const v = new Verzoegert();
    const a = vi.fn();
    const b = vi.fn();
    v.rufe("a", a);
    v.rufe("a", a);
    v.rufe("b", b);
    vi.advanceTimersByTime(900);
    expect(a).toHaveBeenCalledTimes(1);
    v.rufe("b", b);
    v.alle();
    expect(b).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
