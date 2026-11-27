// Eine Stimmprobe abspielen (BF-113, BF-114): der Server legt je Stimme einen festen Satz als Ton ab, meist schon vorab gesprochen.
// Im Tippen wird ein Tonelement freigegeben (sonst bleibt das Telefon stumm), danach kommt die Probe in dasselbe Element. Solange
// sie geholt wird und noch nicht klingt, gilt `laedt` (der Knopf dreht); bis sie zu Ende ist, `spielt`. Ohne Adresse spricht
// die Stimme des Geräts den Text. Eine neue Probe löst die laufende ab.
import type { Probenton } from "../api/vorlesen";
import { stilleAdresse } from "./ton";

export class Stimmprobe {
  laedt = $state(false);
  spielt = $state(false);
  #ton: HTMLAudioElement | null = null;

  /** Im Tippen rufen. `holen` fragt den Server, `ohneTon` spricht den Text mit der Stimme des Geräts. Scheitert das Abspielen,
   *  endet die Probe und der Grund kommt als Fehler zurück. */
  async spiele(holen: () => Promise<Probenton>, ohneTon: (text: string) => void, tempo = 1): Promise<void> {
    this.halt();
    const ton = new Audio(stilleAdresse());
    void ton.play().catch(() => undefined);
    this.#ton = ton;
    this.laedt = this.spielt = true;
    const gilt = () => this.#ton === ton;
    try {
      const probe = await holen();
      if (!gilt()) return;
      if (!probe.url) {
        this.#ende();
        return ohneTon(probe.text);
      }
      ton.onplaying = () => void (gilt() && (this.laedt = false));
      ton.onended = ton.onerror = () => void (gilt() && this.#ende());
      ton.src = probe.url;
      ton.preservesPitch = true;                            // schneller heißt nicht höher
      ton.defaultPlaybackRate = ton.playbackRate = tempo;
      await ton.play();
    } catch (e) {
      if (!gilt()) return;
      this.#ende();
      throw e;
    }
  }

  halt(): void {
    this.#ton?.pause();
    this.#ende();
  }

  #ende(): void {
    this.#ton = null;
    this.laedt = this.spielt = false;
  }
}
