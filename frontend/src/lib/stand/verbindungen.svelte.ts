// Lampen unten in der Leiste und Kacheln in den Einstellungen: Dienste, Fassung, Adresse des Assistenten
import { get } from "../api/client";
import { kiStatus } from "../api/ai";
import { healthCheck, ladeConfig, ladeVersion } from "../api/config";
import { ladeOberflaeche, ladeVerbindungen } from "../api/orte";
import type { Guete, Verbindung } from "../typen";

export interface Dienststand {
  stand: Guete | "aus";
  text: string;
}

const PRUEFT: Dienststand = { stand: "aus", text: "wird geprüft" };
const TAKT_MS = 60_000;

class Verbindungen {
  liste = $state<Verbindung[]>([]);
  app = $state<Dienststand>(PRUEFT);
  ki = $state<Dienststand>(PRUEFT);
  fassung = $state("");
  neueFassung = $state("");
  assistent = $state("");
  #uhr: ReturnType<typeof setInterval> | undefined;

  starte(): void {
    if (this.#uhr) return;
    void this.laden();
    this.#uhr = setInterval(() => void this.pruefen(), TAKT_MS);
  }

  halte(): void {
    clearInterval(this.#uhr);
    this.#uhr = undefined;
  }

  async laden(): Promise<void> {
    await Promise.allSettled([this.pruefen(), this.#fassungLaden(), this.#assistentLaden()]);
  }

  async pruefen(): Promise<void> {
    await Promise.allSettled([this.#appPruefen(), this.#kiPruefen(), this.#listeLaden()]);
  }

  async #appPruefen(): Promise<void> {
    try {
      await healthCheck();
      this.app = { stand: "gut", text: "BücherFreunde antwortet" };
    } catch {
      this.app = { stand: "schlecht", text: "BücherFreunde antwortet nicht" };
    }
  }

  async #kiPruefen(): Promise<void> {
    try {
      const { lm_studio: ki } = await ladeConfig();
      if (!ki?.aktiviert) this.ki = { stand: "aus", text: "KI ist ausgeschaltet" };
      else this.ki = (await kiStatus()).erreichbar ? { stand: "gut", text: "KI antwortet" } : { stand: "schlecht", text: "KI antwortet nicht" };
    } catch {
      this.ki = { stand: "schlecht", text: "KI antwortet nicht" };
    }
  }

  async #listeLaden(): Promise<void> {
    this.liste = await ladeVerbindungen();
  }

  async #assistentLaden(): Promise<void> {
    this.assistent = (await ladeOberflaeche()).assistent ?? "";
  }

  async #fassungLaden(): Promise<void> {
    this.fassung = (await ladeVersion()).version ?? "";
    const neu = await get("/api/config/update-check");
    this.neueFassung = neu.update_verfuegbar && neuerAls(neu.remote_version ?? "", this.fassung) ? neu.remote_version : "";
  }

  /** Adresse, unter der der Assistent eine Frage übernimmt; leer, wenn keiner eingerichtet ist */
  frageAdresse(frage: string): string {
    if (!this.assistent) return "";
    const ziel = new URL(this.assistent);
    ziel.searchParams.set("frage", frage);
    return ziel.href;
  }
}

/** Nur eine höhere Fassung ist neu, nicht jede andere. */
export function neuerAls(a: string, b: string): boolean {
  const [x, y] = [a, b].map((f) => f.split(".").map((t) => Number.parseInt(t, 10) || 0));
  for (let n = 0; n < Math.max(x.length, y.length); n++) {
    if ((x[n] ?? 0) !== (y[n] ?? 0)) return (x[n] ?? 0) > (y[n] ?? 0);
  }
  return false;
}

export const verbindungen = new Verbindungen();
