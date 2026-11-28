// Verweise auf einer PDF-Seite (BF-125): die Links der Datei (Anmerkungen vom Typ Link, nach außen oder auf eine Seite)
// und Adressen, die nur als Text dastehen. Eine eigene Ebene über der Textebene trägt je Verweis unsichtbare Flächen zum
// Anklicken; die Textebene selbst bleibt unberührt, denn Markierungen suchen dort ihren Wortlaut (pdf/markierung.ts).

/** Wohin ein Verweis führt: eine Adresse nach außen oder eine Seite des Buchs */
export type Verweisziel = { art: "adresse"; adresse: string } | { art: "seite"; seite: number };

export interface Flaeche {
  x: number;
  y: number;
  breite: number;
  hoehe: number;
}

export interface Verweis {
  ziel: Verweisziel;
  flaechen: Flaeche[];
}

/** Eine Adresse im Text: ihre Stücke im zusammengesetzten Text der Seite (bricht sie um, je Zeile eines) */
export interface Textadresse {
  adresse: string;
  stuecke: [von: number, bis: number][];
}

const ANFANG = /(?:https?:\/\/|www\.)[^\s<>"'„“”‚‘’«»]+/giu;
/** Satzzeichen am Ende gehören zum Satz, nicht zur Adresse */
const SCHLUSS = /[.,;:!?'"»“”]+$/u;
/** Endet eine Zeile mitten in einer Adresse an einem dieser Zeichen, geht sie in der nächsten weiter; ein Punkt am Zeilenende
 *  schließt meist den Satz und zählt darum nicht */
const BRICHT_UM = /[/\-_?=&#%~]$/u;
const WEITER = /^[^\s<>"'„“”‚‘’«»]+/u;
/** Nach außen nur diese Arten; alles andere (etwa javascript:) wird kein Verweis */
const ERLAUBT = new Set(["http:", "https:", "mailto:"]);

/** Ohne Satzzeichen am Ende; eine schließende Klammer bleibt nur, wenn die Adresse sie auch öffnet */
function ohneSchluss(roh: string): string {
  let t = roh.trim().replace(SCHLUSS, "");
  while (t.endsWith(")") && (t.match(/\(/g)?.length ?? 0) < (t.match(/\)/g)?.length ?? 0)) t = t.slice(0, -1).replace(SCHLUSS, "");
  return t;
}

/** Die Adresse, wie der Browser sie öffnet; null, wenn sie keine gültige ist */
export function adresseVon(roh: string): string | null {
  const t = ohneSchluss(roh);
  const voll = /^www\./i.test(t) ? `https://${t}` : t;
  try {
    const u = new URL(voll);
    if (!ERLAUBT.has(u.protocol)) return null;
    if (u.protocol !== "mailto:" && !u.hostname.includes(".")) return null;
    return u.href;
  } catch {
    return null;
  }
}

/** Adressen im Text einer Seite; Zeilen sind durch "\n" getrennt */
export function adressenIn(text: string): Textadresse[] {
  const aus: Textadresse[] = [];
  let verbraucht = 0;
  for (const m of text.matchAll(ANFANG)) {
    // In der Fortsetzung einer umbrochenen Adresse beginnt keine neue
    if (m.index < verbraucht) continue;
    let von = m.index;
    let bis = von + m[0].length;
    let roh = m[0];
    const stuecke: [number, number][] = [];
    // Über das Zeilenende weiter, solange die Adresse dort sichtbar umbricht
    while (text[bis] === "\n" && BRICHT_UM.test(roh)) {
      const weiter = WEITER.exec(text.slice(bis + 1));
      if (!weiter) break;
      stuecke.push([von, bis]);
      von = bis + 1;
      bis = von + weiter[0].length;
      roh += weiter[0];
    }
    verbraucht = bis;
    const adresse = adresseVon(roh);
    if (!adresse) continue;
    // Was am Ende als Satzzeichen wegfiel, gehört auch nicht zur Fläche
    stuecke.push([von, Math.max(von + 1, bis - (roh.length - ohneSchluss(roh).length))]);
    aus.push({ adresse, stuecke });
  }
  return aus;
}

/** Der Text einer Textebene von pdf.js: ihre Textknoten in Lesefolge, ein Zeilenende als "\n" */
export class Ebenentext {
  readonly text: string;
  readonly #stuecke: { knoten: Text; von: number }[] = [];

  constructor(ebene: HTMLElement) {
    const teile: string[] = [];
    let laenge = 0;
    const gang = ebene.ownerDocument.createTreeWalker(ebene, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    for (let k = gang.nextNode(); k; k = gang.nextNode()) {
      if (k.nodeType === Node.TEXT_NODE) {
        const t = k as Text;
        this.#stuecke.push({ knoten: t, von: laenge });
        teile.push(t.data);
        laenge += t.data.length;
      } else if ((k as Element).tagName === "BR") {
        teile.push("\n");
        laenge += 1;
      }
    }
    this.text = teile.join("");
  }

  /** Der Bereich zwischen zwei Stellen des Textes; null, wo kein Textknoten liegt */
  bereich(von: number, bis: number): Range | null {
    const a = this.#stelle(von, false);
    const b = this.#stelle(bis, true);
    if (!a || !b) return null;
    const r = a.knoten.ownerDocument.createRange();
    r.setStart(a.knoten, a.versatz);
    r.setEnd(b.knoten, b.versatz);
    return r;
  }

  #stelle(i: number, ende: boolean): { knoten: Text; versatz: number } | null {
    for (const s of this.#stuecke) {
      const rest = i - s.von;
      if (rest >= 0 && (ende ? rest <= s.knoten.data.length && rest > 0 : rest < s.knoten.data.length)) return { knoten: s.knoten, versatz: rest };
    }
    return null;
  }
}

const ueberdeckt = (a: Flaeche, b: Flaeche) => {
  const x = Math.min(a.x + a.breite, b.x + b.breite) - Math.max(a.x, b.x);
  const y = Math.min(a.y + a.hoehe, b.y + b.hoehe) - Math.max(a.y, b.y);
  return x > 0 && y > 0 && x * y >= 0.5 * a.breite * a.hoehe;
};

/** Die Adressen im Text der Ebene als Flächen, bezogen auf den Rahmen der Seite; was ein Link der Datei schon deckt, fällt weg */
export function textverweise(ebene: HTMLElement, rahmen: { left: number; top: number }, schonDa: Verweis[]): Verweis[] {
  const text = new Ebenentext(ebene);
  const belegt = schonDa.flatMap((v) => v.flaechen);
  const aus: Verweis[] = [];
  for (const a of adressenIn(text.text)) {
    const flaechen = a.stuecke.flatMap(([von, bis]) => [...(text.bereich(von, bis)?.getClientRects() ?? [])])
      .filter((r) => r.width > 0 && r.height > 0)
      .map((r) => ({ x: r.left - rahmen.left, y: r.top - rahmen.top, breite: r.width, hoehe: r.height }));
    if (flaechen.length && !flaechen.every((f) => belegt.some((b) => ueberdeckt(f, b)))) aus.push({ ziel: { art: "adresse", adresse: a.adresse }, flaechen });
  }
  return aus;
}

/** Eine Anmerkung vom Typ Link, wie pdf.js sie liefert (nur, was hier zählt) */
export interface Linkanmerkung {
  subtype: string;
  rect: number[];
  url?: string;
  unsafeUrl?: string;
  dest?: string | unknown[] | null;
}

/** Die Links der Datei auf dieser Seite; rechteck rechnet von Punkten der Datei in Punkte der gezeichneten Seite */
export async function dateiverweise(anmerkungen: Linkanmerkung[], rechteck: (r: number[]) => number[], seiteVon: (ziel: string | unknown[]) => Promise<number | null>): Promise<Verweis[]> {
  const aus: Verweis[] = [];
  for (const a of anmerkungen) {
    if (a.subtype !== "Link" || a.rect?.length !== 4) continue;
    const [x1, y1, x2, y2] = rechteck(a.rect);
    const flaeche = { x: Math.min(x1, x2), y: Math.min(y1, y2), breite: Math.abs(x2 - x1), hoehe: Math.abs(y2 - y1) };
    if (!flaeche.breite || !flaeche.hoehe) continue;
    const adresse = a.url ? adresseVon(a.url) : null;
    if (adresse) aus.push({ ziel: { art: "adresse", adresse }, flaechen: [flaeche] });
    else if (a.dest) {
      const seite = await seiteVon(a.dest);
      if (seite) aus.push({ ziel: { art: "seite", seite }, flaechen: [flaeche] });
    }
  }
  return aus;
}

/** Die Ebene mit den Flächen zum Anklicken; ein Verweis auf eine Seite geht an springe */
export function verweisebene(dok: Document, verweise: Verweis[], springe: (seite: number) => void): HTMLElement {
  const ebene = dok.createElement("div");
  ebene.className = "verweisebene";
  for (const v of verweise) {
    for (const f of v.flaechen) {
      const a = dok.createElement("a");
      a.className = "verweis";
      a.draggable = false;
      Object.assign(a.style, { left: `${f.x}px`, top: `${f.y}px`, width: `${f.breite}px`, height: `${f.hoehe}px` });
      if (v.ziel.art === "adresse") {
        a.href = v.ziel.adresse;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.title = v.ziel.adresse.replace(/^mailto:/, "");
      } else {
        const seite = v.ziel.seite;
        a.href = `#seite-${seite}`;
        a.title = `Zu Seite ${seite}`;
        a.addEventListener("click", (e) => {
          e.preventDefault();
          springe(seite);
        });
      }
      ebene.append(a);
    }
  }
  return ebene;
}
