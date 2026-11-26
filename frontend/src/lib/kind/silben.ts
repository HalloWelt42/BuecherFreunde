// Farbige Silben (BF-78): deutsche Silbentrennung nach den Trennmustern von TeX für die Rechtschreibung von 1996 (Paket
// hyphen, ISC-Lizenz, Muster aus hyph-utf8), erst geladen, wenn ein Kind die Silben sieht. Die Trennmuster lassen eine einzelne
// Silbe am Wortanfang aus (Ufer, Oma); für Kinder zählt sie mit (U-fer, O-ma). Eine Silbe ohne Selbstlaut gibt es nicht.

type Trenner = (wort: string) => string;

const WEICH = "­";
const SELBSTLAUT = /[aeiouyäöüáàâéèêíìîóòôúùû]/i;
const DOPPELLAUT = /^(?:ei|ai|au|eu|äu|ie|ey|ay)/i;
/** Ein Mitlaut, wie er gesprochen wird: sch, ch, ck, ph, qu, th zählen als einer */
const MITLAUT = /^(?:sch|ch|ck|ph|qu|th|[bcdfghjklmnpqrstvwxzß])/i;

let trenner: Trenner | null = null;
let laden: Promise<Trenner> | null = null;

/** Lädt die Trennmuster einmal; danach trennt silben() sofort */
export function ladeSilbentrenner(): Promise<Trenner> {
  laden ??= import("hyphen/de-1996").then((m) => {
    const t: Trenner = (wort) => m.hyphenateSync(wort, { hyphenChar: WEICH, minWordLength: 2 });
    trenner = t;
    return t;
  });
  return laden;
}

export const silbentrennerBereit = (): boolean => trenner !== null;

/** Ein einzelner Selbstlaut am Anfang vor einem Mitlaut und einem Selbstlaut ist eine eigene Silbe: U-fer, a-ber, E-cke */
function randsilbe(teil: string): string[] {
  if (teil.length < 3 || DOPPELLAUT.test(teil) || !SELBSTLAUT.test(teil[0])) return [teil];
  const mitlaut = MITLAUT.exec(teil.slice(1));
  if (!mitlaut) return [teil];
  const danach = 1 + mitlaut[0].length;
  return danach < teil.length && SELBSTLAUT.test(teil[danach]) ? [teil[0], teil.slice(1)] : [teil];
}

/** Silben aus einem getrennten Wort (Trennstellen als weiches Trennzeichen) */
export function silbenAus(getrennt: string): string[] {
  const teile = getrennt.split(WEICH).filter(Boolean).flatMap(randsilbe);
  // Ein Stück ohne Selbstlaut gehört zur Silbe davor, am Anfang zur nächsten
  const aus: string[] = [];
  for (const t of teile) {
    if (!SELBSTLAUT.test(t) && aus.length) aus[aus.length - 1] += t;
    else if (aus.length && !SELBSTLAUT.test(aus[aus.length - 1])) aus[aus.length - 1] += t;
    else aus.push(t);
  }
  return aus;
}

/** Die Silben eines Wortes aus Buchstaben; ohne geladene Trennmuster bleibt es ganz */
export function silben(wort: string, trenne: Trenner | null = trenner): string[] {
  if (!wort) return [];
  if (!trenne || !SELBSTLAUT.test(wort)) return [wort];
  return silbenAus(trenne(wort));
}

/** Ein Wort aus dem Text in Satzzeichen davor, den Kern aus Buchstaben und Satzzeichen danach */
export interface Wortteile {
  vor: string;
  kern: string;
  nach: string;
}

export function wortteile(text: string): Wortteile {
  const m = /^([^\p{L}\p{N}]*)(.*?)([^\p{L}\p{N}]*)$/su.exec(text);
  return m ? { vor: m[1], kern: m[2], nach: m[3] } : { vor: "", kern: text, nach: "" };
}

/** Silben eines Wortkerns; Bindestriche trennen Teile, die je für sich getrennt werden (Erdbeer-Eis) */
export function kernsilben(kern: string, trenne: Trenner | null = trenner): string[] {
  const aus: string[] = [];
  for (const teil of kern.split(/(-)/)) {
    if (teil === "-") {
      if (aus.length) aus[aus.length - 1] += "-";
      else aus.push("-");
    } else if (/^\p{L}+$/u.test(teil)) aus.push(...silben(teil, trenne));
    else if (teil) aus.push(teil);
  }
  return aus;
}

/** Wie viele Silben ein Wort hat; ein Maß für die Sprechdauer beim Mitlesen */
export function silbenzahl(text: string, trenne: Trenner | null = trenner): number {
  const { kern } = wortteile(text);
  if (!kern) return 0;
  if (trenne) return Math.max(1, kernsilben(kern, trenne).length);
  // Ohne Trennmuster: Gruppen von Selbstlauten zählen
  return Math.max(1, kern.match(/[aeiouyäöü]+/gi)?.length ?? 1);
}
