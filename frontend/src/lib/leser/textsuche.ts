// Wortlaut in zerstückeltem Text finden: verglichen ohne Leerraum, weil Textebene und Volltext ihn verschieden setzen

export interface Bereich {
  von: number;
  bis: number;
}

const KURZ = [60, 30, 15];
const HOECHSTENS = 160;

const ohneLeer = (t: string) => t.replace(/\s+/g, "");
const LEER = /\s/;

/**
 * Die Stücke, die zum gesuchten Wortlaut gehören, als Bereich der Nummern [von, bis). Findet sich nicht alles, zählt ein
 * kürzerer Anfang. ab: erst ab diesem Anteil (0 bis 1) des Textes suchen, sonst von vorn.
 */
export function findeStuecke(stuecke: string[], wortlaut: string, ab = 0): Bereich | null {
  const gesucht = ohneLeer(wortlaut).toLowerCase();
  if (gesucht.length < 2) return null;
  const teile = stuecke.map((s) => ohneLeer(s).toLowerCase());
  const anfaenge: number[] = [];
  let laenge = 0;
  for (const t of teile) {
    anfaenge.push(laenge);
    laenge += t.length;
  }
  const alles = teile.join("");
  const nach = Math.floor(ab * alles.length);
  const suche = (w: string) => {
    const spaeter = alles.indexOf(w, nach);
    return spaeter >= 0 || nach === 0 ? spaeter : alles.indexOf(w);
  };
  let stelle = suche(gesucht);
  let umfang = gesucht.length;
  for (const kurz of KURZ) {
    if (stelle >= 0) break;
    if (gesucht.length <= kurz) continue;
    stelle = suche(gesucht.slice(0, kurz));
    umfang = Math.min(gesucht.length, HOECHSTENS);
  }
  if (stelle < 0) return null;
  const ende = Math.min(stelle + umfang, alles.length);
  const beruehrt = teile.map((t, i) => t.length > 0 && anfaenge[i] < ende && anfaenge[i] + t.length > stelle);
  const von = beruehrt.indexOf(true);
  return von < 0 ? null : { von, bis: beruehrt.lastIndexOf(true) + 1 };
}

export interface Zeichenstelle {
  knoten: Text;
  versatz: number;
}

/**
 * Der Text vieler Textknoten ohne Leerraum und klein geschrieben, einmal gebaut; jede Suche darin kostet danach nur das
 * Suchen. Für tausend Markierungen auf einem Blatt wird er einmal gebaut statt tausendmal (BF-47).
 */
export class Zeichenindex {
  readonly #knoten: Text[];
  readonly #text: string;
  /** Je Zeichen des Textes: welcher Knoten und welche Stelle darin */
  readonly #nr: Uint32Array;
  readonly #versatz: Uint32Array;

  constructor(knoten: Text[]) {
    this.#knoten = knoten;
    const laenge = knoten.reduce((n, k) => n + k.data.length, 0);
    const nr = new Uint32Array(laenge);
    const versatz = new Uint32Array(laenge);
    const zeichen: string[] = [];
    knoten.forEach((k, i) => {
      const d = k.data;
      for (let j = 0; j < d.length; j++) {
        if (LEER.test(d[j])) continue;
        nr[zeichen.length] = i;
        versatz[zeichen.length] = j;
        zeichen.push(d[j].toLowerCase()[0]);
      }
    });
    this.#text = zeichen.join("");
    this.#nr = nr.subarray(0, zeichen.length);
    this.#versatz = versatz.subarray(0, zeichen.length);
  }

  /** Wortlaut als Anfang und Ende, zeichengenau; anteil: die Fundstelle, die diesem Anteil am nächsten liegt (sonst die erste) */
  finde(wortlaut: string, anteil: number | null): { von: Zeichenstelle; bis: Zeichenstelle } | null {
    const gesucht = ohneLeer(wortlaut).toLowerCase();
    if (gesucht.length < 2) return null;
    const beste = this.#naechste(gesucht, anteil === null ? 0 : anteil * this.#text.length);
    if (beste < 0) return null;
    const letzte = this.#stelle(beste + gesucht.length - 1);
    return { von: this.#stelle(beste), bis: { knoten: letzte.knoten, versatz: letzte.versatz + 1 } };
  }

  /** Die Fundstelle, die ziel am nächsten liegt; bei gleichem Abstand die frühere */
  #naechste(gesucht: string, ziel: number): number {
    const davor = this.#text.lastIndexOf(gesucht, Math.floor(ziel));
    const danach = this.#text.indexOf(gesucht, davor + 1);
    if (davor < 0 || danach < 0) return Math.max(davor, danach);
    return Math.abs(davor - ziel) <= Math.abs(danach - ziel) ? davor : danach;
  }

  #stelle(i: number): Zeichenstelle {
    return { knoten: this.#knoten[this.#nr[i]], versatz: this.#versatz[i] };
  }
}


/** Ein einzelner Wortlaut; wer viele sucht, baut den Zeichenindex einmal */
export function findeZeichen(knoten: Text[], wortlaut: string, anteil: number | null): { von: Zeichenstelle; bis: Zeichenstelle } | null {
  return new Zeichenindex(knoten).finde(wortlaut, anteil);
}
