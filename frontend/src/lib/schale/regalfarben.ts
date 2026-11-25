// Farben der Regalwand: Vorgabe aus dem Entwurf, danach aus den eigenen Umschlägen, je Sitzung einmal gesammelt
import { farbenAusBild, type Dreiklang } from "../farben";
import { VORGABE } from "../palette";
import { liesJson, merkeJson } from "../speicher";
import { wahl } from "../stand/wahl.svelte";

const SCHLUESSEL = "regalwand.farben";
const HOECHSTENS = 60;
const MINDESTENS = 12;
const RUHE_MS = 4000;

type Zuhoerer = (farben: Dreiklang[]) => void;

class Regalfarben {
  #gesammelt = new Map<number, Dreiklang>();
  #uhr: ReturnType<typeof setTimeout> | undefined;
  #fertig = false;
  #zuhoerer: Zuhoerer | null = null;

  get jetzt(): Dreiklang[] {
    const gemerkt = liesJson<Dreiklang[]>(SCHLUESSEL, []);
    return gemerkt.length >= MINDESTENS ? gemerkt : VORGABE;
  }

  beiNeuen(tun: Zuhoerer): () => void {
    this.#zuhoerer = tun;
    return () => {
      this.#zuhoerer = null;
    };
  }

  /** Ein Umschlag ist geladen: Farben für Licht und Wand nehmen */
  sammle(id: number, bild: HTMLImageElement): void {
    if (this.#gesammelt.has(id) || wahl.kenntFarben(id)) return;
    const farben = farbenAusBild(bild);
    if (!farben) return;
    wahl.merkeFarben(id, farben);
    if (this.#fertig) return;
    this.#gesammelt.set(id, farben);
    clearTimeout(this.#uhr);
    if (this.#gesammelt.size >= HOECHSTENS) this.#abschliessen();
    else this.#uhr = setTimeout(() => this.#abschliessen(), RUHE_MS);
  }

  #abschliessen(): void {
    if (this.#fertig || this.#gesammelt.size < MINDESTENS) return;
    this.#fertig = true;
    const farben = [...this.#gesammelt.values()];
    merkeJson(SCHLUESSEL, farben);
    this.#zuhoerer?.(farben);
  }
}

export const regalfarben = new Regalfarben();
