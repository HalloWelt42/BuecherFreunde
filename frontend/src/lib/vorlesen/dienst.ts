// Vorlesen mit dem Sprechdienst: Satz für Satz als Ton vom Server, lückenlos gespielt. Gelesen wird nur wenig voraus, so
// spricht der Dienst ein ganzes Buch nicht in einem Zug durch.
import { vorleseStrom } from "../api/vorlesen";
import type { Beobachter, Vorleser } from "./typen";
import { Vorlauf } from "./vorlauf";
import { zeilenAus } from "./zeilen";

interface Zeile {
  art: "satz" | "ende" | "fehler";
  ton?: string;
  meldung?: string;
}

const PAUSE_S = 0.3;
const VORRAT_S = 45;

function tonAus(basis64: string): ArrayBuffer {
  return Uint8Array.from(atob(basis64), (z) => z.charCodeAt(0)).buffer;
}

const warte = (ms: number) => new Promise((r) => setTimeout(r, ms));

export class Dienstvorleser implements Vorleser {
  #ton: AudioContext | null = null;
  #abbruch: AbortController | null = null;
  #quellen = new Set<AudioBufferSourceNode>();
  #vorlauf = new Vorlauf();

  entsperre(): AudioContext {
    const ton = (this.#ton ??= new AudioContext());
    void ton.resume().catch(() => undefined);
    return ton;
  }

  lies(text: string, stimme: string, bei: Beobachter): void {
    this.halt();
    const abbruch = new AbortController();
    this.#abbruch = abbruch;
    void this.#spiele(text, stimme, bei, abbruch).catch((grund) => {
      if (abbruch.signal.aborted) return;
      this.halt();
      bei.fehler(grund instanceof Error ? grund.message : "Vorlesen brach ab");
    });
  }

  async #spiele(text: string, stimme: string, bei: Beobachter, abbruch: AbortController): Promise<void> {
    const ton = this.entsperre();
    const vorlauf = this.#vorlauf;
    let bereit: AudioBuffer[] = [];
    let zeitpunkt = 0;
    let spielt = false;
    let fertig = false;

    const pruefeEnde = () => {
      if (!fertig || this.#quellen.size || bereit.length || abbruch.signal.aborted) return;
      vorlauf.beenden();
      this.#abbruch = null;
      bei.ende();
    };
    const plane = (puffer: AudioBuffer) => {
      const quelle = ton.createBufferSource();
      quelle.buffer = puffer;
      quelle.connect(ton.destination);
      zeitpunkt = Math.max(zeitpunkt, ton.currentTime + 0.05);
      quelle.start(zeitpunkt);
      zeitpunkt += puffer.duration + PAUSE_S;
      this.#quellen.add(quelle);
      quelle.onended = () => {
        this.#quellen.delete(quelle);
        pruefeEnde();
      };
    };
    const weiter = () => {
      if (!spielt) {
        if (!bereit.length || !vorlauf.genug(bereit.reduce((s, p) => s + p.duration, 0), fertig)) return;
        spielt = true;
        bei.klingt();
      }
      bereit.forEach(plane);
      bereit = [];
    };

    vorlauf.beginnen();
    bei.wartet();
    const antwort = await vorleseStrom(text, stimme, abbruch.signal);
    if (!antwort.body) throw new Error("Vorlesen brach ab");
    for await (const z of zeilenAus<Zeile>(antwort.body)) {
      if (abbruch.signal.aborted) return;
      if (z.art === "fehler") throw new Error(z.meldung || "Vorlesen brach ab");
      if (z.art === "ende") break;
      if (!z.ton) continue;
      const puffer = await ton.decodeAudioData(tonAus(z.ton));
      if (abbruch.signal.aborted) return;
      if (spielt && !this.#quellen.size && ton.currentTime > zeitpunkt) {
        vorlauf.abgerissen();
        spielt = false;
        bei.wartet();
      }
      bereit.push(puffer);
      weiter();
      while (!abbruch.signal.aborted && zeitpunkt - ton.currentTime > VORRAT_S) await warte(500);
    }
    fertig = true;
    weiter();
    pruefeEnde();
  }

  halt(): void {
    this.#abbruch?.abort();
    this.#abbruch = null;
    for (const q of this.#quellen) {
      q.onended = null;
      try {
        q.stop();
      } catch {
        // schon verklungen
      }
    }
    this.#quellen.clear();
  }
}
