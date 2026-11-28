// BF-121: Holt die Vertonung den Ton langsamer, als vorgelesen wird, muss Pause trotzdem gehen; vorher war der Knopf gesperrt,
// solange gewartet wurde, und am Rechner ließ sich das laufende Vorlesen kaum anhalten.
import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import Spieler from "../src/ansichten/leser/Spieler.svelte";
import Knopf from "../src/lib/teile/Knopf.svelte";
import { vorlesen } from "../src/lib/stand/vorlesen.svelte";

afterEach(() => {
  vorlesen.wartet = false;
  vorlesen.pausiert = false;
  vi.restoreAllMocks();
});

describe("Spieler beim Vorlesen", () => {
  it("Pause geht, während der Ton noch geholt wird, und das Zeichen dreht", async () => {
    vorlesen.wartet = true;
    vorlesen.pausiert = false;
    const pause = vi.spyOn(vorlesen, "pauseOderWeiter").mockImplementation(() => {});
    const { container } = render(Spieler, { art: "Seite" });
    const knopf = screen.getByRole("button", { name: "Pause" });
    expect((knopf as HTMLButtonElement).disabled).toBe(false);
    expect(container.querySelector(".haupt-taste .fa-circle-notch")).not.toBeNull();
    await fireEvent.click(knopf);
    expect(pause).toHaveBeenCalledOnce();
  });

  it("angehalten heißt der Knopf Weiter, ohne zu drehen", () => {
    vorlesen.wartet = true;
    vorlesen.pausiert = true;
    const { container } = render(Spieler, { art: "Seite" });
    expect((screen.getByRole("button", { name: "Weiter" }) as HTMLButtonElement).disabled).toBe(false);
    expect(container.querySelector(".haupt-taste .fa-circle-notch")).toBeNull();
  });
});

describe("Knopf", () => {
  it("laeuft sperrt, dreht nicht", () => {
    render(Knopf, { text: "Läuft", symbol: "play", laeuft: true });
    render(Knopf, { text: "Dreht", symbol: "play", dreht: true });
    expect((screen.getByRole("button", { name: "Läuft" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Dreht" }) as HTMLButtonElement).disabled).toBe(false);
  });
});
