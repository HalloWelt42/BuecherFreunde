// Ansagen im Kinderbereich (BF-78, Entwurf Runde 4): die einzige Stelle, an der etwas gesprochen wird, das kein Vorlesen ist.
// Hinweise (Lesezeit, fünf Minuten vorher, Ruhezeit, Schloss, Katze benennen, leere Regale, Ende des Buchs) und nach dem Druck
// jede Taste und jeder Umschlag mit ihrem Namen. Je Kind abschaltbar (Lesehilfen hinweise_sprechen und tasten_ansagen).
//
// Töne: fertige Sätze in der Stimme, die die Eltern nach einer Probe gewählt haben (GET /api/familie/ansagen), je Schlüssel
// (lib/kind/ansagen.ts). Eine Ansage ist eine Folge von Schlüsseln, die ohne Pause hintereinander klingen (die Uhr: "Es ist vier
// Uhr", "fünfunddreißig", "Noch fünfundzwanzig Minuten"). Töne werden bei Bedarf geholt und je Seite gemerkt. Fehlt ein Ton
// (der Auftrag läuft noch), bleibt die Ansage still; nur wenn die Eltern die Stimme des Geräts gewählt haben, spricht sie den Text.
//
// Regeln: Eine neue Ansage beendet die laufende, es gibt keine Warteschlange. Über das Vorlesen wird nie gesprochen; während
// des Vorlesens sagen nur die Tasten an, die den Vorlesestrom selbst steuern, und wer sie bedient, lässt das Vorlesen erst
// danach weiterklingen (fertig()). Die Ansage kommt nach der Wirkung der Taste. Vor dem ersten Antippen bleibt alles still.
import { anfrage, get } from "../api/client";
import { vorlesen } from "../stand/vorlesen.svelte";
import { stilleAdresse } from "../vorlesen/ton";
import { geraetDa, geraetestimmen, Geraetesprecher } from "../vorlesen/geraet";
import type { Ansagefolge } from "./ansagen";

export interface Ansageeintrag {
  text: string;
  /** Der fertige Ton (GET /api/familie/ansagen/ton/{ordner}/{datei}); null mit der Stimme des Geräts */
  url: string | null;
}

/** GET /api/familie/ansagen: für das aktive Profil, ohne Profil die der Profilwahl in der Stimme der Familie */
export interface Ansagekatalog {
  /** Die Stimme, die die Eltern gewählt haben; "geraet": die Stimme des Geräts */
  stimme: string;
  fertig: number;
  gesamt: number;
  /** Der Auftrag, die Töne zu sprechen, läuft noch */
  laeuft: boolean;
  eintraege: Record<string, Ansageeintrag>;
}

export const GERAETESTIMME = "geraet";

export interface Tonquelle {
  katalog(): Promise<Ansagekatalog>;
  hole(url: string): Promise<Blob>;
  spiele(ton: Blob, abbruch: AbortSignal): Promise<void>;
  /** Mit der Stimme des Geräts */
  sprich(text: string, abbruch: AbortSignal): Promise<void>;
  /** Noch im Tippen: gibt den Ton frei */
  entsperre(): void;
}

/** Klingt gerade Vorlesen? */
export type Vorlesenklingt = () => boolean;

/** Länger wartet niemand auf das Ende einer Ansage */
const HOECHSTENS_MS = 4000;
/** So oft wird nachgefragt, solange die Töne noch entstehen */
const NACHFRAGE_MS = 30_000;

export class Ansage {
  hinweise = $state(false);
  tasten = $state(false);
  katalog = $state.raw<Ansagekatalog | null>(null);
  #frei = false;
  #laufend: { abbruch: AbortController; fertig: Promise<void> } | null = null;
  #toene = new Map<string, Promise<Blob>>();
  #nachfrage: ReturnType<typeof setTimeout> | undefined;

  constructor(private quelle: Tonquelle, private klingt: Vorlesenklingt) {}

  /** Was die Eltern für dieses Kind eingestellt haben */
  stelle(hinweise: boolean, tasten: boolean): void {
    this.hinweise = hinweise;
    this.tasten = tasten;
    if (!hinweise && !tasten) this.stoppe();
  }

  /** Die Töne des Kindes; solange sie entstehen, wird nachgefragt */
  async lade(): Promise<void> {
    clearTimeout(this.#nachfrage);
    try {
      this.katalog = await this.quelle.katalog();
    } catch {
      // ohne Antwort bleibt, was bekannt ist
    }
    if (!this.katalog || this.katalog.laeuft) this.#nachfrage = setTimeout(() => void this.lade(), NACHFRAGE_MS);
  }

  /** Nicht mehr nachfragen (der Bereich ist weg) */
  beende(): void {
    clearTimeout(this.#nachfrage);
    this.stoppe();
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
  hinweis(folge: Ansagefolge): Promise<void> {
    if (!this.hinweise || this.klingt()) return Promise.resolve();
    return this.#sage(folge);
  }

  /** Nach dem Druck einer Taste; strom: sie steuert das Vorlesen selbst und darf auch während des Vorlesens kurz ansagen */
  taste(folge: Ansagefolge, strom = false): Promise<void> {
    if (!this.tasten || (this.klingt() && !strom)) return Promise.resolve();
    return this.#sage(folge);
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

  /** Die Einträge einer Folge; null, wenn einer fehlt oder noch keinen Ton hat */
  eintraege(folge: Ansagefolge): Ansageeintrag[] | null {
    const k = this.katalog;
    if (!k || !folge.length) return null;
    const geraet = k.stimme === GERAETESTIMME;
    const teile = folge.map((s) => k.eintraege[s]);
    return teile.every((t) => t && (geraet ? t.text : t.url)) ? teile : null;
  }

  #sage(folge: Ansagefolge): Promise<void> {
    const teile = this.eintraege(folge);
    // Fehlt ein Ton, bleibt diese Ansage still; die laufende endet trotzdem, eine neue Taste gilt
    this.stoppe();
    if (!this.#frei || !teile) return Promise.resolve();
    const abbruch = new AbortController();
    const fertig = this.#klinge(teile, abbruch.signal).catch(() => undefined);
    const lauf = { abbruch, fertig };
    this.#laufend = lauf;
    void fertig.then(() => {
      if (this.#laufend === lauf) this.#laufend = null;
    });
    return fertig;
  }

  async #klinge(teile: Ansageeintrag[], abbruch: AbortSignal): Promise<void> {
    if (this.katalog?.stimme === GERAETESTIMME) return this.quelle.sprich(teile.map((t) => t.text).join(" "), abbruch);
    // Erst alle Töne, dann ohne Pause hintereinander
    const toene = await Promise.all(teile.map((t) => this.#ton(t.url!)));
    for (const ton of toene) {
      if (abbruch.aborted) return;
      await this.quelle.spiele(ton, abbruch);
    }
  }

  #ton(url: string): Promise<Blob> {
    let t = this.#toene.get(url);
    if (!t) {
      t = this.quelle.hole(url);
      t.catch(() => this.#toene.delete(url));
      this.#toene.set(url, t);
    }
    return t;
  }
}

/** Der Ton im Browser: ein eigenes Tonelement, sonst die Stimmen des Geräts */
class Browserton implements Tonquelle {
  #element: HTMLAudioElement | null = null;
  #geraet = new Geraetesprecher();

  #ton(): HTMLAudioElement {
    this.#element ??= new Audio();
    return this.#element;
  }

  katalog(): Promise<Ansagekatalog> {
    return get<Ansagekatalog>("/api/familie/ansagen");
  }

  async hole(url: string): Promise<Blob> {
    return (await anfrage(url)).blob();
  }

  entsperre(): void {
    const t = this.#ton();
    t.src = stilleAdresse();
    void t.play().catch(() => undefined);
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
