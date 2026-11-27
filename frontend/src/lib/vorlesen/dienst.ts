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
/** So lange darf ein Ton ohne Fortschritt stehen, ehe er als hängend gilt (am Telefon bleibt er manchmal still stehen) */
export const STILL_MS = 12_000;
const BLICK_MS = 2_000;

const tonAus = (basis64: string): ArrayBuffer => Uint8Array.from(atob(basis64), (z) => z.charCodeAt(0)).buffer;

export class Dienstsprecher implements Sprecher {
  #element: HTMLAudioElement | null = null;
  #frei = false;
  #tempo = 1;
  /** Angehalten von Hand: ein stehender Ton ist dann kein Fehler */
  #angehalten = false;
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
    this.#angehalten = false;
    return new Promise<void>((gut, schlecht) => {
      // Endet der Ton nie (kein ended, kein Fehler), bliebe das Vorlesen für immer an: die Wache merkt, wenn er steht
      let [stand, seit] = [-1, Date.now()];
      const wache = setInterval(() => {
        if (this.#angehalten || t.currentTime !== stand) return void ([stand, seit] = [t.currentTime, Date.now()]);
        if (Date.now() - seit >= STILL_MS) scheitere("Der Ton blieb stehen");
      }, BLICK_MS);
      const raeume = () => {
        clearInterval(wache);
        this.#fertig = null;
        t.onended = t.onerror = t.ontimeupdate = null;
        URL.revokeObjectURL(adresse);
      };
      const beende = () => {
        t.pause();
        raeume();
        gut();
      };
      // Nur der Satz, der gerade gilt, kann scheitern; ein abgelöster schweigt
      const scheitere = (grund: string) => {
        if (this.#fertig !== beende) return;
        t.pause();
        raeume();
        schlecht(new Error(grund));
      };
      this.#fertig = beende;
      t.onended = () => {
        if (this.#fertig !== beende) return;
        raeume();
        gut();
      };
      t.onerror = () => scheitere("Der Ton ließ sich nicht abspielen");
      t.ontimeupdate = () => {
        const dauer = (Number.isFinite(t.duration) ? t.duration : satz.dauer) - PAUSE_S;
        if (dauer > 0) fortschritt(Math.min(1, t.currentTime / dauer));
      };
      t.src = adresse;
      this.#stelleTempo(t);
      t.play().catch((grund: unknown) => {
        // Abgelöst durch den nächsten Satz oder angehalten, bevor er klang: kein Fehler
        if (this.#fertig !== beende || this.#angehalten) return;
        if (grund instanceof DOMException && grund.name === "NotAllowedError") {
          this.#frei = false;
          return scheitere("Der Browser gibt den Ton erst nach einem Tippen frei");
        }
        scheitere("Der Ton ließ sich nicht abspielen");
      });
    });
  }

  pause(): void {
    this.#angehalten = true;
    this.#element?.pause();
  }
  weiter(): void {
    this.#angehalten = false;
    if (this.#fertig) void this.#element?.play().catch(() => undefined);
  }
  halt(): void {
    this.#angehalten = false;
    this.#fertig?.();
  }
}
