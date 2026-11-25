// Vorlesen mit den Stimmen, die Browser und Gerät mitbringen; geht überall und ohne Anschluss. Lange Texte gehen in kurzen
// Stücken hinein, weil Browser lange Äußerungen still abbrechen.
import { saetze } from "./saetze";
import type { Beobachter, Stimme, Vorleser } from "./typen";

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

export class Geraetevorleser implements Vorleser {
  #lauf = 0;

  entsperre(): void {
    if (geraetDa()) speechSynthesis.cancel();
  }

  lies(text: string, stimme: string, bei: Beobachter): void {
    this.halt();
    const lauf = ++this.#lauf;
    const wahl = speechSynthesis.getVoices().find((s) => s.voiceURI === stimme);
    const stuecke = saetze(text);
    const naechstes = (n: number) => {
      if (lauf !== this.#lauf) return;
      if (n >= stuecke.length) return bei.ende();
      const a = new SpeechSynthesisUtterance(stuecke[n]);
      if (wahl) a.voice = wahl;
      a.lang = wahl?.lang ?? "de-DE";
      a.onend = () => naechstes(n + 1);
      a.onerror = (e) => lauf === this.#lauf && e.error !== "canceled" && e.error !== "interrupted" && bei.fehler("Die Stimme des Geräts brach ab");
      speechSynthesis.speak(a);
    };
    bei.klingt();
    naechstes(0);
  }

  halt(): void {
    this.#lauf++;
    if (geraetDa()) speechSynthesis.cancel();
  }
}
