// Vorlesen mit den Stimmen, die Browser und Gerät mitbringen; geht überall und ohne Anschluss. Jeder Satz ist eine eigene
// Äußerung, weil Browser lange still abbrechen.
import { saetzeMitLage } from "./saetze";
import type { Sprecher, Stimme, Tonsatz } from "./typen";

export const geraetDa = () => typeof window !== "undefined" && "speechSynthesis" in window;

/** Stimmen des Geräts, deutsche zuerst. Manche Browser liefern sie erst nach einem Augenblick (`voiceschanged`). */
export function geraetestimmen(): Stimme[] {
  if (!geraetDa()) return [];
  const deutsch = (s: SpeechSynthesisVoice) => s.lang.toLowerCase().startsWith("de");
  return speechSynthesis
    .getVoices()
    .toSorted((a, b) => Number(deutsch(b)) - Number(deutsch(a)) || a.name.localeCompare(b.name, "de"))
    .map((s) => ({ id: `geraet:${s.voiceURI}`, name: deutsch(s) ? s.name : `${s.name} (${s.lang})`, gruppe: "Dieses Gerät" }));
}

const ZEICHEN_JE_S = 14;

export class Geraetesprecher implements Sprecher {
  tempo = 1;
  #lauf = 0;
  #jetzt: { sprich: () => void; fertig: () => void } | null = null;

  entsperre(): void {
    if (geraetDa() && !this.#jetzt) speechSynthesis.cancel();
  }

  async *saetze(text: string): AsyncIterable<Tonsatz> {
    for (const s of saetzeMitLage(text)) yield { ...s, ton: null, dauer: s.text.length / ZEICHEN_JE_S };
  }

  spiele(satz: Tonsatz, stimme: string, fortschritt: (anteil: number) => void): Promise<void> {
    const wahl = speechSynthesis.getVoices().find((s) => s.voiceURI === stimme);
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
        speechSynthesis.speak(a);
      };
      this.#jetzt = { sprich, fertig };
      sprich();
    });
  }

  // Anhalten und Weitersprechen können viele Browser nicht zuverlässig: der Satz beginnt neu
  pause(): void {
    this.#lauf++;
    if (geraetDa()) speechSynthesis.cancel();
  }
  weiter(): void {
    this.#jetzt?.sprich();
  }
  halt(): void {
    this.#jetzt?.fertig();
    if (geraetDa()) speechSynthesis.cancel();
  }
}
