// Farben der Regalwand: Vorgabe aus dem Entwurf, danach aus den eigenen Umschlägen (Bild oder gestaltetes Blatt), je
// Sitzung einmal gesammelt
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
  /** Bücher, deren Farben aus ihrem Bild stammen; wechselt ein Buch zum Blatt und zurück, wird das Bild neu gelesen */
  #ausBild = new Set<number>();
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

  /** Ein Bild ist geladen: seine Farben für Licht und Wand, je Buch einmal gelesen */
  sammle(id: number, bild: HTMLImageElement): void {
    if (this.#ausBild.has(id)) return;
    const farben = farbenAusBild(bild);
    if (!farben) return;
    this.nimm(id, farben);
    this.#ausBild.add(id);
  }

  /** Farben, die schon feststehen, etwa die eines gestalteten Blatts (BF-59); für das Licht gilt, was zuletzt zu sehen war */
  nimm(id: number, farben: Dreiklang): void {
    this.#ausBild.delete(id);
    wahl.merkeFarben(id, farben);
    if (this.#fertig || this.#gesammelt.has(id)) return;
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
