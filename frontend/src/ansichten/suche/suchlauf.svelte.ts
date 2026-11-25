// Treffer nach Wörtern und nach Bedeutung; "Beides" mischt sie im Wechsel
import { suche as sucheWoerter } from "../../lib/api/search";
import { sucheBedeutung } from "../../lib/api/orte";
import type { Suchart } from "../../lib/stand/suche.svelte";
import type { Bedeutungstreffer, Treffer } from "../../lib/typen";
import { nurText } from "./suchsprache";

const JE_SEITE = 20;

export type Fund = { art: "wort"; schluessel: string; wort: Treffer } | { art: "sinn"; schluessel: string; sinn: Bedeutungstreffer };

export class Suchlauf {
  woerter = $state<Treffer[]>([]);
  gesamt = $state(0);
  filter = $state<Record<string, string>>({});
  sinn = $state<Bedeutungstreffer[]>([]);
  /** Warum die Suche nach Bedeutung nichts liefert; leer, wenn sie läuft */
  grund = $state("");
  laedt = $state(false);
  fehler = $state("");
  fertig = $state(false);
  #lauf = 0;

  funde = $derived.by<Fund[]>(() => {
    const aus: Fund[] = [];
    const laenge = Math.max(this.woerter.length, this.sinn.length);
    for (let n = 0; n < laenge; n++) {
      const s = this.sinn[n];
      const w = this.woerter[n];
      if (s) aus.push({ art: "sinn", schluessel: `s${n}-${s.buch_id}-${s.seite}`, sinn: s });
      if (w) aus.push({ art: "wort", schluessel: `w${w.book_id}`, wort: w });
    }
    return aus;
  });

  /** Alle bekannten Stellen: Bücher mit den Wörtern und Stellen nach Bedeutung */
  zahl = $derived(this.gesamt + this.sinn.length);

  async starte(frage: string, art: Suchart): Promise<void> {
    const lauf = ++this.#lauf;
    Object.assign(this, { woerter: [], gesamt: 0, filter: {}, sinn: [], grund: "", fehler: "", fertig: false, laedt: true });
    await Promise.all([art !== "bedeutung" && this.#woerter(frage, 0, lauf), art !== "woerter" && this.#bedeutung(frage, lauf)]);
    if (lauf === this.#lauf) Object.assign(this, { laedt: false, fertig: true });
  }

  async mehr(frage: string): Promise<void> {
    if (this.laedt || this.woerter.length >= this.gesamt) return;
    this.laedt = true;
    await this.#woerter(frage, this.woerter.length, this.#lauf);
    this.laedt = false;
  }

  async #woerter(frage: string, ab: number, lauf: number): Promise<void> {
    try {
      const a = await sucheWoerter(frage, { limit: JE_SEITE, offset: ab });
      if (lauf !== this.#lauf) return;
      const bekannt = new Set(this.woerter.map((t) => t.book_id));
      this.woerter = [...this.woerter, ...a.treffer.filter((t) => !bekannt.has(t.book_id))];
      this.gesamt = a.treffer.length || !ab ? a.gesamt : this.woerter.length;
      this.filter = a.aktive_filter ?? {};
    } catch (e) {
      if (lauf === this.#lauf) this.fehler = e instanceof Error ? e.message : String(e);
    }
  }

  async #bedeutung(frage: string, lauf: number): Promise<void> {
    const text = nurText(frage);
    if (!text) return;
    try {
      const a = await sucheBedeutung(text, JE_SEITE);
      if (lauf !== this.#lauf) return;
      this.sinn = a.treffer;
      this.grund = a.verfuegbar ? "" : (a.grund ?? "Die Suche nach Bedeutung antwortet gerade nicht");
    } catch (e) {
      if (lauf === this.#lauf) this.grund = e instanceof Error ? e.message : String(e);
    }
  }
}
