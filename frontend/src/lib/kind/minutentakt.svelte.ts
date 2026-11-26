// Der Minutentakt der Kinderuhr: schlägt einmal je Minute, genau am Minutenwechsel der Uhr des Geräts. Dazwischen ändert sich
// nichts, so bleibt das Bild ruhig. Läuft nur, solange jemand zusieht; der Zähler der Lesezeit zum Server ist davon getrennt.

export class Minutentakt {
  jetzt = $state(new Date());
  #uhr: ReturnType<typeof setTimeout> | undefined;
  #zuseher = 0;

  constructor(private zeit: () => Date = () => new Date()) {}

  #naechster(): void {
    const n = this.zeit();
    const bisWechsel = 60_000 - (n.getSeconds() * 1000 + n.getMilliseconds());
    this.#uhr = setTimeout(() => {
      this.jetzt = this.zeit();
      this.#naechster();
    }, bisWechsel + 20);
  }

  /** Beginnt zu zählen; liefert das Ende */
  beobachte(): () => void {
    if (this.#zuseher++ === 0) {
      this.jetzt = this.zeit();
      this.#naechster();
    }
    return () => {
      if (--this.#zuseher === 0) clearTimeout(this.#uhr);
    };
  }
}

export const minutentakt = new Minutentakt();
