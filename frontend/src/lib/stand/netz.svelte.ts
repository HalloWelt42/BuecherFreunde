// Antwortet der Server? Gemerkt bei jeder Anfrage; ist er weg, fragt die Seite nach, bis er wieder da ist. Bleibt er bei
// sichtbarer Seite länger weg, lädt sie sich einmal selbst neu (BF-108): am Telefon kann die Verbindung (HTTP/3) tot sein, ohne
// dass der Browser eine neue aufbaut; dann kommt keine Anfrage mehr an, obwohl der Server läuft. Höchstens einmal in einer
// Weile, damit ein wirklich fehlender Server keine Schleife auslöst.

const NACHFRAGEN_MS = 8000;
/** So viele Nachfragen ohne Antwort, dann lädt die sichtbare Seite neu */
export const NEU_LADEN_NACH = 4;
/** Frühestens so lange nach dem letzten selbst ausgelösten Neuladen wieder */
export const NEU_LADEN_ABSTAND_MS = 5 * 60_000;
const ZULETZT_NEU = "bf-netz-neu-geladen";
type Zuhoerer = () => void;

class Netz {
  weg = $state(false);
  #uhr: ReturnType<typeof setInterval> | undefined;
  #wiederDa = new Set<Zuhoerer>();
  #vergeblich = 0;

  constructor(private neuLaden: () => void = () => location.reload()) {}

  beiWiederDa(tun: Zuhoerer): () => void {
    this.#wiederDa.add(tun);
    return () => this.#wiederDa.delete(tun);
  }

  da(): void {
    this.#vergeblich = 0;
    if (!this.weg) return;
    this.weg = false;
    clearInterval(this.#uhr);
    for (const tun of this.#wiederDa) tun();
  }

  fort(): void {
    if (this.weg) return;
    this.weg = true;
    this.#uhr = setInterval(() => void this.pruefe(), NACHFRAGEN_MS);
    addEventListener("online", () => void this.pruefe(), { once: true });
  }

  async pruefe(): Promise<void> {
    try {
      if ((await fetch("/api/health", { cache: "no-store" })).ok) return this.da();
    } catch {
      // noch nicht
    }
    this.#vergeblich++;
    if (this.#vergeblich >= NEU_LADEN_NACH && document.visibilityState === "visible" && this.#darfNeuLaden()) this.neuLaden();
  }

  #darfNeuLaden(): boolean {
    try {
      const zuletzt = Number(sessionStorage.getItem(ZULETZT_NEU) ?? 0);
      if (Date.now() - zuletzt < NEU_LADEN_ABSTAND_MS) return false;
      sessionStorage.setItem(ZULETZT_NEU, String(Date.now()));
      return true;
    } catch {
      return false;
    }
  }
}

export { Netz };
export const netz = new Netz();
