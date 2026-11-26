// Was an diese Installation angeschlossen ist. Was fehlt, zeigt die Oberfläche nicht.
import { ladeOberflaeche } from "../api/orte";
import { ich } from "./ich.svelte";

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
  /** Sandbox der Codeschmiede: Codestellen ausführen (BF-29); ohne sie keine Taste und kein Editor im Bau */
  ausfuehren: boolean;
}

const OHNE: Anschluesse = { ablage: "geraet", anmeldung: "kellerwolke", bedeutung: false, assistent: "", nachschlag: "", nachschlag_art: "", ki: false, vorlesen: false, ausfuehren: false };

class Anschlussstand {
  #roh = $state<Anschluesse>(OHNE);
  /**
   * Was das Profil nicht darf (BF-78), sieht es nicht, auch wenn es angeschlossen ist: KI, Nachschlagen, Ausführen. Bis das
   * Profil feststeht, gilt der Server.
   */
  #sichtbar = $derived.by((): Anschluesse => {
    const r = this.#roh;
    if (!ich.jetzt) return r;
    const ki = ich.darf("ki");
    return {
      ...r,
      ki: r.ki && ki,
      assistent: ki ? r.assistent : "",
      bedeutung: r.bedeutung && ki,
      nachschlag: ich.darf("nachschlagen") ? r.nachschlag : "",
      ausfuehren: r.ausfuehren && ich.darf("ausfuehren"),
    };
  });
  geladen = $state(false);

  get jetzt(): Anschluesse {
    return this.#sichtbar;
  }
  set jetzt(wert: Anschluesse) {
    this.#roh = wert;
  }

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
