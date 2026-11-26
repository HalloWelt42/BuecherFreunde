// Wie die Oberfläche aussieht: Licht, Glas, Dahinter, Schrift. Gemerkt im Browser, gesetzt als Merkmale an <html>.
import { lies, merke } from "../speicher";

export type Thema = "light" | "dark" | "system";
export type Glas = "" | "klar" | "dicht" | "ohne";
export type Grund = "" | "licht" | "ruhig" | "bild";
export type Schriftstufe = "" | "mittel" | "gross" | "riesig";

const DUNKEL = "(prefers-color-scheme: dark)";

export const wahlen = {
  thema: [["light", "Hell"], ["dark", "Dunkel"], ["system", "System"]] as [Thema, string][],
  glas: [["klar", "Klar"], ["", "Milchig"], ["dicht", "Dicht"], ["ohne", "Ohne"]] as [Glas, string][],
  grund: [["", "Regalwand"], ["licht", "Licht"], ["ruhig", "Ruhig"], ["bild", "Eigenes Bild"]] as [Grund, string][],
  schrift: [["", "Klein"], ["mittel", "Mittel"], ["gross", "Groß"], ["riesig", "Sehr groß"]] as [Schriftstufe, string][],
};

function gueltig<T extends string>(wert: string, liste: [T, string][], vorgabe: T): T {
  return liste.some(([w]) => w === wert) ? (wert as T) : vorgabe;
}

class Darstellung {
  #thema = $state<Thema>(gueltig(lies("theme", "system"), wahlen.thema, "system"));
  #glas = $state<Glas>(gueltig(lies("darstellung.glas"), wahlen.glas, ""));
  #grund = $state<Grund>(gueltig(lies("darstellung.grund"), wahlen.grund, ""));
  #schrift = $state<Schriftstufe>(gueltig(lies("darstellung.schrift"), wahlen.schrift, ""));
  #systemDunkel = $state(false);

  constructor() {
    const abfrage = window.matchMedia(DUNKEL);
    this.#systemDunkel = abfrage.matches;
    abfrage.addEventListener("change", (e) => {
      this.#systemDunkel = e.matches;
      this.anwenden();
    });
  }

  get thema(): Thema {
    return this.#thema;
  }
  set thema(wert: Thema) {
    this.#thema = wert;
    merke("theme", wert);
    this.anwenden();
  }

  get glas(): Glas {
    return this.#glas;
  }
  set glas(wert: Glas) {
    this.#glas = wert;
    merke("darstellung.glas", wert);
    this.anwenden();
  }

  get grund(): Grund {
    return this.#grund;
  }
  set grund(wert: Grund) {
    this.#grund = wert;
    merke("darstellung.grund", wert);
    this.anwenden();
  }

  get schrift(): Schriftstufe {
    return this.#schrift;
  }
  set schrift(wert: Schriftstufe) {
    this.#schrift = wert;
    merke("darstellung.schrift", wert);
    this.anwenden();
  }

  /** Gilt gerade die dunkle Seite? */
  get dunkel(): boolean {
    return this.#thema === "dark" || (this.#thema === "system" && this.#systemDunkel);
  }

  anwenden(): void {
    const merkmale = document.documentElement.dataset;
    merkmale.theme = this.dunkel ? "dark" : "light";
    for (const [name, wert] of [["glas", this.#glas], ["grund", this.#grund], ["schrift", this.#schrift]]) {
      if (wert) merkmale[name] = wert;
      else delete merkmale[name];
    }
    statusleiste();
  }
}

/**
 * Statusleiste und Leiste des Browsers in der Farbe des Grunds (--grund in stil/marken.css). Bis das Skript läuft, gelten
 * die zwei Angaben in index.html nach der Einstellung des Geräts; danach eine, die der gewählten Darstellung folgt (der
 * Leser färbt sie im Vollbild um, lib/stand/blattgrund.ts).
 */
function statusleiste(): void {
  const [meta, ...weitere] = document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]');
  if (!meta) return;
  for (const m of weitere) m.remove();
  meta.removeAttribute("media");
  meta.content = getComputedStyle(document.documentElement).getPropertyValue("--grund").trim() || meta.content;
}

export const darstellung = new Darstellung();
