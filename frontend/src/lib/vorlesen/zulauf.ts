// Der Zulauf einer Vorlesefolge: holt Text und Ton voraus, Stück für Stück in eigenen kurzen Anfragen, so reißt kein langer
// Strom an einer Grenze dazwischen. Liest über das Ende einer Einheit hinaus, damit keine Lücke zu hören ist.
import { saetzeMitLage, stuecke } from "./saetze";
import type { Lesequelle, Satzort, Sprecher, Stelle, Strecke, Tonsatz } from "./typen";

export interface Posten {
  ort: Satzort;
  satz: Tonsatz;
}

const STUECK_ZEICHEN = 700;
const VORRAT_S = 45;
const VERSUCHE = 2;
const STILL_MS = 90_000;

export class Zulauf {
  #bereit: Posten[] = [];
  #abbruch = new AbortController();
  #platz: (() => void) | null = null;
  fertig = false;
  fehler: Error | null = null;
  /** Bis hierhin ist alles geholt */
  bis: Stelle;

  constructor(private quelle: Lesequelle, strecke: Strecke, private sprecher: Sprecher, private stimme: string, private gemeldet: () => void, private pause = (ms: number) => new Promise((r) => setTimeout(r, ms))) {
    this.bis = strecke.von;
    void this.#hole(strecke)
      .then(() => (this.fertig = true))
      .catch((e: unknown) => (this.fehler = e instanceof Error ? e : new Error(String(e))))
      .finally(() => !this.#abbruch.signal.aborted && gemeldet());
  }

  stoppe(): void {
    this.#abbruch.abort();
    this.#platz?.();
  }

  get leer(): boolean {
    return this.#bereit.length === 0;
  }
  /** Sekunden, die bereitliegen */
  get sekunden(): number {
    return this.#bereit.reduce((s, p) => s + p.satz.dauer, 0);
  }

  nimm(): Posten | undefined {
    const p = this.#bereit.shift();
    if (this.sekunden < VORRAT_S) this.#platz?.();
    return p;
  }
  lege(...posten: Posten[]): void {
    this.#bereit.unshift(...posten);
  }

  async #hole({ von, bis }: Strecke): Promise<void> {
    let zeichen = von.zeichen;
    for (let einheit = von.einheit; einheit < this.quelle.anzahl && !this.#abbruch.signal.aborted; einheit++, zeichen = 0) {
      if (bis && (einheit > bis.einheit || (einheit === bis.einheit && bis.zeichen <= zeichen))) return;
      const text = await this.quelle.text(einheit);
      // Mitten in einem Satz beginnt es an seinem Anfang
      if (einheit === von.einheit && zeichen > 0) zeichen = saetzeMitLage(text).find((s) => s.bis > zeichen && s.von <= zeichen)?.von ?? zeichen;
      const ende = bis && einheit === bis.einheit ? bis.zeichen : text.length;
      for (const s of stuecke(text.slice(zeichen, ende), STUECK_ZEICHEN)) {
        while (this.sekunden >= VORRAT_S && !this.#abbruch.signal.aborted) await new Promise<void>((r) => (this.#platz = r));
        if (this.#abbruch.signal.aborted) return;
        await this.#sprich(s.text, { einheit, zeichen: zeichen + s.von });
      }
      if (bis && einheit === bis.einheit) return;
    }
  }

  // Reißt es mitten im Stück, geht es beim nächsten Versuch nach dem letzten guten Satz weiter
  async #sprich(text: string, ab: Stelle): Promise<void> {
    let geholt = 0;
    for (let versuch = 0; ; versuch++) {
      const wache = this.#wache();
      try {
        const rest = text.slice(geholt);
        const basis = geholt;
        for await (const satz of this.sprecher.saetze(rest, this.stimme, wache.signal)) {
          wache.lebt();
          if (this.#abbruch.signal.aborted) return;
          geholt = basis + satz.bis;
          versuch = 0;
          this.bis = { einheit: ab.einheit, zeichen: ab.zeichen + geholt };
          this.#bereit.push({ ort: { einheit: ab.einheit, von: ab.zeichen + basis + satz.von, bis: ab.zeichen + geholt }, satz });
          this.gemeldet();
        }
        this.bis = { einheit: ab.einheit, zeichen: ab.zeichen + text.length };
        return;
      } catch (e) {
        if (this.#abbruch.signal.aborted || !text.slice(geholt).trim()) return;
        if (versuch >= VERSUCHE) throw wache.eingeschlafen() ? new Error("Der Sprechdienst antwortet nicht") : e;
      } finally {
        wache.ende();
      }
      await this.pause(1000 * 3 ** versuch);
      if (this.#abbruch.signal.aborted) return;
    }
  }

  // Ein Strom, der verstummt, gilt als gerissen
  #wache() {
    const eigen = new AbortController();
    const weiter = () => eigen.abort();
    this.#abbruch.signal.addEventListener("abort", weiter);
    let schlief = false;
    let uhr: ReturnType<typeof setTimeout>;
    const lebt = () => {
      clearTimeout(uhr);
      uhr = setTimeout(() => {
        schlief = true;
        eigen.abort();
      }, STILL_MS);
    };
    lebt();
    const ende = () => {
      clearTimeout(uhr);
      this.#abbruch.signal.removeEventListener("abort", weiter);
      eigen.abort();
    };
    return { signal: eigen.signal, lebt, ende, eingeschlafen: () => schlief };
  }
}
