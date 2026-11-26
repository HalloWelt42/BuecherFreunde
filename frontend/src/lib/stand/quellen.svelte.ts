// Die Quellen für Angaben mit ihrem gemerkten Stand. Laden fragt keine Quelle, erst "Neu prüfen" tut es, je Quelle höchstens einmal in der Minute.
import { ladeQuellen, pruefeQuelle, type Quellenstand } from "../api/metadata";

class Quellen {
  liste = $state<Quellenstand[]>([]);
  geladen = $state(false);
  fehler = $state("");
  prueft = $state("");

  /** Quellen für Angaben zu Büchern, die gefragt werden können */
  buecher = $derived(this.liste.filter((q) => q.art === "buch" && q.bereit));
  /** In der Einrichtung abgeschaltet? Erst wenn der Stand da ist; vorher gilt nichts als aus */
  aus(kennung: string): boolean {
    return this.liste.find((q) => q.kennung === kennung)?.aktiv === false;
  }

  /** Kennung -> Name, wie die Oberfläche sie nennt */
  namen = $derived(Object.fromEntries(this.liste.map((q) => [q.kennung, q.name])));

  async laden(): Promise<void> {
    try {
      this.liste = await ladeQuellen();
      this.fehler = "";
    } catch (e) {
      this.fehler = e instanceof Error ? e.message : String(e);
    } finally {
      this.geladen = true;
    }
  }

  /** Einmal laden, wenn es noch niemand getan hat */
  async bereit(): Promise<void> {
    if (!this.geladen) await this.laden();
  }

  async pruefe(kennung: string): Promise<Quellenstand | null> {
    this.prueft = kennung;
    try {
      const neu = await pruefeQuelle(kennung);
      this.liste = this.liste.map((q) => (q.kennung === kennung ? neu : q));
      return neu;
    } finally {
      this.prueft = "";
    }
  }
}

export const quellen = new Quellen();
