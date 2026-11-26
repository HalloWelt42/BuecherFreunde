// Ziehen und Ablegen mit der Maus (BF-67) über das Ziehen des Browsers. Am Telefon wird nicht gezogen, dort gelten
// Haken und Tasten. Es zieht immer nur eines zugleich, deshalb gibt es diesen Zustand einmal.
import type { Spalte } from "./zuordnung.svelte";

/** Eigene Art der Daten: fällt nichts in Textfelder, wenn man daneben loslässt */
const ZIEHART = "application/x-buecherfreunde-buecher";

class Ziehen {
  von = $state<Spalte | null>(null);
  ids = $state<ReadonlySet<number>>(new Set());
  /** Wo es landen würde: die Spalte und das Buch, vor dem es einsortiert wird (null: am Ende) */
  ueber = $state<{ spalte: Spalte; vor: number | null } | null>(null);
  #nr = 0;

  zieht(id: number): boolean {
    return this.ids.has(id);
  }

  beginne(e: DragEvent, von: Spalte, ids: number[]): void {
    const daten = e.dataTransfer;
    if (!daten) return;
    daten.setData(ZIEHART, ids.join(","));
    daten.effectAllowed = "move";
    if (e.currentTarget instanceof HTMLElement) zeigeSchwebebild(daten, e.currentTarget, ids.length);
    // Erst nach dem Beginn die Oberfläche ändern: ändert sie sich noch im selben Augenblick, bricht manch ein Browser das Ziehen ab
    const nr = ++this.#nr;
    setTimeout(() => {
      if (nr !== this.#nr) return;
      this.von = von;
      this.ids = new Set(ids);
    }, 0);
  }

  ende(): void {
    this.#nr++;
    this.von = null;
    this.ids = new Set();
    this.ueber = null;
  }
}

/** Die gezogene Zeile schräg mit Schatten wie im Entwurf, bei mehreren mit ihrer Zahl. Der Browser nimmt ein Abbild
 *  davon; danach wird sie gleich wieder entfernt. */
function zeigeSchwebebild(daten: DataTransfer, zeile: HTMLElement, zahl: number): void {
  const huelle = document.createElement("div");
  huelle.className = "schwebebild";
  const kopie = zeile.cloneNode(true) as HTMLElement;
  kopie.classList.add("schwebend");
  kopie.style.width = `${zeile.offsetWidth}px`;
  huelle.append(kopie);
  if (zahl > 1) {
    const marke = document.createElement("span");
    marke.className = "schwebezahl";
    marke.textContent = String(zahl);
    huelle.append(marke);
  }
  document.body.append(huelle);
  daten.setDragImage(huelle, 28, 24);
  setTimeout(() => huelle.remove(), 0);
}

export const ziehen = new Ziehen();
