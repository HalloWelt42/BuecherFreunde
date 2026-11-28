// Vorlesen mit den Stimmen, die Browser und Gerät mitbringen; geht überall und ohne Anschluss. Jeder Satz ist eine eigene
// Äußerung, weil Browser lange still abbrechen.
//
// Nur hier wird die Sprachausgabe des Browsers angefasst. Manche Browser sperren sie zum Schutz vor Wiedererkennung und werfen
// dann schon beim Fragen nach den Stimmen (BF-121: so brach das ganze Feld Vorlesen ab). Gesperrt heißt hier: keine Stimme des
// Geräts; die Stimmen der Vertonung bleiben.
import { saetzeMitLage } from "./saetze";
import type { Sprecher, Stimme, Tonsatz } from "./typen";

/** Die Sprachausgabe des Browsers, wenn er sie zulässt */
function sprachausgabe(): SpeechSynthesis | null {
  try {
    return typeof window !== "undefined" && "speechSynthesis" in window ? window.speechSynthesis : null;
  } catch {
    return null;
  }
}

/** Was der Browser an Stimmen nennt; gesperrt: keine */
function stimmenDesBrowsers(): SpeechSynthesisVoice[] {
  try {
    return sprachausgabe()?.getVoices() ?? [];
  } catch {
    return [];
  }
}

export const geraetDa = () => sprachausgabe() !== null;

/** Stimmen des Geräts, deutsche zuerst. Manche Browser liefern sie erst nach einem Augenblick (`beiNeuenStimmen`). */
export function geraetestimmen(): Stimme[] {
  const deutsch = (s: SpeechSynthesisVoice) => s.lang.toLowerCase().startsWith("de");
  return stimmenDesBrowsers()
    .toSorted((a, b) => Number(deutsch(b)) - Number(deutsch(a)) || a.name.localeCompare(b.name, "de"))
    .map((s) => ({ id: `geraet:${s.voiceURI}`, name: deutsch(s) ? s.name : `${s.name} (${s.lang})`, gruppe: "Dieses Gerät" }));
}

/** Meldet der Browser später (andere) Stimmen, ruft er `tun` */
export function beiNeuenStimmen(tun: () => void): void {
  try {
    sprachausgabe()?.addEventListener?.("voiceschanged", tun);
  } catch {
    // gesperrt: es kommen keine
  }
}

/** Was gerade gesprochen wird, endet */
function verstumme(): void {
  try {
    sprachausgabe()?.cancel();
  } catch {
    // gesperrt: es spricht nichts
  }
}

/** Ein Satz mit der Stimme, die das Gerät für Deutsch nimmt (Probe der Gerätestimme); false, wenn der Browser es nicht zulässt */
export function sprichEinmal(text: string): boolean {
  const s = sprachausgabe();
  if (!s) return false;
  try {
    s.cancel();
    const a = new SpeechSynthesisUtterance(text);
    a.lang = "de-DE";
    s.speak(a);
    return true;
  } catch {
    return false;
  }
}

const ZEICHEN_JE_S = 14;

export class Geraetesprecher implements Sprecher {
  tempo = 1;
  #lauf = 0;
  #jetzt: { sprich: () => void; fertig: () => void } | null = null;

  entsperre(): void {
    if (!this.#jetzt) verstumme();
  }

  async *saetze(text: string): AsyncIterable<Tonsatz> {
    for (const s of saetzeMitLage(text)) yield { ...s, ton: null, dauer: s.text.length / ZEICHEN_JE_S };
  }

  spiele(satz: Tonsatz, stimme: string, fortschritt: (anteil: number) => void): Promise<void> {
    const wahl = stimmenDesBrowsers().find((s) => s.voiceURI === stimme);
    return new Promise<void>((gut, schlecht) => {
      const fertig = () => {
        this.#lauf++;
        this.#jetzt = null;
        gut();
      };
      const sprich = () => {
        const lauf = ++this.#lauf;
        const a = new SpeechSynthesisUtterance(satz.text.replace(/\s+/g, " "));
        if (wahl) a.voice = wahl;
        a.lang = wahl?.lang ?? "de-DE";
        a.rate = this.tempo;
        a.onboundary = (e) => lauf === this.#lauf && fortschritt(Math.min(1, e.charIndex / Math.max(1, satz.text.length)));
        a.onend = () => lauf === this.#lauf && fertig();
        a.onerror = (e) => {
          if (lauf !== this.#lauf || e.error === "canceled" || e.error === "interrupted") return;
          this.#jetzt = null;
          schlecht(new Error("Die Stimme des Geräts brach ab"));
        };
        try {
          const s = sprachausgabe();
          if (!s) throw new Error("ohne Sprachausgabe");
          s.speak(a);
        } catch {
          this.#jetzt = null;
          schlecht(new Error("Der Browser lässt die Stimme des Geräts nicht sprechen"));
        }
      };
      this.#jetzt = { sprich, fertig };
      sprich();
    });
  }

  // Anhalten und Weitersprechen können viele Browser nicht zuverlässig: der Satz beginnt neu
  pause(): void {
    this.#lauf++;
    verstumme();
  }
  weiter(): void {
    this.#jetzt?.sprich();
  }
  halt(): void {
    this.#jetzt?.fertig();
    verstumme();
  }
}
