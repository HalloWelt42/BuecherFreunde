// Was an diese Installation angeschlossen ist. Was fehlt, zeigt die Oberfläche nicht.
import { ladeOberflaeche } from "../api/orte";

export interface Anschluesse {
  ablage: "kellerwolke" | "geraet";
  anmeldung: "kellerwolke" | "eigen";
  bedeutung: boolean;
  assistent: string;
  nachschlag: string;
  ki: boolean;
  vorlesen: boolean;
}

const OHNE: Anschluesse = { ablage: "geraet", anmeldung: "kellerwolke", bedeutung: false, assistent: "", nachschlag: "", ki: false, vorlesen: false };

class Anschlussstand {
  jetzt = $state<Anschluesse>(OHNE);
  geladen = $state(false);

  inWolke = $derived(this.jetzt.ablage === "kellerwolke");

  /** Scheitert es, gilt das Nötigste; der nächste Start fragt neu. */
  async laden(): Promise<void> {
    try {
      this.jetzt = { ...OHNE, ...(await ladeOberflaeche()).anschluesse };
    } catch {
      // ohne Antwort bleibt es beim Nötigsten
    }
    this.geladen = true;
  }
}

export const anschluesse = new Anschlussstand();
