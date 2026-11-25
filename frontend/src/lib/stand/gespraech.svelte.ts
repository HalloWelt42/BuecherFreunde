// Gespräch mit dem Assistenten im kleinen Fenster. Der Chat liegt in der Anwendung, dort geht er auf Wunsch weiter.
import { antwortStrom, brichAntwortAb, stelleFrage, type Antwortbeleg, type Antwortzeile, type Stelle } from "../api/helfer";
import { zeilenAus } from "../vorlesen/zeilen";

export interface Runde {
  frage: string;
  stelle: string;
  antwort: string;
  laeuft: boolean;
  wartetAuf: string;
  fehler: string;
  belege: Antwortbeleg[];
}

export interface Bezug extends Stelle {
  /** Wie das Buch heißt, nur zum Zeigen */
  titel?: string;
}

const FERTIG = ["fertig", "fehler", "abgebrochen"];

class Gespraechsstand {
  offen = $state(false);
  bezug = $state.raw<Bezug>({});
  runden = $state<Runde[]>([]);
  adresse = $state("");
  #chat = "";
  #zug = "";
  #abbruch: AbortController | null = null;

  laeuft = $derived(this.runden.at(-1)?.laeuft ?? false);

  /** Öffnet das Fenster mit einer Stelle; gefragt wird erst, wenn der Mensch fragt. */
  oeffne(bezug: Bezug): void {
    this.offen = true;
    this.bezug = bezug;
  }

  schliesse(): void {
    this.offen = false;
  }

  neu(): void {
    this.#abbruch?.abort();
    this.runden = [];
    this.adresse = "";
    this.#chat = "";
  }

  loeseStelle(): void {
    this.bezug = { buch: this.bezug.buch, titel: this.bezug.titel };
  }

  async frage(text: string): Promise<void> {
    if (this.laeuft) return;
    const { titel: _titel, ...stelle } = this.bezug;
    this.runden.push({ frage: text, stelle: stelle.text ?? "", antwort: "", laeuft: true, wartetAuf: "", fehler: "", belege: [] });
    const runde = this.runden[this.runden.length - 1];
    const abbruch = new AbortController();
    this.#abbruch = abbruch;
    try {
      const gestellt = await stelleFrage(text, stelle, this.#chat);
      this.#chat = gestellt.chat;
      this.#zug = gestellt.zug;
      this.adresse = gestellt.adresse;
      this.loeseStelle();
      const antwort = await antwortStrom(gestellt.chat, gestellt.zug, abbruch.signal);
      if (antwort.body) for await (const z of zeilenAus<Antwortzeile>(antwort.body)) this.#uebernimm(runde, z);
    } catch (e) {
      if (!abbruch.signal.aborted) runde.fehler = e instanceof Error ? e.message : String(e);
    } finally {
      runde.laeuft = false;
    }
  }

  #uebernimm(runde: Runde, z: Antwortzeile): void {
    if (z.art === "text") {
      runde.wartetAuf = "";
      runde.antwort = z.neu ? z.text : runde.antwort.slice(0, z.ab) + z.text;
      return;
    }
    if (z.antwort) runde.antwort = z.antwort;
    runde.wartetAuf = z.wartet_auf;
    runde.belege = z.belege;
    runde.fehler = z.zustand === "fehler" ? z.fehler || "Der Assistent konnte nicht antworten" : "";
    if (FERTIG.includes(z.zustand)) runde.laeuft = false;
  }

  async halt(): Promise<void> {
    this.#abbruch?.abort();
    if (this.#zug) await brichAntwortAb(this.#zug).catch(() => undefined);
  }
}

export const gespraech = new Gespraechsstand();
