import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import Band from "../src/ansichten/bibliothek/Band.svelte";
import Suchfeld from "../src/lib/schale/Suchfeld.svelte";
import { auswahl } from "../src/lib/stand/auswahl.svelte";
import { navigate, route } from "../src/lib/router.svelte";
import type { Buch } from "../src/lib/typen";

const buch: Buch = {
  id: 5, hash: "", title: "Der Steppenwolf", author: "Hermann Hesse", publisher: "", file_format: "epub", file_size: 1, cover_path: "", page_count: 250, year: 1927, isbn: "", typ: "", gattung: "", umschlag: "titelseite", umschlag_schlicht: false, umschlag_wahl: "", sammlung_id: null, band_nummer: "",
  is_favorite: false, is_to_read: false, rating: 4, reading_position: "", last_read_at: null, categories: [], sammlung: null, created_at: "", updated_at: "",
};

function antworte(daten: unknown) {
  globalThis.fetch = vi.fn(() => Promise.resolve(new Response(JSON.stringify(daten)))) as typeof fetch;
}

beforeEach(() => {
  navigate("/", true);
  auswahl.modus(false);
});

describe("Buch im Regal", () => {
  it("zeigt Titel, Autor, Format und führt zur Buchseite", () => {
    render(Band, { props: { buch } });
    expect(screen.getAllByText("Hermann Hesse").length).toBeGreaterThan(0);
    expect(screen.getByText("EPUB")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Der Steppenwolf" }).getAttribute("href")).toBe("/book/5");
  });

  it("überlässt Klicks mit Cmd dem Browser", async () => {
    render(Band, { props: { buch } });
    const e = new MouseEvent("click", { bubbles: true, cancelable: true, metaKey: true });
    screen.getByRole("link", { name: "Der Steppenwolf" }).dispatchEvent(e);
    expect(e.defaultPrevented).toBe(false);
  });

  it("wählt im Bearbeitungsmodus aus statt zu öffnen", async () => {
    auswahl.modus(true);
    render(Band, { props: { buch } });
    await fireEvent.click(screen.getByRole("button", { name: "Der Steppenwolf" }));
    expect(auswahl.hat(5)).toBe(true);
    expect(route.path).toBe("/");
  });
});

describe("Suchfeld", () => {
  const feld = () => screen.getByRole("searchbox") as HTMLInputElement;

  it("geht mit Enter zur Suche und behält Sonderzeichen", async () => {
    antworte({ vorschlaege: [] });
    render(Suchfeld, { props: { id: "s" } });
    await fireEvent.input(feld(), { target: { value: "C++ & mehr" } });
    await fireEvent.submit(feld().form!);
    expect(route.path).toBe("/search");
    expect((route.params as Record<string, string>).q).toBe("C++ & mehr");
  });

  it("bleibt bei leerem Feld stehen", async () => {
    render(Suchfeld, { props: { id: "s" } });
    await fireEvent.input(feld(), { target: { value: "   " } });
    await fireEvent.submit(feld().form!);
    expect(route.path).toBe("/");
  });

  it("schlägt Bücher vor und öffnet das gewählte", async () => {
    antworte({ vorschlaege: [{ id: 9, titel: "<b>Netz</b>werke", autor: "Anne" }] });
    render(Suchfeld, { props: { id: "s" } });
    await fireEvent.focus(feld());
    await fireEvent.input(feld(), { target: { value: "netz" } });
    await waitFor(() => expect(screen.getByText("werke", { exact: false })).toBeTruthy(), { timeout: 1500 });
    await fireEvent.keyDown(feld(), { key: "ArrowDown" });
    await fireEvent.submit(feld().form!);
    expect(route.path).toBe("/book/9");
  });

  it("fragt nicht bei einem Zeichen", async () => {
    antworte({ vorschlaege: [] });
    render(Suchfeld, { props: { id: "s" } });
    await fireEvent.input(feld(), { target: { value: "n" } });
    await new Promise((r) => setTimeout(r, 400));
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });
});
