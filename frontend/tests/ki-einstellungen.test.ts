// BF-10: Die KI kommt über die Leitstelle; die Einstellungen zeigen den Stand und wählen nur das Modell
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import KiVerbindung from "../src/ansichten/einstellungen/KiVerbindung.svelte";
import { anschluesse } from "../src/lib/stand/anschluesse.svelte";
import { verbindungen } from "../src/lib/stand/verbindungen.svelte";
import type { Verbindung } from "../src/lib/typen";

interface Aufruf {
  weg: string;
  art: string;
  inhalt: unknown;
}

/** Antworten je Weg; schreibt mit, was gefragt wurde */
function server(antworten: Record<string, unknown>): Aufruf[] {
  const aufrufe: Aufruf[] = [];
  globalThis.fetch = vi.fn((weg: string, optionen: RequestInit = {}) => {
    const pfad = String(weg).split("?")[0];
    aufrufe.push({ weg: pfad, art: optionen.method ?? "GET", inhalt: optionen.body ? JSON.parse(String(optionen.body)) : null });
    return Promise.resolve(new Response(JSON.stringify(antworten[pfad] ?? {})));
  }) as unknown as typeof fetch;
  return aufrufe;
}

function leitstelle(stand: Verbindung["stand"], text: string): Verbindung[] {
  return [{ kennung: "leitstelle", name: "Leitstelle", stand, text }];
}

const STATUS = { erreichbar: true, grund: "", modelle: ["gemma", "qwen"], url: "https://leitstelle.lan/v1", modell: "qwen", aktiviert: true };

beforeEach(() => {
  anschluesse.jetzt = { ...anschluesse.jetzt, ki: true };
});

describe("KI in den Einstellungen", () => {
  it("zeigt die Leitstelle angeschlossen, die Adresse nur zum Lesen und die Modelle zur Wahl", async () => {
    server({ "/api/ai/status": STATUS });
    verbindungen.liste = leitstelle("gut", "KI mit qwen");
    render(KiVerbindung);
    expect(screen.getByText("angeschlossen")).toBeTruthy();
    const wahl = (await screen.findByRole("combobox", { name: "Modell" })) as HTMLSelectElement;
    expect([...wahl.options].map((o) => o.value)).toEqual(["gemma", "qwen"]);
    expect(wahl.value).toBe("qwen");
    expect(screen.getByText("https://leitstelle.lan/v1")).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button", { name: /absuchen/i })).toBeNull();
    expect(screen.queryByRole("button", { name: "Speichern" })).toBeNull();
  });

  it("wählt das Modell mit dem Feld, das die Schnittstelle annimmt, und nie eine Adresse", async () => {
    const aufrufe = server({ "/api/ai/status": STATUS, "/api/ai/config": { url: STATUS.url, modell: "gemma", aktiviert: true }, "/api/verbindungen": leitstelle("gut", "KI mit gemma") });
    verbindungen.liste = leitstelle("gut", "KI mit qwen");
    render(KiVerbindung);
    const wahl = await screen.findByRole("combobox", { name: "Modell" });
    await fireEvent.change(wahl, { target: { value: "gemma" } });
    await waitFor(() => expect(aufrufe.some((a) => a.art === "PATCH")).toBe(true));
    expect(aufrufe.filter((a) => a.art === "PATCH")).toEqual([{ weg: "/api/ai/config", art: "PATCH", inhalt: { lm_studio_model: "gemma" } }]);
  });

  it("nennt den Grund, wenn die Leitstelle das gewählte Modell nicht anbietet, und lässt es gewählt", async () => {
    server({ "/api/ai/status": { ...STATUS, erreichbar: false, modell: "alt", grund: "Die Leitstelle bietet das Modell alt nicht an" } });
    verbindungen.liste = leitstelle("warn", "Die Leitstelle bietet das Modell alt nicht an");
    render(KiVerbindung);
    expect(screen.getByText("Die Leitstelle bietet das Modell alt nicht an")).toBeTruthy();
    const wahl = (await screen.findByRole("combobox", { name: "Modell" })) as HTMLSelectElement;
    expect(wahl.value).toBe("alt");
  });

  it("ohne Einrichtung: nicht eingerichtet, mit Grund, ohne Modellwahl und ohne Anfrage an die KI", async () => {
    anschluesse.jetzt = { ...anschluesse.jetzt, ki: false };
    const aufrufe = server({});
    verbindungen.liste = [];
    render(KiVerbindung);
    expect(screen.getByText("nicht eingerichtet")).toBeTruthy();
    expect(screen.getByText("Adresse oder Schlüssel fehlen in der Einrichtung des Servers")).toBeTruthy();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(aufrufe.some((a) => a.weg === "/api/ai/status")).toBe(false);
  });
});
