// Text auf dem gestalteten Blatt setzen (BF-59): Umbruch, Größe nach Breite und Höhe, Maskieren für XML.
// Maße in Einheiten des Blatts (200 breit, 300 hoch). Längen zählen Zeichen; die Laufweite f (Geviert je Zeichen) macht
// daraus eine Breite.

/** Höhe des Blatts; die Breite ist 200 */
export const H = 300;

export const SERIF = "Literata, Georgia, serif";
export const GROTESK = "Barlow, sans-serif";

export type Anker = "start" | "middle" | "end";

// --- Maskieren ---

const XML: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" };
// Steuerzeichen außer Tab und Zeilenwechsel sind in XML verboten
const STEUERZEICHEN = /[\u0000-\u0008\u000B\u000C\u000E-\u001F￾￿]/g;

/** Angaben aus den Daten sicher in Text und Attribute des SVG: nichts bricht das Dokument, nichts wird eingeschleust */
export const maskiere = (text: string): string => text.replace(STEUERZEICHEN, "").replace(/[&<>"']/g, (z) => XML[z]);

// --- Längen ---

// Zeichen in voller Breite (Chinesisch, Japanisch, Koreanisch) sind etwa ein Geviert breit. Die Muster rechnen mit
// Laufweiten von .58 bis .645; 1,75 Zeichen decken auch die schmalste ab.
const VOLL = /[ᄀ-ᅟ⺀-꓏가-힣豈-﫿︰-﹏＀-｠￠-￦]/u;
const VOLLE_BREITE = 1.75;
const graphem = typeof Intl !== "undefined" && "Segmenter" in Intl ? new Intl.Segmenter("de", { granularity: "grapheme" }) : null;

const zeichen = (text: string): string[] => (graphem ? [...graphem.segment(text)].map((t) => t.segment) : [...text]);
const breiteVon = (z: string): number => (VOLL.test(z) ? VOLLE_BREITE : 1);

/** Länge in Zeichen; ein Umlaut aus zwei Teilen zählt einmal, Zeichen in voller Breite zählen mehr */
export const laenge = (text: string): number => zeichen(text).reduce((summe, z) => summe + breiteVon(z), 0);

/** Kürzt auf höchstens so viele Zeichen, am letzten Wort davor, und hängt " ..." an */
export function gekuerzt(text: string, hoechstens: number): string {
  if (laenge(text) <= hoechstens) return text;
  const ENDE = " ...";
  let stueck = "";
  let l = 0;
  for (const z of zeichen(text)) {
    if (l + breiteVon(z) > hoechstens - ENDE.length) break;
    stueck += z;
    l += breiteVon(z);
  }
  const wortende = stueck.lastIndexOf(" ");
  return `${(wortende > stueck.length / 2 ? stueck.slice(0, wortende) : stueck).replace(/[\s,;:]+$/, "")}${ENDE}`;
}

// --- Umbruch ---

interface Wort {
  text: string;
  laenge: number;
  /** Fortsetzung eines zu langen Worts: beginnt immer eine neue Zeile */
  fortsetzung: boolean;
}

export interface Zeile {
  text: string;
  laenge: number;
}

/** Ab dieser Länge bricht ein Wort in Stücke; kürzere bleiben ganz, die Schrift wird dann kleiner */
const WORT_HOECHSTENS = 20;

/** Ein zu langes Wort bricht an seinen Bindestrichen, sonst in gleich lange Stücke mit Trennstrich */
function stuecke(wort: string): string[] {
  if (laenge(wort) <= WORT_HOECHSTENS) return [wort];
  // Ohne Rückschau im Ausdruck: ältere iPads kennen sie nicht und brächen schon beim Laden ab
  const anBindestrichen = wort.match(/[^-]*-+|[^-]+/g) ?? [wort];
  if (anBindestrichen.length > 1) return anBindestrichen.flatMap(stuecke);
  const ganz = laenge(wort);
  const ziel = ganz / Math.ceil(ganz / (WORT_HOECHSTENS - 1));
  const teile: string[] = [];
  let jetzt = "";
  let summe = 0;
  for (const z of zeichen(wort)) {
    // Geschnitten wird, wo die Mitte des nächsten Zeichens hinter dem nächsten Ziel liegt: so werden es gleich lange Stücke
    if (jetzt && summe + breiteVon(z) / 2 > ziel * (teile.length + 1)) {
      teile.push(VOLL.test(jetzt.slice(-1)) ? jetzt : `${jetzt}-`);
      jetzt = "";
    }
    jetzt += z;
    summe += breiteVon(z);
  }
  return [...teile, jetzt];
}

function zerlege(text: string): Wort[] {
  return text.split(/\s+/).filter(Boolean).flatMap((wort) => stuecke(wort).map((s, i) => ({ text: s, laenge: laenge(s), fortsetzung: i > 0 })));
}

/** Füllt Zeilen bis n Zeichen; ein Wort länger als n steht allein */
function zeilen(woerter: Wort[], n: number): Zeile[] {
  const z: Zeile[] = [];
  for (const w of woerter) {
    const letzte = z[z.length - 1];
    if (letzte && !w.fortsetzung && letzte.laenge + 1 + w.laenge <= n) {
      letzte.text += ` ${w.text}`;
      letzte.laenge += 1 + w.laenge;
    } else z.push({ text: w.text, laenge: w.laenge });
  }
  return z;
}

const laengste = (z: Zeile[]): number => Math.max(...z.map((s) => s.laenge));

/** Zeilenlängen, unter denen das Einpassen wählt */
const KUERZESTE_ZEILE = 8;
const LAENGSTE_ZEILE = 28;

// --- Textzeilen ---

export interface Schrift {
  schrift?: string;
  w?: number;
  anker?: Anker;
}

function textzeile(text: string, x: number, y: number, farbe: string, grad: number, { schrift = GROTESK, w = 600, anker = "middle" }: Schrift): string {
  return `<text x="${x}" y="${y.toFixed(1)}" font-family="${schrift}" font-weight="${w}" font-size="${grad.toFixed(1)}" fill="${farbe}" text-anchor="${anker}">${maskiere(text)}</text>`;
}

/** Breite, die eine kleine Zeile höchstens einnimmt, in Zeichen bei Grad, Laufweite und Sperrung */
const zeichenFuer = (breit: number, grad: number, sperrung: number): number => Math.floor(breit / (grad * 0.58 + sperrung));

/** Autorzeile: 11 Grad, leicht gesperrt; zu lang wird sie gekürzt */
export function autorzeile(text: string, x: number, y: number, farbe: string, anker: Anker = "start", breit = 168): string {
  if (!text) return "";
  return `<text x="${x}" y="${y}" font-family="${GROTESK}" font-weight="600" font-size="11" letter-spacing=".4" fill="${farbe}" text-anchor="${anker}">${maskiere(gekuerzt(text, zeichenFuer(breit, 11, 0.4)))}</text>`;
}

/** Kleine Zeile: 10 Grad, gesperrt; zu lang wird sie gekürzt */
export function klein(text: string, x: number, y: number, farbe: string, anker: Anker = "middle", breit = 168): string {
  if (!text) return "";
  return `<text x="${x}" y="${y}" font-family="${GROTESK}" font-weight="500" font-size="10" letter-spacing=".5" fill="${farbe}" text-anchor="${anker}">${maskiere(gekuerzt(text, zeichenFuer(breit, 10, 0.5)))}</text>`;
}

// --- Titel mit fester Zeilenlänge ---

export interface Zeilensatz extends Schrift {
  /** Zeichen je Zeile */
  n?: number;
  max?: number;
  breit?: number;
  f?: number;
  abstand?: number;
  /** Tiefste Grundlinie der letzten Zeile; darüber hinaus wird die Schrift kleiner */
  bis?: number;
}

/** Zeilen und Größe für einen Titel mit fester Zeilenlänge: die längste Zeile füllt die Breite, die letzte endet bei bis.
 *  Reicht die Höhe nicht, werden die Zeilen länger, bis der Titel am größten steht (wie beim Einpassen); sonst bleibt n. */
export function setze(text: string, y: number, { n = 13, max = 27, breit = 164, f = 0.645, abstand = 1.13, bis = H }: Zeilensatz): { zeilen: Zeile[]; grad: number } {
  const woerter = zerlege(text);
  if (!woerter.length) return { zeilen: [], grad: max };
  const satz = (jeZeile: number) => {
    const z = zeilen(woerter, jeZeile);
    const nachBreite = Math.min(max, breit / (laengste(z) * f));
    const nachHoehe = z.length > 1 ? (bis - y) / ((z.length - 1) * abstand) : max;
    return { zeilen: z, grad: Math.min(nachBreite, nachHoehe), zuHoch: nachHoehe < nachBreite };
  };
  let best = satz(n);
  for (let laenger = n + 1; best.zuHoch && laenger <= LAENGSTE_ZEILE; laenger++) {
    const s = satz(laenger);
    if (s.grad > best.grad + 0.01) best = s;
  }
  return { zeilen: best.zeilen, grad: best.grad };
}

/** Titel ab der ersten Grundlinie y (so setzen ihn die Muster des Entwurfs) */
export function titel(text: string, x: number, y: number, farbe: string, o: Zeilensatz = {}): string {
  const { schrift = SERIF, w = 700, anker = "start", abstand = 1.13 } = o;
  const { zeilen: z, grad } = setze(text, y, o);
  return z.map((s, i) => textzeile(s.text, x, y + i * grad * abstand, farbe, grad, { schrift, w, anker })).join("");
}

// --- Eingepasster Titel ---

export interface Einpassung extends Schrift {
  breit: number;
  hoehe: number;
  max?: number;
  f?: number;
}

const BLOCK_ABSTAND = 1.15;

/** Höhe eines Blocks aus Zeilen in einem Grad: Zeilenabstände, die letzte Zeile ohne Durchschuss */
export const blockhoehe = (zeilenzahl: number, grad: number): number => grad * (zeilenzahl * BLOCK_ABSTAND - 0.15);

/** Einpassen: wählt die Zeilenlänge, bei der der Titel in Breite und Höhe am größten steht */
export function passe(text: string, { breit, hoehe, max = 22, f = 0.58 }: Einpassung): { zeilen: Zeile[]; grad: number } {
  const woerter = zerlege(text);
  if (!woerter.length) return { zeilen: [], grad: max };
  let best: { zeilen: Zeile[]; grad: number } | null = null;
  for (let n = KUERZESTE_ZEILE; n <= LAENGSTE_ZEILE; n++) {
    const z = zeilen(woerter, n);
    const grad = Math.min(max, breit / (laengste(z) * f), hoehe / blockhoehe(z.length, 1));
    if (!best || grad > best.grad + 0.01) best = { zeilen: z, grad };
  }
  return best!;
}

/** Titel oben bündig an y, eingepasst; gibt das SVG und die genutzte Höhe */
export function block(text: string, x: number, y: number, farbe: string, o: Einpassung): { svg: string; hoehe: number } {
  const { zeilen: z, grad } = passe(text, o);
  const svg = z.map((s, i) => textzeile(s.text, x, y + grad * 0.86 + i * grad * BLOCK_ABSTAND, farbe, grad, o)).join("");
  return { svg, hoehe: blockhoehe(z.length, grad) };
}
