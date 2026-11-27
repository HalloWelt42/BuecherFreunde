// BF-105: Am Telefon lässt sich der Code im Blatt Ausführen bearbeiten: dritter Reiter mit dem Editor, Zurücksetzen auf das
// Listing aus dem Buch, nur wenn geändert.
import { fireEvent, render, screen } from "@testing-library/svelte";
import Telefonblatt from "../src/lib/ausfuehren/Telefonblatt.svelte";

function arbeit(geaendert: boolean) {
  return {
    code: 'print("Hallo")\nzahl = 7\n', sprache: "python", schritte: [], veraltet: false, aktuell: null, haltepunkte: [], variablen: [], lauf: null, i: 0,
    geaendert, sitzung: { laeuft: false, fehler: "" }, ziel: () => 0, gehe: () => {}, starte: () => {},
  };
}

const grund = { name: "listing.py", kann: true, fassung: "", ed: "dunkel", onzurstelle: () => {}, onschliessen: () => {} };

describe("Telefonblatt", () => {
  it("zeigt im Reiter Bearbeiten den Editor; unverändert ist Zurücksetzen gesperrt", async () => {
    const zurueck = vi.fn();
    const { container } = render(Telefonblatt, { props: { ...grund, arbeit: arbeit(false) as never, onzuruecksetzen: zurueck } });
    await fireEvent.click(screen.getByRole("button", { name: /Bearbeiten/ }));
    expect(container.querySelector(".code-editor")).not.toBeNull();
    expect(container.querySelector(".blatt-sheet")!.classList.contains("hoch")).toBe(true);
    expect(screen.getByText("Wie im Buch")).toBeTruthy();
    expect((screen.getByRole("button", { name: /Zurücksetzen/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("geändert: Hinweis im Kopf und Zurücksetzen holt das Listing zurück", async () => {
    const zurueck = vi.fn();
    render(Telefonblatt, { props: { ...grund, arbeit: arbeit(true) as never, onzuruecksetzen: zurueck } });
    expect(screen.getByText(/^geändert, /)).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: /Bearbeiten/ }));
    await fireEvent.click(screen.getByRole("button", { name: /Zurücksetzen/ }));
    expect(zurueck).toHaveBeenCalledOnce();
  });
});
