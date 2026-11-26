// Angaben im eigenen Regal einer Sammlung (BF-66): Band, Titel ohne Reihennamen, Autoren
import type { Buch } from "../../lib/typen";

/** Trennzeichen zwischen Reihe und Titel: Bindestrich, Halbgeviert- und Geviertstrich, Doppelpunkt */
const STRICHE = "\\-\u2013\u2014:";
/** Wörter vor einer Bandnummer */
const BANDWORT = "(?:band|bd\\.?|teil|folge|nr\\.?|no\\.?|#)";

/** Ein Name als Muster: Sonderzeichen wörtlich, Leerraum beliebig lang */
function alsMuster(text: string): string {
  return text.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
}

/** Vorn: ein Name der Reihe, auch mit Nummer ("Reihe 03 - Titel", "Reihe Band 3: Titel", "Reihe: Titel") */
function ohneName(titel: string, name: string): string | null {
  if (!name.trim()) return null;
  const muster = new RegExp(`^${alsMuster(name)}(?![\\p{L}\\p{N}])\\s*(?:${BANDWORT}\\s*)?(?:\\d+[a-z]?(?![\\p{L}\\p{N}]))?\\s*[.)]?\\s*[${STRICHE},]?\\s*`, "iu");
  const m = titel.match(muster);
  return m && m[0].length < titel.length ? titel.slice(m[0].length) : null;
}

/** Vorn ein Kürzel mit genau der Bandnummer ("RZ 03 - Titel"), auch ohne bekannten Namen */
function ohneKuerzel(titel: string, band: string): string | null {
  const nummer = Number.parseInt(band, 10);
  if (!Number.isFinite(nummer)) return null;
  const m = titel.match(new RegExp(`^\\S.{0,40}?\\s(?:${BANDWORT}\\s*)?0*${nummer}(?!\\d)\\s*[.)]?\\s*[${STRICHE}]\\s*(?=\\S)`, "iu"));
  return m ? titel.slice(m[0].length) : null;
}

/** Hinten: "(Reihe 3)" oder "- Reihe 3" */
function ohneEnde(titel: string, name: string): string {
  if (!name.trim()) return titel;
  const n = alsMuster(name);
  return titel.replace(new RegExp(`\\s*(?:\\(\\s*${n}(?![\\p{L}])[^()]*\\)|[${STRICHE},]\\s*${n}(?![\\p{L}])[^${STRICHE}]*)$`, "iu"), "").trim();
}

/** Was vor Nummer und Strich steht ("RZ" in "RZ 03 - Titel") */
const KOPF = new RegExp(`^(\\S.{0,39}?)\\s*(?:${BANDWORT}\\s*)?\\d+[a-z]?\\s*[.)]?\\s*[${STRICHE}]\\s*\\S`, "iu");

/** Der Kopf, den die meisten Titel einer Sammlung vor ihrer Nummer tragen, etwa ein Kürzel der Reihe; ohne Mehrheit leer.
 *  Er bleibt erkennbar, wenn die Bandnummern nach dem Umstellen nicht mehr zu den Nummern im Titel passen. */
export function reihenkopf(titel: string[]): string {
  const zahl = new Map<string, { kopf: string; n: number }>();
  for (const t of titel) {
    const kopf = t.trim().match(KOPF)?.[1].trim();
    if (!kopf) continue;
    const schluessel = kopf.toLocaleLowerCase("de");
    const bisher = zahl.get(schluessel);
    zahl.set(schluessel, { kopf: bisher?.kopf ?? kopf, n: (bisher?.n ?? 0) + 1 });
  }
  const best = [...zahl.values()].sort((a, b) => b.n - a.n)[0];
  return best && best.n >= Math.max(2, Math.ceil(titel.length / 2)) ? best.kopf : "";
}

/** Der Titel ohne Reihennamen und Nummer, wie er auf dem Schild im Regal der Sammlung steht. namen: der Name der Sammlung
 *  und der Kopf ihrer Titel (reihenkopf); bliebe nichts, der ganze Titel. */
export function kurztitel(titel: string, namen: string[], band = ""): string {
  const ganz = titel.trim();
  let rest = ganz;
  for (const name of namen) rest = ohneName(rest, name) ?? rest;
  if (rest === ganz) rest = ohneKuerzel(ganz, band.trim()) ?? ganz;
  for (const name of namen) rest = ohneEnde(rest, name);
  return rest || ganz;
}

/** "Band 3"; ohne Nummer nichts */
export function bandText(band: string | number | null | undefined): string {
  const b = String(band ?? "").trim();
  return b ? `Band ${b}` : "";
}

/** Die Autoren, die häufigsten zuerst; gleich häufige in der Reihenfolge, in der sie zuerst vorkommen (sort ist stabil) */
export function autoren(buecher: Pick<Buch, "author">[]): string[] {
  const zahl = new Map<string, number>();
  for (const b of buecher) {
    const a = b.author?.trim();
    if (a) zahl.set(a, (zahl.get(a) ?? 0) + 1);
  }
  return [...zahl].sort((x, y) => y[1] - x[1]).map(([a]) => a);
}

/** Die Autoren einer Sammlung: "A", "A und B", "A, B und C", mehr als drei "A, B, C und weitere" */
export function autorenText(buecher: Pick<Buch, "author">[], hoechstens = 3): string {
  const namen = autoren(buecher);
  if (namen.length > hoechstens) return `${namen.slice(0, hoechstens).join(", ")} und weitere`;
  return namen.length > 1 ? `${namen.slice(0, -1).join(", ")} und ${namen.at(-1)}` : (namen[0] ?? "");
}
