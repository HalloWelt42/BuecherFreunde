// Ansagen im Kinderbereich (BF-78, Entwurf Runde 4): die einzige Stelle, an der etwas gesprochen wird, das kein Vorlesen ist.
// Hinweise (Lesezeit, fünf Minuten vorher, Ruhezeit, Schloss, Katze benennen, leere Regale) und nach dem Druck jede Taste und
// jeder Umschlag mit ihrem Namen. Je Kind abschaltbar (Lesehilfen hinweise_sprechen und tasten_ansagen).
//
// Regeln: Eine neue Ansage beendet die laufende, es gibt keine Warteschlange. Über das Vorlesen wird nie gesprochen; während
// des Vorlesens sagen nur die Tasten an, die den Vorlesestrom selbst steuern, und wer sie bedient, lässt das Vorlesen erst
// danach weiterklingen (fertig()). Die Ansage kommt nach der Wirkung der Taste. Vor dem ersten Antippen bleibt alles still.
//
// Ton: der Satz vom Server (POST /api/vorlesen/ansage, dort zwischengespeichert), hier je Seite gemerkt; fehlt der Weg oder
// ist der Sprechdienst nicht bereit (503), spricht die Stimme des Geräts.
import { anfrage, ApiError } from "../api/client";
import { anschluesse } from "../stand/anschluesse.svelte";
import { vorlesen } from "../stand/vorlesen.svelte";
import { saetze } from "../vorlesen/saetze";
import { stilleAdresse } from "../vorlesen/ton";
import { geraetDa, geraetestimmen, Geraetesprecher } from "../vorlesen/geraet";

/** Ton vom Server; "fehlt": den Weg gibt es nicht (für immer zur Stimme des Geräts), "spaeter": gerade nicht bereit */
export type Ansageton = Blob | "fehlt" | "spaeter";

export interface Tonquelle {
  hole(text: string, abbruch: AbortSignal): Promise<Ansageton>;
  spiele(ton: Blob, abbruch: AbortSignal): Promise<void>;
  /** Mit der Stimme des Geräts */
  sprich(text: string, abbruch: AbortSignal): Promise<void>;
  /** Noch im Tippen: gibt den Ton frei */
  entsperre(): void;
}

/** Klingt gerade Vorlesen? */
export type Vorlesenklingt = () => boolean;

/** So viele Sätze merkt sich die Seite */
const VORRAT = 80;
/** So lang darf ein Satz für den Server sein */
const SATZ_HOECHSTENS = 300;
/** Länger wartet niemand auf das Ende einer Ansage */
const HOECHSTENS_MS = 4000;

export class Ansage {
  hinweise = $state(false);
  tasten = $state(false);
  #frei = false;
  #laufend: { abbruch: AbortController; fertig: Promise<void> } | null = null;
  #toene = new Map<string, Blob>();
  #ohneDienst = false;

  constructor(private quelle: Tonquelle, private klingt: Vorlesenklingt) {}

  /** Was die Eltern für dieses Kind eingestellt haben */
  stelle(hinweise: boolean, tasten: boolean): void {
    this.hinweise = hinweise;
    this.tasten = tasten;
    if (!hinweise && !tasten) this.stoppe();
  }

  /** Das erste Antippen: ab jetzt darf es klingen. Im Tippen rufen. */
  freigeben(): void {
    if (this.#frei) return;
    this.#frei = true;
    this.quelle.entsperre();
  }

  get frei(): boolean {
    return this.#frei;
  }

  /** Ein Hinweis; nie über dem Vorlesen */
  hinweis(text: string): Promise<void> {
    if (!this.hinweise || this.klingt()) return Promise.resolve();
    return this.#sage(text);
  }

  /** Nach dem Druck einer Taste; strom: sie steuert das Vorlesen selbst und darf auch während des Vorlesens kurz ansagen */
  taste(text: string, strom = false): Promise<void> {
    if (!this.tasten || (this.klingt() && !strom)) return Promise.resolve();
    return this.#sage(text);
  }

  /** Bis die laufende Ansage zu Ende ist (höchstens ein paar Sekunden) */
  fertig(): Promise<void> {
    const l = this.#laufend;
    return l ? Promise.race([l.fertig, new Promise<void>((r) => setTimeout(r, HOECHSTENS_MS))]) : Promise.resolve();
  }

  stoppe(): void {
    this.#laufend?.abbruch.abort();
    this.#laufend = null;
  }

  #sage(text: string): Promise<void> {
    const satz = text.trim();
    if (!this.#frei || !satz) return Promise.resolve();
    this.stoppe();
    const abbruch = new AbortController();
    const fertig = this.#klinge(satz, abbruch.signal).catch(() => undefined);
    const lauf = { abbruch, fertig };
    this.#laufend = lauf;
    void fertig.then(() => {
      if (this.#laufend === lauf) this.#laufend = null;
    });
    return fertig;
  }

  /** Satz für Satz: der Server nimmt je Ansage genau einen Satz mit höchstens 300 Zeichen */
  async #klinge(text: string, abbruch: AbortSignal): Promise<void> {
    for (const satz of saetze(text)) {
      if (abbruch.aborted) return;
      await this.#klingeSatz(satz.slice(0, SATZ_HOECHSTENS), abbruch);
    }
  }

  async #klingeSatz(satz: string, abbruch: AbortSignal): Promise<void> {
    const ton: Ansageton = this.#toene.get(satz) ?? (this.#ohneDienst ? "fehlt" : await this.quelle.hole(satz, abbruch).catch((): Ansageton => "spaeter"));
    if (abbruch.aborted) return;
    if (ton instanceof Blob) {
      this.#merke(satz, ton);
      return this.quelle.spiele(ton, abbruch);
    }
    if (ton === "fehlt") this.#ohneDienst = true;
    return this.quelle.sprich(satz, abbruch);
  }

  #merke(satz: string, ton: Blob): void {
    this.#toene.delete(satz);
    this.#toene.set(satz, ton);
    if (this.#toene.size > VORRAT) this.#toene.delete(this.#toene.keys().next().value!);
  }
}

/** Der Ton im Browser: ein eigenes Tonelement, der Sprechdienst über den Server, sonst die Stimmen des Geräts */
class Browserton implements Tonquelle {
  #element: HTMLAudioElement | null = null;
  #geraet = new Geraetesprecher();

  #ton(): HTMLAudioElement {
    this.#element ??= new Audio();
    return this.#element;
  }

  entsperre(): void {
    const t = this.#ton();
    t.src = stilleAdresse();
    void t.play().catch(() => undefined);
  }

  async hole(text: string, abbruch: AbortSignal): Promise<Ansageton> {
    if (!anschluesse.jetzt.vorlesen) return "fehlt";
    const stimme = vorlesen.stimme.startsWith("dienst:") ? vorlesen.stimme.slice("dienst:".length) : "";
    try {
      const antwort = await anfrage("/api/vorlesen/ansage", { method: "POST", body: JSON.stringify(stimme ? { text, stimme } : { text }), signal: abbruch });
      return await antwort.blob();
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 405)) return "fehlt";
      return "spaeter";
    }
  }

  spiele(ton: Blob, abbruch: AbortSignal): Promise<void> {
    const t = this.#ton();
    const adresse = URL.createObjectURL(ton);
    return new Promise<void>((fertig) => {
      const ende = () => {
        t.onended = t.onerror = null;
        abbruch.removeEventListener("abort", weg);
        URL.revokeObjectURL(adresse);
        fertig();
      };
      const weg = () => {
        t.pause();
        ende();
      };
      abbruch.addEventListener("abort", weg);
      t.onended = t.onerror = ende;
      t.src = adresse;
      t.play().catch(ende);
    });
  }

  async sprich(text: string, abbruch: AbortSignal): Promise<void> {
    if (!geraetDa()) return;
    const gewaehlt = vorlesen.stimme.startsWith("geraet:") ? vorlesen.stimme.slice("geraet:".length) : (geraetestimmen()[0]?.id.slice("geraet:".length) ?? "");
    const weg = () => this.#geraet.halt();
    abbruch.addEventListener("abort", weg);
    try {
      await this.#geraet.spiele({ text, von: 0, bis: text.length, ton: null, dauer: text.length / 14 }, gewaehlt, () => {});
    } finally {
      abbruch.removeEventListener("abort", weg);
    }
  }
}

export const ansage = new Ansage(new Browserton(), () => vorlesen.aktiv && !vorlesen.pausiert);
