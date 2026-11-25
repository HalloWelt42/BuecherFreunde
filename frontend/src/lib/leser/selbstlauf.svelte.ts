// Von selbst lesen: gescrollt rollt die Fläche ruhig weiter, geblättert kommt nach der Zeit für einen Schirm der nächste. Das
// Tempo zählt Zeilen je Minute, für beide Arten gleich. Die Leertaste hält an.
import type { Hilfeort } from "./sitzung.svelte";

class Selbstlauf {
  an = $state(false);
  pausiert = $state(false);
  #ort: Hilfeort | null = null;
  #bild = 0;
  #zuletzt = 0;
  #rest = 0;
  #seit = 0;
  /** Zeilen je Minute */
  tempo = 18;

  starte(ort: Hilfeort, tempo: number): void {
    this.halt();
    [this.#ort, this.tempo] = [ort, tempo];
    [this.an, this.pausiert] = [true, false];
    this.#zuletzt = performance.now();
    this.#bild = requestAnimationFrame((t) => this.#schritt(t));
  }

  pauseOderWeiter(): void {
    if (!this.an) return;
    this.pausiert = !this.pausiert;
    this.#zuletzt = performance.now();
  }

  halt(): void {
    cancelAnimationFrame(this.#bild);
    [this.an, this.pausiert, this.#ort, this.#rest, this.#seit] = [false, false, null, 0, 0];
  }

  #schritt(jetzt: number): void {
    const ort = this.#ort;
    if (!ort || !this.an) return;
    const dt = Math.min(0.25, (jetzt - this.#zuletzt) / 1000);
    this.#zuletzt = jetzt;
    if (!this.pausiert) {
      const zeile = ort.zeilenhoehe();
      let weiter = true;
      if (ort.art() === "scrollen") {
        // Bruchteile sammeln: nur ganze Bildpunkte bewegen, sonst zittert die Schrift
        this.#rest += (this.tempo / 60) * zeile * dt;
        const px = Math.floor(this.#rest);
        if (px >= 1) {
          this.#rest -= px;
          weiter = ort.rolle(px);
        }
      } else {
        this.#seit += dt;
        const schirm = Math.max(1, (ort.blatt()?.height ?? 600) / zeile);
        if (this.#seit >= (schirm / this.tempo) * 60) {
          this.#seit = 0;
          weiter = ort.blaettere();
        }
      }
      if (!weiter) return this.halt();
    }
    this.#bild = requestAnimationFrame((t) => this.#schritt(t));
  }
}

export const selbstlauf = new Selbstlauf();
