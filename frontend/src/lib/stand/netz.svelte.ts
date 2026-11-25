// Antwortet der Server? Gemerkt bei jeder Anfrage; ist er weg, fragt die Seite nach, bis er wieder da ist.

const NACHFRAGEN_MS = 8000;
type Zuhoerer = () => void;

class Netz {
  weg = $state(false);
  #uhr: ReturnType<typeof setInterval> | undefined;
  #wiederDa = new Set<Zuhoerer>();

  beiWiederDa(tun: Zuhoerer): () => void {
    this.#wiederDa.add(tun);
    return () => this.#wiederDa.delete(tun);
  }

  da(): void {
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
      if ((await fetch("/api/health", { cache: "no-store" })).ok) this.da();
    } catch {
      // noch nicht
    }
  }
}

export const netz = new Netz();
