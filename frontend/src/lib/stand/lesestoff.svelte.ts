// Ohne Netz lesen: eine ausdrückliche Wahl je Gerät, Vorgabe aus. Was gemerkt ist, hält der Dienst im Hintergrund; hier wird
// gefragt und geschaltet. Ohne Dienst bleibt der Stand null und die Einstellungen zeigen die Wahl nicht.
import { sprich, type Lesestoffstand } from "../hintergrund";

class Lesestoff {
  stand = $state<Lesestoffstand | null>(null);
  geladen = $state(false);

  async laden(): Promise<void> {
    this.stand = await sprich({ art: "lesestoff" });
    this.geladen = true;
  }

  /** Aus heißt auch: die gemerkten Bücher gehen vom Gerät (vorher fragt die Ansicht nach) */
  async schalte(an: boolean): Promise<void> {
    this.stand = await sprich({ art: "lesestoff-an", an });
  }

  async leere(): Promise<void> {
    this.stand = await sprich({ art: "lesestoff-leeren" });
  }
}

export const lesestoff = new Lesestoff();
