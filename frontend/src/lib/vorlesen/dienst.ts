// Vorlesen mit der Vertonung: Satz für Satz als Ton vom Server. Gespielt wird über ein Tonelement, weil nur das am
// gesperrten Telefon weiterläuft und auf Kopfhörertasten hört.
import { vorleseStrom } from "../api/vorlesen";
import { lageAb } from "./saetze";
import { mitPause, stilleAdresse } from "./ton";
import type { Sprecher, Tonsatz } from "./typen";
import { zeilenAus } from "./zeilen";

interface Zeile {
  art: "satz" | "ende" | "fehler";
  text?: string;
  ton?: string;
  meldung?: string;
}

const PAUSE_S = 0.3;

const tonAus = (basis64: string): ArrayBuffer => Uint8Array.from(atob(basis64), (z) => z.charCodeAt(0)).buffer;

export class Dienstsprecher implements Sprecher {
  #element: HTMLAudioElement | null = null;
  #frei = false;
  #tempo = 1;
  /** Beendet den laufenden Satz */
  #fertig: (() => void) | null = null;

  #ton(): HTMLAudioElement {
    if (!this.#element) {
      this.#element = new Audio();
      this.#element.preload = "auto";
    }
    return this.#element;
  }

  get tempo(): number {
    return this.#tempo;
  }
  set tempo(wert: number) {
    this.#tempo = wert;
    if (this.#element) this.#stelleTempo(this.#element);
  }

  // Schneller heißt nicht höher: die Tonhöhe bleibt
  #stelleTempo(t: HTMLAudioElement): void {
    t.preservesPitch = true;
    t.defaultPlaybackRate = this.#tempo;
    t.playbackRate = this.#tempo;
  }

  entsperre(): void {
    if (this.#frei || this.#fertig) return;
    const t = this.#ton();
    t.src = stilleAdresse();
    this.#frei = true;
    void t.play().catch(() => (this.#frei = false));
  }

  async *saetze(text: string, stimme: string, abbruch: AbortSignal): AsyncIterable<Tonsatz> {
    const antwort = await vorleseStrom(text, stimme, abbruch);
    if (!antwort.body) throw new Error("Vorlesen brach ab");
    let ab = 0;
    for await (const z of zeilenAus<Zeile>(antwort.body)) {
      if (z.art === "fehler") throw new Error(z.meldung || "Vorlesen brach ab");
      if (z.art === "ende") return;
      if (!z.ton) continue;
      const [von, bis] = lageAb(text, z.text ?? "", ab);
      ab = bis;
      yield { text: z.text ?? "", von, bis, ...mitPause(tonAus(z.ton), PAUSE_S) };
    }
    // Ohne die Schlusszeile ist der Strom gerissen; was fehlt, holt der Nächste
    if (text.slice(ab).trim()) throw new Error("Die Vertonung hat mitten im Text aufgehört");
  }

  spiele(satz: Tonsatz, _stimme: string, fortschritt: (anteil: number) => void): Promise<void> {
    const t = this.#ton();
    const adresse = URL.createObjectURL(satz.ton ?? new Blob());
    return new Promise<void>((gut, schlecht) => {
      const raeume = () => {
        this.#fertig = null;
        t.onended = t.onerror = t.ontimeupdate = null;
        URL.revokeObjectURL(adresse);
      };
      this.#fertig = () => {
        t.pause();
        raeume();
        gut();
      };
      t.onended = () => {
        raeume();
        gut();
      };
      t.onerror = () => {
        raeume();
        schlecht(new Error("Der Ton ließ sich nicht abspielen"));
      };
      t.ontimeupdate = () => {
        const dauer = (Number.isFinite(t.duration) ? t.duration : satz.dauer) - PAUSE_S;
        if (dauer > 0) fortschritt(Math.min(1, t.currentTime / dauer));
      };
      t.src = adresse;
      this.#stelleTempo(t);
      t.play().catch((grund: unknown) => {
        // Abgelöst durch den nächsten Satz oder eine Pause ist kein Fehler
        if (!(grund instanceof DOMException) || grund.name !== "NotAllowedError" || !this.#fertig) return;
        raeume();
        this.#frei = false;
        schlecht(new Error("Der Browser gibt den Ton erst nach einem Tippen frei"));
      });
    });
  }

  pause(): void {
    this.#element?.pause();
  }
  weiter(): void {
    if (this.#fertig) void this.#element?.play().catch(() => undefined);
  }
  halt(): void {
    this.#fertig?.();
  }
}
