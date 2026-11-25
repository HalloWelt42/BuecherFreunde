// Wird das Gerät mit dem Finger bedient (Telefon hoch und quer, Tablet) oder ist das Fenster schmal? Entscheidet, wie der
// Leser startet (Textansicht, eigene Ansicht und Zoom), nicht, wie die Schale aussieht: das tun die Container-Breiten.
const ABFRAGE = "(hover: none) and (pointer: coarse), (max-width: 700px)";

class Geraet {
  #telefon = $state(false);

  constructor() {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const abfrage = window.matchMedia(ABFRAGE);
    this.#telefon = abfrage.matches;
    abfrage.addEventListener("change", (e) => (this.#telefon = e.matches));
  }

  get telefon(): boolean {
    return this.#telefon;
  }
}

export const geraet = new Geraet();
