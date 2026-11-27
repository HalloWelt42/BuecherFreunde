// Seiten in der Texterkennung (BF-109): die Textansicht bittet für die gelesene Seite um Vorrang und fragt sanft nach, im
// wachsenden Abstand, bis keine gezeigte Seite mehr wartet; erkannte Seiten holt sie neu
import { texterkennungVorrang, type Vorrangstand } from "../../api/books";

/** Abstände der Nachfragen; nach jeder erkannten Seite geht es wieder vorn los, öfter als im kürzesten wird nie gefragt */
export const ABSTAENDE_MS = [3000, 5000, 8000, 13000, 20000] as const;

export interface Wartelage {
  /** die gezeigten Seiten, die noch auf ihre Erkennung warten */
  wartend: number[];
  /** die gelesene Seite */
  gelesen: number;
}

type Bitte = (buch: number, seite: number) => Promise<Vorrangstand>;

export class Erkennungswarten {
  #uhr: ReturnType<typeof setTimeout> | null = null;
  #schritt = 0;
  #gefragt = 0;
  #zuletzt = Number.NEGATIVE_INFINITY;
  #fragt = false;
  #aus = false;

  /** erkannt: diese Seiten sind fertig (oder warten nicht mehr), neu holen */
  constructor(
    private buch: number,
    private lage: () => Wartelage,
    private erkannt: (nrn: number[]) => Promise<unknown>,
    private bitte: Bitte = texterkennungVorrang,
  ) {}

  /** Nach jeder Änderung der gezeigten oder der gelesenen Seite: fragt bald, wenn eine Seite wartet; die gelesene zuerst */
  pruefe(): void {
    if (this.#aus || this.#fragt) return;
    const ab = this.#ab();
    if (ab === null) return this.#still();
    if (this.#uhr !== null && ab === this.#gefragt) return;
    this.#gefragt = ab;
    this.#schritt = 0;
    this.#plane(Math.max(0, ABSTAENDE_MS[0] - (Date.now() - this.#zuletzt)));
  }

  halte(): void {
    this.#aus = true;
    this.#still();
  }

  /** Die gelesene Seite, wenn sie wartet, sonst die nächste wartende danach, sonst die letzte davor */
  #ab(): number | null {
    const { wartend, gelesen } = this.lage();
    if (!wartend.length) return null;
    return wartend.find((n) => n >= gelesen) ?? wartend[wartend.length - 1];
  }

  #plane(ms: number): void {
    this.#still();
    this.#uhr = setTimeout(() => void this.#frage(), ms);
  }

  #still(): void {
    if (this.#uhr !== null) clearTimeout(this.#uhr);
    this.#uhr = null;
  }

  async #frage(): Promise<void> {
    this.#uhr = null;
    const ab = this.#ab();
    if (ab === null || this.#aus) return;
    this.#fragt = true;
    this.#gefragt = ab;
    this.#zuletzt = Date.now();
    let fertig: number[] = [];
    try {
      const antwort = await this.bitte(this.buch, ab);
      const offen = new Set(antwort.wartet);
      fertig = this.lage().wartend.filter((n) => !antwort.bereit || (n >= antwort.von && n <= antwort.bis && !offen.has(n)));
      if (fertig.length) await this.erkannt(fertig);
    } catch {
      // gestört: beim nächsten Mal wieder
    } finally {
      this.#fragt = false;
    }
    if (this.#aus) return;
    if (fertig.length) this.#schritt = 0;
    const abstand = ABSTAENDE_MS[Math.min(this.#schritt, ABSTAENDE_MS.length - 1)];
    this.#schritt += 1;
    if (this.#ab() !== null) this.#plane(abstand);
  }
}
