// BF-101: Am iPhone fiel die Stimme nach kurzem Proben aus und die Probe blieb gesperrt. Ein Satz muss immer enden: gut, mit
// Fehler oder abgelöst; nie hängt er für immer. Gegen ein nachgebautes Tonelement, das sich wie Safari verhält.
import { Dienstsprecher, STILL_MS } from "../src/lib/vorlesen/dienst";
import type { Tonsatz } from "../src/lib/vorlesen/typen";

class Tonattrappe {
  src = "";
  preload = "";
  currentTime = 0;
  duration = Number.NaN;
  paused = true;
  playbackRate = 1;
  defaultPlaybackRate = 1;
  preservesPitch = true;
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeupdate: (() => void) | null = null;
  /** Wie das nächste play() ausgeht */
  static antwort: () => Promise<void> = () => Promise.resolve();
  static zuletzt: Tonattrappe;
  constructor() {
    Tonattrappe.zuletzt = this;
  }
  play(): Promise<void> {
    this.paused = false;
    return Tonattrappe.antwort();
  }
  pause(): void {
    this.paused = true;
  }
}

const satz = (): Tonsatz => ({ text: "Ein Satz.", von: 0, bis: 9, ton: new Blob(["x"]), dauer: 2 }) as Tonsatz;
const ablehnung = (name: string) => () => Promise.reject(new DOMException("abgelehnt", name));

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("Audio", Tonattrappe);
  URL.createObjectURL = vi.fn(() => "blob:satz");
  URL.revokeObjectURL = vi.fn();
  Tonattrappe.antwort = () => Promise.resolve();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("Sprecher der Vertonung", () => {
  it("endet gut, wenn der Ton endet", async () => {
    const s = new Dienstsprecher();
    const lauf = s.spiele(satz(), "", () => {});
    await vi.advanceTimersByTimeAsync(10);
    Tonattrappe.zuletzt.onended?.();
    await expect(lauf).resolves.toBeUndefined();
  });

  it("lehnt Safari das Abspielen ab (nicht nur NotAllowedError), endet der Satz mit Grund statt zu hängen", async () => {
    Tonattrappe.antwort = ablehnung("AbortError");
    const s = new Dienstsprecher();
    const lauf = s.spiele(satz(), "", () => {});
    await expect(lauf).rejects.toThrow("Der Ton ließ sich nicht abspielen");
    Tonattrappe.antwort = ablehnung("NotAllowedError");
    await expect(s.spiele(satz(), "", () => {})).rejects.toThrow("erst nach einem Tippen");
  });

  it("ein Ton, der still stehen bleibt, gilt nach der Frist als hängend", async () => {
    const s = new Dienstsprecher();
    const lauf = s.spiele(satz(), "", () => {});
    const gescheitert = expect(lauf).rejects.toThrow("Der Ton blieb stehen");
    await vi.advanceTimersByTimeAsync(STILL_MS + 4_000);
    await gescheitert;
  });

  it("läuft der Ton weiter, schlägt die Wache nicht an", async () => {
    const s = new Dienstsprecher();
    let fertig = false;
    const lauf = s.spiele(satz(), "", () => {}).then(() => (fertig = true));
    for (let i = 0; i < 10; i++) {
      Tonattrappe.zuletzt.currentTime += 1.5;
      await vi.advanceTimersByTimeAsync(2_000);
    }
    expect(fertig).toBe(false);
    Tonattrappe.zuletzt.onended?.();
    await lauf;
    expect(fertig).toBe(true);
  });

  it("von Hand angehalten ist kein Stillstand und keine Ablehnung", async () => {
    let lehneAb: (g: unknown) => void = () => {};
    Tonattrappe.antwort = () => new Promise((_g, s) => (lehneAb = s));
    const s = new Dienstsprecher();
    let ausgang = "offen";
    const lauf = s.spiele(satz(), "", () => {}).then(() => (ausgang = "gut"), () => (ausgang = "fehler"));
    s.pause();
    lehneAb(new DOMException("unterbrochen", "AbortError"));
    await vi.advanceTimersByTimeAsync(STILL_MS * 3);
    expect(ausgang).toBe("offen");
    s.halt();
    await lauf;
    expect(ausgang).toBe("gut");
  });

  it("ein abgelöster Satz schweigt, wenn sein play() danach scheitert", async () => {
    let lehneAb: (g: unknown) => void = () => {};
    Tonattrappe.antwort = () => new Promise((_g, s) => (lehneAb = s));
    const s = new Dienstsprecher();
    const erster = s.spiele(satz(), "", () => {});
    s.halt();
    await expect(erster).resolves.toBeUndefined();
    Tonattrappe.antwort = () => Promise.resolve();
    const zweiter = s.spiele(satz(), "", () => {});
    lehneAb(new DOMException("abgelöst", "AbortError"));
    await vi.advanceTimersByTimeAsync(10);
    Tonattrappe.zuletzt.onended?.();
    await expect(zweiter).resolves.toBeUndefined();
  });
});
