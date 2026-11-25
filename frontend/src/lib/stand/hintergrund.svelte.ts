// Eigene Hintergrundbilder: Liste vom Server, gewähltes Bild im Browser gemerkt
import { del, get, upload } from "../api/client";
import { lies, merke } from "../speicher";

export interface Hintergrundbild {
  dateiname: string;
  groesse?: number;
}

class Hintergrund {
  bilder = $state<Hintergrundbild[]>([]);
  #nummer = $state(Number.parseInt(lies("bgIndex", "0"), 10) || 0);

  nummer = $derived(this.bilder.length ? Math.min(this.#nummer, this.bilder.length - 1) : 0);
  adresse = $derived(this.bilder.length ? this.adresseVon(this.bilder[this.nummer].dateiname) : "");

  adresseVon(name: string): string {
    return `/api/config/design/hintergrund/${encodeURIComponent(name)}`;
  }

  async laden(): Promise<void> {
    try {
      this.bilder = (await get("/api/config/design/hintergruende")).bilder ?? [];
    } catch {
      this.bilder = [];
    }
  }

  waehle(nummer: number): void {
    this.#nummer = nummer;
    merke("bgIndex", String(nummer));
  }

  blaettere(schritt: number): void {
    const n = this.bilder.length;
    if (n > 1) this.waehle((this.nummer + schritt + n) % n);
  }

  async hochladen(datei: File): Promise<void> {
    const daten = new FormData();
    daten.append("datei", datei);
    await upload("/api/config/design/hintergrund", daten);
    await this.laden();
  }

  async entferne(name: string): Promise<void> {
    await del(`/api/config/design/hintergrund/${encodeURIComponent(name)}`);
    await this.laden();
  }
}

export const hintergrund = new Hintergrund();
