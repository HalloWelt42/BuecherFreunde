// Gemeinfreie Bücher: Suche und Auswahl über alle Seiten. Geholt wird über die Annahme; ihr Stand steht dort
// (annahme.gemeinfrei), als Auftrag im Kopf zeigt ihn lib/stand/auftraege.svelte.ts.
import { sucheGemeinfreie, uebernimmGemeinfreie, type Fundbuch } from "../api/gutenberg";
import { annahme } from "./annahme.svelte";
import { auftraege } from "./auftraege.svelte";

class Gutenberg {
  wort = $state("");
  sprache = $state("de");
  treffer = $state<Fundbuch[]>([]);
  gesamt = $state(0);
  seite = $state(1);
  weitere = $state(false);
  laedt = $state(false);
  fehler = $state("");
  gesucht = $state(false);
  #gewaehlt = $state<ReadonlyMap<number, Fundbuch>>(new Map());

  zahl = $derived(this.#gewaehlt.size);
  alleGewaehlt = $derived(this.treffer.length > 0 && this.treffer.every((b) => this.#gewaehlt.has(b.gutenberg_id)));
  laeuft = $derived(annahme.gemeinfrei.laeuft);

  #lauf = 0;

  hat(id: number): boolean {
    return this.#gewaehlt.has(id);
  }

  /** Neue Frage, Seite 1; die Auswahl gehört zur alten Frage und fällt weg */
  async suche(): Promise<void> {
    this.#gewaehlt = new Map();
    await this.#hole(1);
  }

  async blaettere(schritt: number): Promise<void> {
    await this.#hole(Math.max(1, this.seite + schritt));
  }

  async #hole(seite: number): Promise<void> {
    const lauf = ++this.#lauf;
    this.laedt = true;
    this.fehler = "";
    try {
      const antwort = await sucheGemeinfreie(this.wort, this.sprache, seite);
      if (lauf !== this.#lauf) return;
      this.treffer = antwort.buecher;
      this.gesamt = antwort.gesamt;
      this.seite = seite;
      this.weitere = !!antwort.naechste;
    } catch (e) {
      if (lauf !== this.#lauf) return;
      this.fehler = e instanceof Error ? e.message : String(e);
      this.treffer = [];
    } finally {
      if (lauf === this.#lauf) {
        this.laedt = false;
        this.gesucht = true;
      }
    }
  }

  schalte(buch: Fundbuch): void {
    const neu = new Map(this.#gewaehlt);
    if (!neu.delete(buch.gutenberg_id)) neu.set(buch.gutenberg_id, buch);
    this.#gewaehlt = neu;
  }

  /** Alle dieser Seite wählen oder abwählen; andere Seiten bleiben, wie sie sind */
  schalteSeite(): void {
    const neu = new Map(this.#gewaehlt);
    const weg = this.alleGewaehlt;
    for (const b of this.treffer) {
      if (weg) neu.delete(b.gutenberg_id);
      else neu.set(b.gutenberg_id, b);
    }
    this.#gewaehlt = neu;
  }

  leere(): void {
    this.#gewaehlt = new Map();
  }

  async uebernimm(): Promise<void> {
    const buecher = [...this.#gewaehlt.values()].map(({ gutenberg_id, titel, autor, download_url, download_format, cover_url }) => ({ gutenberg_id, titel, autor, download_url, download_format, cover_url }));
    await uebernimmGemeinfreie(buecher);
    this.#gewaehlt = new Map();
    await annahme.auffrischen();
  }

  /** Geholtes, schon Vorhandenes und Gescheitertes aus der Liste nehmen; die Bücher bleiben */
  async zuruecksetzen(): Promise<void> {
    await auftraege.gemeinfreiAufraeumen();
  }
}

export const gutenberg = new Gutenberg();
