// Fassungen eines Buchs auf der Buchseite (BF-71): Original und Übersetzungen als Flaggenlabels, welche gewählt ist (sie
// öffnet "Lesen") und wo man in ihr liest. Solange eine Übersetzung läuft, kommt ihr Stand regelmäßig nach.
import { holeFassungen, holeFassungslesestand, waehleFassung } from "../../lib/api/uebersetzung";
import { leseAdresse } from "../../lib/lesestand";
import { melde } from "../../lib/stand/meldungen.svelte";
import { UEBERSETZBAR } from "../../lib/uebersetzung/texte";
import type { Fassungseintrag, Fassungslesestand, Uebersetzung, Zielsprache } from "../../lib/uebersetzung/typen";
import { anschluesse } from "../../lib/stand/anschluesse.svelte";
import type { BuchEinzeln } from "../../lib/typen";

const TAKT_MS = 4000;

/** Leser einer Fassung: das Original unter /book/12/read, eine Übersetzung unter /book/12/read/de */
export function fassungsAdresse(buch: number, sprache: string | null, stelle: Record<string, string | number | undefined> = {}): string {
  const original = leseAdresse(buch, stelle);
  return sprache ? original.replace(/\/read(\?|$)/, `/read/${sprache}$1`) : original;
}

/** Ein englisches EPUB ohne deutsche Fassung, mit KI: das Label "Ins Deutsche übersetzen" */
export function uebersetzbar(buch: Pick<BuchEinzeln, "language" | "file_format">, liste: Fassungseintrag[]): boolean {
  const englisch = (buch.language ?? "").trim().toLowerCase().startsWith("en");
  return englisch && UEBERSETZBAR.includes(buch.file_format) && anschluesse.jetzt.ki && !liste.some((f) => !f.original && f.sprache === "de");
}

export class Buchfassungen {
  liste = $state<Fassungseintrag[]>([]);
  geladen = $state(false);
  /** Lesestand der gewählten Übersetzung; beim Original steht er am Buch */
  lesestand = $state<Fassungslesestand | null>(null);
  waehlt = $state(false);
  gewaehlt = $derived(this.liste.find((f) => f.gewaehlt) ?? this.liste[0] ?? null);
  /** Die gewählte Übersetzung; null, wenn das Original gewählt ist */
  uebersetzung = $derived(this.gewaehlt && !this.gewaehlt.original ? (this.gewaehlt as Uebersetzung) : null);
  deutsch = $derived((this.liste.find((f) => !f.original && f.sprache === "de") as Uebersetzung | undefined) ?? null);
  #uhr: ReturnType<typeof setTimeout> | undefined;
  #an = true;

  constructor(private buch: number) {}

  async laden(): Promise<void> {
    try {
      this.#uebernimm(await holeFassungen(this.buch));
    } catch {
      // ohne Antwort bleibt, was bekannt ist; ohne Liste gibt es keine Labels
    }
    this.geladen = true;
    this.#weiter();
  }

  /** Nicht mehr nachfragen (die Buchseite ist zu) */
  beende(): void {
    this.#an = false;
    clearTimeout(this.#uhr);
  }

  #weiter(): void {
    clearTimeout(this.#uhr);
    if (this.#an && this.liste.some((f) => f.stand === "laeuft")) this.#uhr = setTimeout(() => void this.laden(), TAKT_MS);
  }

  #uebernimm(liste: Fassungseintrag[]): void {
    const vorher = this.uebersetzung?.id ?? null;
    this.liste = liste;
    const jetzt = this.uebersetzung?.id ?? null;
    if (jetzt === null) this.lesestand = null;
    else if (jetzt !== vorher || this.lesestand === null) void this.#ladeLesestand(jetzt);
  }

  async #ladeLesestand(fassung: number): Promise<void> {
    try {
      const s = await holeFassungslesestand(fassung);
      if (this.uebersetzung?.id === fassung) this.lesestand = s;
    } catch {
      // ohne Antwort beginnt "Lesen" am Anfang
    }
  }

  async waehle(f: Fassungseintrag): Promise<void> {
    if (f.gewaehlt || this.waehlt) return;
    this.waehlt = true;
    try {
      this.#uebernimm(await waehleFassung(this.buch, f.original ? null : (f.sprache as Zielsprache)));
    } catch (e) {
      melde.schlecht(e, "Nicht gewählt");
    } finally {
      this.waehlt = false;
    }
  }
}
