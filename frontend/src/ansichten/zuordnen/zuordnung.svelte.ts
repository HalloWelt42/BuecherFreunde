// Zustand der Zuordnung (BF-67): links was drin ist, rechts der Bestand, dazu Haken und die drei Wege Dazu, Heraus, Ordnen.
// Jede Änderung steht sofort da und kommt danach vom Server (Bandnummern vergibt er); geht sie schief, gilt wieder der Server.
import type { Parameter } from "../../lib/api/client";
import { anzahl } from "../../lib/format";
import { bestand } from "../../lib/stand/bestand.svelte";
import { melde } from "../../lib/stand/meldungen.svelte";
import { frage } from "../../lib/stand/rueckfrage.svelte";
import type { Buch } from "../../lib/typen";
import { autoren } from "../sammlung/angaben";
import { Buchseiten } from "./buchseiten.svelte";
import { gleich, neueNummern, ordne, vergibtNeu } from "./reihenfolge";
import type { Zuordnungsziel } from "./ziel";

export type Spalte = "drin" | "uebrig";

const TITEL_HOECHSTENS = 5;

/** "A, B, C und 4 weitere" für Rückfragen */
export function titelliste(buecher: Pick<Buch, "title">[], hoechstens = TITEL_HOECHSTENS): string {
  const kopf = buecher.slice(0, hoechstens).map((b) => b.title).join(", ");
  return buecher.length > hoechstens ? `${kopf} und ${buecher.length - hoechstens} weitere` : kopf;
}

export class Zuordnung {
  readonly ziel: Zuordnungsziel;
  readonly drin: Buchseiten;
  readonly uebrig = new Buchseiten();
  haken = $state<Record<Spalte, ReadonlySet<number>>>({ drin: new Set(), uebrig: new Set() });
  wort = $state("");
  gleicherAutor = $state(false);
  ohneSammlung = $state(false);
  laeuft = $state(false);
  /** Der häufigste Autor der linken Spalte, für den Schalter "Gleicher Autor" */
  readonly autor: string;
  /** Was rechts steht: der Bestand ohne das, was schon drin ist */
  readonly rechts: Buch[];
  /** Filter des Bestands; ändert er sich, lädt die rechte Spalte neu */
  readonly uebrigFilter: Parameter;

  constructor(ziel: Zuordnungsziel) {
    this.ziel = ziel;
    this.drin = new Buchseiten(!!ziel.ordne);
    this.gleicherAutor = ziel.gleicherAutorVorgabe;
    this.ohneSammlung = ziel.ohneSammlungVorgabe;
    this.autor = $derived(autoren(this.drin.liste)[0] ?? "");
    this.rechts = $derived(this.uebrig.liste.filter((b) => !ziel.hat(b)));
    this.uebrigFilter = $derived({
      ...ziel.uebrig(this.ohneSammlung),
      suche: this.wort.trim() || undefined,
      autor: this.gleicherAutor && this.autor ? this.autor : undefined,
    });
  }

  liste(spalte: Spalte): Buch[] {
    return spalte === "drin" ? this.drin.liste : this.rechts;
  }

  hat(spalte: Spalte, id: number): boolean {
    return this.haken[spalte].has(id);
  }

  hakeAn(spalte: Spalte, id: number, an: boolean): void {
    const neu = new Set(this.haken[spalte]);
    if (an) neu.add(id);
    else neu.delete(id);
    this.haken = { ...this.haken, [spalte]: neu };
  }

  /** Die angehakten einer Spalte in der Reihenfolge, in der sie dort stehen */
  angehakt(spalte: Spalte): number[] {
    return this.liste(spalte).filter((b) => this.haken[spalte].has(b.id)).map((b) => b.id);
  }

  /** Wer zieht: ein angehaktes Buch nimmt alle angehakten seiner Spalte mit, sonst nur sich */
  gezogene(spalte: Spalte, id: number): number[] {
    return this.hat(spalte, id) ? this.angehakt(spalte) : [id];
  }

  /** Nimmt die Spalte `nach` an, was aus `von` gezogen wird? Umstellen gibt es nur, wo es eine Reihenfolge gibt */
  nimmt(von: Spalte, nach: Spalte): boolean {
    return nach === "drin" ? von === "uebrig" || !!this.ziel.ordne : von === "drin";
  }

  /** Ablegen nach dem Ziehen: hinein (an die Stelle vor `vor`), umstellen oder heraus */
  lege(von: Spalte, nach: Spalte, ids: number[], vor: number | null): Promise<void> {
    if (!this.nimmt(von, nach)) return Promise.resolve();
    if (nach === "uebrig") return this.heraus(ids);
    return von === "uebrig" ? this.dazu(ids, vor) : this.stelleUm(ids, vor);
  }

  #leere(spalte: Spalte): void {
    this.haken = { ...this.haken, [spalte]: new Set() };
  }

  /** Bücher aus dem Bestand hinein, ans Ende oder vor `vor` (nur mit Reihenfolge) */
  async dazu(ids: number[], vor: number | null = null): Promise<void> {
    const weg = new Set(ids);
    const neu = this.rechts.filter((b) => weg.has(b.id));
    if (!neu.length || this.laeuft) return;
    const folge = this.ziel.ordne && vor !== null ? ordne(this.drin.liste.map((b) => b.id), neu.map((b) => b.id), vor) : null;
    const folgen = this.ziel.folgenDazu(neu);
    if (folgen.length && !(await frage({ titel: `${anzahl(neu.length, "Buch", "Bücher")} hierher?`, text: titelliste(neu), folgen, ja: "Hierher", symbol: "arrow-left" }))) return;
    if (folge && !(await this.#darfDurchzaehlen(folge))) return;
    const alle = new Map([...this.drin.liste, ...neu].map((b) => [b.id, b]));
    this.drin.ordne(folge ? folge.flatMap((id) => alle.get(id) ?? []) : [...this.drin.liste, ...neu]);
    this.uebrig.nimm(ids);
    this.#leere("uebrig");
    await this.#schreibe(async () => {
      await this.ziel.dazu(neu.map((b) => b.id));
      if (folge) await this.ziel.ordne?.(folge);
    }, `${anzahl(neu.length, "Buch", "Bücher")} zugeordnet`);
  }

  /** Bücher heraus, zurück in den Bestand; erst nach der Rückfrage mit ihren Titeln */
  async heraus(ids: number[]): Promise<void> {
    const weg = new Set(ids);
    const raus = this.drin.liste.filter((b) => weg.has(b.id));
    if (!raus.length || this.laeuft) return;
    const ja = await frage({ titel: `${anzahl(raus.length, "Buch", "Bücher")} herausnehmen?`, text: titelliste(raus), folgen: this.ziel.folgenHeraus(raus.length), ja: "Herausnehmen", symbol: "arrow-right" });
    if (!ja) return;
    this.drin.nimm(ids);
    this.uebrig.stelle(raus.map((b) => this.ziel.ohne(b)));
    this.#leere("drin");
    await this.#schreibe(() => this.ziel.heraus(raus.map((b) => b.id)), `${anzahl(raus.length, "Buch", "Bücher")} herausgenommen`);
  }

  /** Links umstellen (nur mit Reihenfolge): die Bandnummern folgen */
  async stelleUm(ids: number[], vor: number | null): Promise<void> {
    const ordnen = this.ziel.ordne;
    if (!ordnen || this.laeuft) return;
    const vorher = this.drin.liste.map((b) => b.id);
    const folge = ordne(vorher, ids, vor);
    if (gleich(vorher, folge) || !(await this.#darfDurchzaehlen(folge))) return;
    const nach = new Map(this.drin.liste.map((b) => [b.id, b]));
    this.drin.ordne(folge.flatMap((id, n) => (nach.has(id) ? [{ ...nach.get(id)!, band_nummer: String(n + 1) }] : [])));
    await this.#schreibe(() => ordnen(folge), "Reihenfolge gespeichert");
  }

  /** Tragen die Bände schon 1 bis n, ändert das Ziehen nur die Folge; sonst gehen Nummern verloren, und das wird gefragt */
  async #darfDurchzaehlen(folge: number[]): Promise<boolean> {
    if (!vergibtNeu(this.drin.liste)) return true;
    const aenderungen = neueNummern(this.drin.liste, folge);
    if (!aenderungen.length) return true;
    const zeilen = aenderungen.slice(0, TITEL_HOECHSTENS).map((a) => `${a.titel}: ${a.alt ? `Band ${a.alt}` : "ohne Nummer"} wird Band ${a.neu}`);
    if (aenderungen.length > TITEL_HOECHSTENS) zeilen.push(`und ${aenderungen.length - TITEL_HOECHSTENS} weitere`);
    return frage({ titel: "Bände neu durchzählen?", text: `Die Reihenfolge vergibt die Bandnummern 1 bis ${folge.length}. Dabei ändern sich:`, folgen: zeilen, ja: "Neu durchzählen", symbol: "arrow-down-1-9" });
  }

  async #schreibe(tun: () => Promise<unknown>, gut: string): Promise<void> {
    this.laeuft = true;
    try {
      await tun();
      melde.gut(gut);
    } catch (e) {
      melde.schlecht(e, "Nicht geändert");
      await this.uebrig.auffrischen();
    } finally {
      await this.drin.auffrischen();
      this.laeuft = false;
      bestand.geaendert();
    }
  }
}
