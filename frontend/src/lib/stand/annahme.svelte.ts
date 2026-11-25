// Die Annahme in der Oberfläche: Einträge des Servers (Ereignisstrom) zusammen mit dem, was dieser Browser hochlädt
import { annahmeDienst, annahmeEreignisse, annahmeErneut, blendeAnnahmenAus, entferneAnnahme, ladeAnnahmen } from "../api/annahme";
import { hochladenZaehlen } from "../api/client";
import { Hochlader } from "../annahme/hochlader";
import { pruefsumme } from "../annahme/pruefsumme";
import type { AnnahmeEintrag, AnnahmeListe, AnnahmeZaehler, Hochladung } from "../annahme/typen";
import { fuegeZusammen, laeuftVonSelbst, type Annahmezeile } from "../annahme/zeilen";
import { bestand } from "./bestand.svelte";

const IM_REGAL = ["wissen", "fertig", "ohne_text"];
const LEER: AnnahmeZaehler = { alle: 0, laeuft: 0, klaeren: 0, da: 0, fertig: 0 };
const AUFFRISCHEN_MS = 800;

class Annahme {
  eintraege = $state<AnnahmeEintrag[]>([]);
  zaehler = $state<AnnahmeZaehler>(LEER);
  hochladungen = $state<Hochladung[]>([]);
  /** Antwortet der Server auf die Annahme? Vor der ersten Antwort unbekannt */
  grund = $state("");
  geladen = $state(false);

  zeilen = $derived<Annahmezeile[]>(fuegeZusammen(this.eintraege, this.hochladungen));
  laufend = $derived(this.zeilen.filter((z) => z.gruppe === "laeuft"));
  vonSelbst = $derived(this.laufend.filter(laeuftVonSelbst).length);
  angehalten = $derived(this.laufend.length - this.vonSelbst);

  #hochlader = new Hochlader(annahmeDienst, pruefsumme);
  #stromAus: (() => void) | null = null;
  #uhr: ReturnType<typeof setTimeout> | undefined;
  #zaehlt = false;

  constructor() {
    this.#hochlader.beiAenderung((liste) => {
      this.hochladungen = liste;
      if (this.#hochlader.laeuft !== this.#zaehlt) {
        this.#zaehlt = this.#hochlader.laeuft;
        hochladenZaehlen(this.#zaehlt ? 1 : -1);
      }
    });
    if (typeof window !== "undefined") addEventListener("online", () => this.#hochlader.verbindungDa());
  }

  async starte(): Promise<void> {
    if (this.#stromAus) return;
    await this.auffrischen();
    if (!this.grund) this.#stromAus = annahmeEreignisse((liste) => this.#uebernimm(liste));
  }

  halte(): void {
    this.#stromAus?.();
    this.#stromAus = null;
  }

  async auffrischen(): Promise<void> {
    try {
      this.#uebernimm(await ladeAnnahmen());
      this.grund = "";
    } catch (e) {
      this.grund = e instanceof Error ? e.message : String(e);
    }
    this.geladen = true;
  }

  #uebernimm(liste: AnnahmeListe): void {
    const vorher = new Map(this.eintraege.map((e) => [e.id, e.stand]));
    const neuImRegal = liste.eintraege.some((e) => IM_REGAL.includes(e.stand) && vorher.has(e.id) && !IM_REGAL.includes(vorher.get(e.id)!));
    this.eintraege = liste.eintraege;
    this.zaehler = liste.zaehler ?? LEER;
    if (!neuImRegal) return;
    clearTimeout(this.#uhr);
    this.#uhr = setTimeout(() => bestand.geaendert(), AUFFRISCHEN_MS);
  }

  nimmAn(dateien: Iterable<File>, anreichern: boolean): void {
    void this.starte();
    this.#hochlader.fuegeHinzu(dateien, anreichern);
  }

  anhalten(schluessel: string): void {
    this.#hochlader.anhalten(schluessel);
  }

  weiter(schluessel: string): void {
    this.#hochlader.weiter(schluessel);
  }

  async erneut(id: number): Promise<void> {
    await annahmeErneut(id);
    await this.auffrischen();
  }

  async entferne(zeile: Annahmezeile): Promise<void> {
    if (zeile.hochladung) this.#hochlader.entferne(zeile.hochladung);
    if (zeile.id !== null) await entferneAnnahme(zeile.id);
    await this.auffrischen();
  }

  async blendeAus(): Promise<void> {
    await blendeAnnahmenAus();
    await this.auffrischen();
  }
}

export const annahme = new Annahme();
