// Ein Tab im Fenster Ausführen (BF-29): die Kopie einer Stelle, ihre Debug-Sitzung und der gezeigte Schritt. Die Logik des
// Debuggers kommt aus dem Appkern (DebugSitzung und Steuerung), gezeichnet wird nach dem Entwurf in BücherFreunde. Kopie,
// Sprache, Fassung und Haltepunkte gehören dem Zustand (lib/stand/ausfuehren.svelte.ts) und sind dort gemerkt.
import { untrack } from "svelte";
import { aufrufstapel, DebugSitzung, istEintritt, istHalt, springe, start, type Rahmen, type Wert, type Ziel } from "appkern-oberflaeche/code";
import { laufIn, type Codesprache, type Lauf } from "../api/ausfuehren";
import { ausfuehren, type Kopie } from "../stand/ausfuehren.svelte";

export type Reiter = "debugger" | "ausgabe";

const ARTEN: Record<Wert["art"], string> = {
  zahl: "Zahl", text: "Text", wahrheit: "Wahrheitswert", nichts: "nichts", liste: "Liste", tupel: "Tupel", menge: "Menge",
  woerterbuch: "Wörterbuch", funktion: "Funktion", klasse: "Klasse", objekt: "Objekt", sonst: "",
};

/** Art eines Werts, wie die Aufzeichnung sie nennt, bei Sammlungen mit ihrer Größe */
export function artVon(w: Wert): string {
  const n = w.elemente?.length ?? w.paare?.length;
  return n === undefined ? ARTEN[w.art] : `${ARTEN[w.art]} (${n}${w.gekuerzt ? "+" : ""})`;
}

export interface Variable {
  name: string;
  art: string;
  wert: string;
  /** In diesem Schritt neu oder geändert */
  neu: boolean;
}

export class Arbeit {
  readonly sitzung = new DebugSitzung();
  /** Gezeigter Schritt der Aufzeichnung */
  i = $state(0);
  reiter = $state<Reiter>("ausgabe");
  /** Fassung, in der der gezeigte Lauf lief */
  laufFassung = $state("");

  #ab: () => void;

  constructor(readonly k: string) {
    // Ein neuer Lauf beginnt am ersten Haltepunkt; spätere Änderungen an den Haltepunkten springen nicht
    this.#ab = $effect.root(() => {
      $effect(() => {
        void this.sitzung.nummer;
        untrack(() => (this.i = start(this.schritte, this.halte)));
      });
    });
  }

  get kopie(): Kopie | null {
    return ausfuehren.kopie(this.k);
  }
  get code(): string {
    return this.kopie?.code ?? "";
  }
  set code(neu: string) {
    ausfuehren.aendere(this.k, { code: neu });
  }
  get haltepunkte(): number[] {
    return this.kopie?.haltepunkte ?? [];
  }
  set haltepunkte(neu: number[]) {
    const alt = this.haltepunkte;
    if (neu.length !== alt.length || neu.some((z, n) => z !== alt[n])) ausfuehren.aendere(this.k, { haltepunkte: neu });
  }
  get sprache(): Codesprache {
    return this.kopie?.sprache ?? "python";
  }
  get geaendert(): boolean {
    return !!this.kopie && this.kopie.code !== this.kopie.listing.code;
  }

  get lauf(): Lauf | null {
    return this.sitzung.lauf as Lauf | null;
  }
  get schritte() {
    return this.sitzung.lauf?.schritte ?? [];
  }
  get halte(): Set<number> {
    return new Set(this.haltepunkte);
  }
  get aktuell() {
    return this.schritte[this.i] ?? null;
  }
  get veraltet(): boolean {
    return this.sitzung.veraltet(this.code);
  }
  /** Zeile, die der Editor markiert: im Debugger der gezeigte Schritt, in der Ausgabe die Zeile des Fehlers */
  get markiert(): number | null {
    if (this.veraltet) return null;
    if (this.reiter === "debugger") return this.aktuell?.zeile ?? null;
    return this.lauf?.fehler && this.lauf.fehlerzeile ? this.lauf.fehlerzeile : null;
  }
  /** Rahmen des gezeigten Schritts: Werte beim Überfahren eines Namens im Editor */
  get rahmen(): readonly Rahmen[] | null {
    return this.reiter === "debugger" && !this.veraltet ? (this.aktuell?.rahmen ?? null) : null;
  }
  get stapel() {
    return this.aktuell ? aufrufstapel(this.schritte, this.i, false) : [];
  }
  get eintritt(): boolean {
    return istEintritt(this.schritte, this.i);
  }
  /** Schritte, an denen ein Haltepunkt hält */
  get treffer(): number[] {
    const halte = this.halte;
    return this.schritte.flatMap((_, k) => (istHalt(this.schritte, k, halte) ? [k] : []));
  }
  get ausgabeBisher(): string {
    return this.schritte.slice(0, this.i + 1).map((s) => s.ausgabe).join("");
  }

  /** Variablen des innersten Rahmens; geändert heißt: anders als im Schritt davor im selben Rahmen */
  get variablen(): Variable[] {
    const s = this.aktuell;
    if (!s) return [];
    const innen = s.rahmen.at(-1);
    const vorher = this.schritte[this.i - 1];
    const alt = vorher && vorher.rahmen.length === s.rahmen.length ? vorher.rahmen.at(-1)?.variablen : undefined;
    return Object.entries(innen?.variablen ?? {}).map(([name, w]) => ({ name, art: artVon(w), wert: w.darstellung, neu: !!alt && alt[name]?.darstellung !== w.darstellung }));
  }

  /** Wohin ein Knopf springen würde; derselbe Schritt heißt: der Knopf hat nichts zu tun */
  ziel(z: Ziel): number {
    return this.schritte.length ? springe(z, this.schritte, this.i, this.halte) : this.i;
  }
  gehe(z: Ziel): void {
    this.i = this.ziel(z);
  }
  gehezu(i: number): void {
    this.i = Math.min(this.schritte.length - 1, Math.max(0, i));
  }

  /** Lauf in der Sandbox; im Debugger aufgezeichnet, in der Ausgabe nur das Ergebnis */
  starte(reiter: Reiter, fassung: string): void {
    if (this.sitzung.laeuft) return;
    this.reiter = reiter;
    this.laufFassung = fassung;
    void this.sitzung.starten(this.code, laufIn(this.sprache, fassung));
  }

  zerstoere(): void {
    this.sitzung.beenden();
    this.#ab();
  }
}
