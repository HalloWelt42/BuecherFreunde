// Was an diese Installation angeschlossen ist. Was fehlt, zeigt die Oberfläche nicht.
import { ladeOberflaeche } from "../api/orte";

export interface Anschluesse {
  ablage: "kellerwolke" | "geraet";
  anmeldung: "kellerwolke" | "eigen";
  bedeutung: boolean;
  assistent: string;
  /** Adresse des Lexikons; leer: kein Nachschlagen */
  nachschlag: string;
  /** Nachschlag aus den Hausdiensten oder das öffentliche Lexikon im Netz */
  nachschlag_art: "nachschlag" | "netz" | "";
  ki: boolean;
  vorlesen: boolean;
}

const OHNE: Anschluesse = { ablage: "geraet", anmeldung: "kellerwolke", bedeutung: false, assistent: "", nachschlag: "", nachschlag_art: "", ki: false, vorlesen: false };

class Anschlussstand {
  jetzt = $state<Anschluesse>(OHNE);
  geladen = $state(false);

  inWolke = $derived(this.jetzt.ablage === "kellerwolke");
  /** Wie die Taste heißt, die einen Artikel im Lexikon selbst öffnet */
  lexikonOeffnen = $derived(this.jetzt.nachschlag_art === "netz" ? "Im Lexikon öffnen" : "In Nachschlag öffnen");

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
