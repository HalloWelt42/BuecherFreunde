// Familie (BF-78): Bilder der Bild-PIN, Rollen, Stufenvorschlag, Altersangaben, Einblick und Lesezeit in Worten.
// Nur Regeln der Oberfläche; was gilt, entscheidet der Server (stufen.json).
import { tagWort } from "./format";
import type { Buch } from "./typen";
import type {
  Einblickart, Einblickeintrag, Gestaltung, Kopfuhr, Leseschrift, Lesezeitregel, Lesezeitvorgabe, Profil, Profileinstellungen, Rolle, Schriftgroesse, Stufe,
  Stufenangabe, Zugang,
} from "./api/familie";

/**
 * Wie die Bilder der Bild-PIN aussehen und heißen. Welche es gibt und in welcher Folge, sagt der Server
 * (`zugang.bilder` in GET /api/familie/stufen); hier steht nur ihr Zeichen und ihr Name zum Vorlesen.
 */
const BILDZEICHEN: Record<string, [string, string]> = {
  apfel: ["apple-whole", "Apfel"],
  auto: ["car", "Auto"],
  ball: ["futbol", "Ball"],
  baum: ["tree", "Baum"],
  blume: ["spa", "Blume"],
  fisch: ["fish", "Fisch"],
  haus: ["house", "Haus"],
  herz: ["heart", "Herz"],
  katze: ["cat", "Katze"],
  mond: ["moon", "Mond"],
  sonne: ["sun", "Sonne"],
  stern: ["star", "Stern"],
  vogel: ["dove", "Vogel"],
  wolke: ["cloud", "Wolke"],
};

export const bildSymbol = (schluessel: string): string => BILDZEICHEN[schluessel]?.[0] ?? "circle-question";
export const bildName = (schluessel: string): string => BILDZEICHEN[schluessel]?.[1] ?? schluessel;

/** Solange GET /api/familie/stufen nicht geantwortet hat: PIN von 4 bis 8 Ziffern, drei Bilder, noch keine zur Wahl */
export const OHNE_ZUGANG: Zugang = { pin_stellen_von: 4, pin_stellen_bis: 8, bild_pin_anzahl: 3, bilder: [] };

export const pinGueltig = (pin: string, z: Zugang = OHNE_ZUGANG): boolean =>
  /^\d+$/.test(pin) && pin.length >= z.pin_stellen_von && pin.length <= z.pin_stellen_bis;

export const ROLLEN: [Rolle, string][] = [
  ["verwaltung", "Verwaltung"],
  ["erwachsen", "Erwachsen"],
  ["kind", "Kind"],
];

export const rollenName = (rolle: Rolle): string => ROLLEN.find(([r]) => r === rolle)?.[1] ?? rolle;

export function stufenName(stufe: Stufe | null | undefined, stufen: readonly Stufenangabe[]): string {
  return stufen.find((s) => s.schluessel === stufe)?.name ?? "";
}

/** "Verwaltung", "Erwachsen", "Kind, Lesen und Lernen" */
export function rollenText(p: Pick<Profil, "rolle" | "stufe">, stufen: readonly Stufenangabe[]): string {
  const stufe = p.rolle === "kind" ? stufenName(p.stufe, stufen) : "";
  return [rollenName(p.rolle), stufe].filter(Boolean).join(", ");
}

/** Wie sich das Profil ausweist */
export function pinText(p: Pick<Profil, "rolle" | "hat_pin" | "hat_bild_pin">): string {
  if (p.hat_bild_pin) return "Bild-PIN gesetzt";
  if (p.hat_pin) return "PIN gesetzt";
  return p.rolle === "kind" ? "ohne Bild-PIN" : "ohne PIN";
}

/** "Kind, geboren 2017, Bild-PIN gesetzt" */
export function profilZeile(p: Profil): string {
  return [rollenName(p.rolle), p.rolle === "kind" && p.geburtsjahr ? `geboren ${p.geburtsjahr}` : "", pinText(p)].filter(Boolean).join(", ");
}

const passt = (alter: number, von: number, bis: number | null): boolean => alter >= von && (bis === null || alter <= bis);

/** Vorschlag der Stufe aus dem Geburtsjahr; ohne Jahr oder ohne passende Stufe keiner */
export function stufeVorschlag(geburtsjahr: number | null | undefined, stufen: readonly Stufenangabe[], jahr = new Date().getFullYear()): Stufenangabe | null {
  if (!geburtsjahr) return null;
  const alter = jahr - geburtsjahr;
  return stufen.find((s) => passt(alter, s.alter_von, s.alter_bis)) ?? null;
}

/** Vorgabe der Lesezeit am Tag für das Alter aus dem Geburtsjahr */
export function lesezeitVorgabe(geburtsjahr: number | null | undefined, vorgaben: readonly Lesezeitvorgabe[], jahr = new Date().getFullYear()): Lesezeitvorgabe | null {
  if (!geburtsjahr) return null;
  const alter = jahr - geburtsjahr;
  return vorgaben.find((v) => passt(alter, v.alter_von, v.alter_bis)) ?? null;
}

/** Tempo des Vorlesens in Worten; das nächstgelegene zählt */
export const TEMPI: [number, string][] = [
  [0.8, "langsam"],
  [1, "normal"],
  [1.2, "schnell"],
];

export function tempoText(tempo: number): string {
  return [...TEMPI].sort((a, b) => Math.abs(a[0] - tempo) - Math.abs(b[0] - tempo))[0][1];
}

export const SCHRIFTEN: [Schriftgroesse, string][] = [
  ["klein", "klein"],
  ["mittel", "mittel"],
  ["gross", "groß"],
];

export const schriftText = (s: Schriftgroesse): string => SCHRIFTEN.find(([w]) => w === s)?.[1] ?? s;

export const minutenText = (n: number): string => `${n} ${n === 1 ? "Minute" : "Minuten"}`;

/** "6 bis 9 Jahre", "ab 14 Jahren" */
function alterSpanne(von: number, bis: number | null): string {
  return bis === null ? `ab ${von} Jahren` : `${von} bis ${bis} Jahre`;
}

/** "Vorgabe für 6 bis 8 Jahre: 45 Minuten", "Vorgabe ab 12 Jahren: ohne Grenze" */
export const vorgabeText = (v: Lesezeitvorgabe): string =>
  `Vorgabe ${v.alter_bis === null ? "" : "für "}${alterSpanne(v.alter_von, v.alter_bis)}: ${v.an ? minutenText(v.minuten) : "ohne Grenze"}`;

/** "07:30" wird "7:30" */
const uhrzeit = (wert: string): string => wert.replace(/^0(\d)/, "$1");

/** "45 Minuten" oder "ohne Grenze" */
export const tageszeitText = (r: Lesezeitregel): string => (r.an ? minutenText(r.minuten) : "ohne Grenze");

/** "19:30 bis 7:00" oder "aus" */
export const ruhezeitText = (r: Lesezeitregel): string => (r.ruhe_an && r.ruhe_von && r.ruhe_bis ? `${uhrzeit(r.ruhe_von)} bis ${uhrzeit(r.ruhe_bis)}` : "aus");

/** Altersangabe eines Buchs: "ab 6", "6 bis 9", "bis 9"; ohne Angabe leer */
export function alterText(b: Pick<Buch, "alter_von" | "alter_bis">): string {
  const von = b.alter_von ?? null;
  const bis = b.alter_bis ?? null;
  if (von !== null && bis !== null) return von === bis ? `${von} Jahre` : `${von} bis ${bis}`;
  if (von !== null) return `ab ${von}`;
  if (bis !== null) return `bis ${bis}`;
  return "";
}

/** Hinweis zur Altersangabe mit ihrer Herkunft */
export function alterHinweis(b: Pick<Buch, "alter_von" | "alter_bis" | "alter_quelle">): string {
  const text = alterText(b);
  if (!text) return "";
  return b.alter_quelle ? `Altersangabe ${text}, aus ${b.alter_quelle === "eigen" ? "eigener Angabe" : b.alter_quelle}` : `Altersangabe ${text}`;
}

/** Was die Eltern sehen, je im Satz nach "dass du ... siehst" und für sich */
const EINBLICK: Record<Einblickart, [string, string]> = {
  titel: ["Titel", "Titel"],
  lesezeit: ["Lesezeit", "Lesezeit"],
  fortschritt: ["Fortschritt", "Fortschritt"],
  grober_fortschritt: ["groben Fortschritt", "grober Fortschritt"],
  zuletzt: ["den letzten Lesetag", "der letzte Lesetag"],
  geteiltes: ["", ""],
};

/** "A", "A und B", "A, B und C" */
export function aufzaehlung(teile: string[]): string {
  if (teile.length < 2) return teile[0] ?? "";
  return `${teile.slice(0, -1).join(", ")} und ${teile[teile.length - 1]}`;
}

/** Was die Eltern sehen, in Worten; mit geteiltes nur von den Büchern, die das Kind teilt. fall 0: nach "dass du", 1: für sich */
function einblickWas(name: string, arten: readonly Einblickart[], fall: 0 | 1): { teile: string; nurGeteiltes: boolean } {
  const teile = aufzaehlung(arten.filter((a) => a !== "geteiltes").map((a) => EINBLICK[a]?.[fall] ?? a));
  const geteilt = arten.includes("geteiltes");
  return { teile: geteilt && teile ? `${teile} der Bücher, die ${name} teilt` : teile, nurGeteiltes: geteilt && !teile };
}

/** Der Hinweis, dass das Kind den Einblick sieht, und was sich mit der nächsten Stufe ändert */
export function einblickHinweis(name: string, sichtbar: readonly Einblickart[], stufe: Stufe | null, stufen: readonly Stufenangabe[]): string {
  const jetzt = einblickWas(name, sichtbar, 0);
  const satz = `${name} sieht im eigenen Bereich, dass du ${jetzt.nurGeteiltes ? `nur siehst, was ${name} teilt` : `${jetzt.teile} siehst`}.`;
  const hier = stufen.findIndex((s) => s.schluessel === stufe);
  const gleich = (a: readonly string[], b: readonly string[]) => a.length === b.length && a.every((x) => b.includes(x));
  const naechste = hier < 0 ? undefined : stufen.slice(hier + 1).find((s) => !gleich(s.einblick, sichtbar));
  if (!naechste) return satz;
  const dann = einblickWas(name, naechste.einblick, 1);
  const ab = alterSpanne(naechste.alter_von, null).replace(/^ab/, "Ab");
  return `${satz} ${ab} nur noch ${dann.nurGeteiltes ? `, was ${name} teilt` : dann.teile}.`.replace(" ,", ",");
}

/** "heute", "vor 3 Tagen", "am 02.11.2026" */
function wann(zeit: string | null | undefined): string {
  const wort = tagWort(zeit);
  return /^\d/.test(wort) ? `am ${wort}` : wort;
}

/** Zweite Zeile eines Eintrags im Einblick: "Seite 12 von 40", "50 Prozent" oder "gelesen gestern"; was die Stufe nicht zeigt, fehlt */
export function einblickZeile(e: Einblickeintrag): string {
  if (e.fortschritt === null) return e.zuletzt ? `zuletzt ${wann(e.zuletzt)}` : "";
  if (e.fortschritt >= 1) return ["gelesen", wann(e.zuletzt)].filter(Boolean).join(" ");
  return e.seite && e.seiten ? `Seite ${e.seite} von ${e.seiten}` : `${Math.round(e.fortschritt * 100)} Prozent`;
}

/** Gelesen ist, was die Stufe als ganz gelesen zeigt */
export const ganzGelesen = (e: Einblickeintrag): boolean => (e.fortschritt ?? 0) >= 1;

/** Leer, solange weder das Profil noch seine Stufe etwas vorgeben */
const OHNE: Profileinstellungen = {
  lesehilfen: { mitlesen: false, tempo: 1, silben: false, lesezeile: false, schrift: "mittel", schrift_wahl: "kinderschrift", hinweise_sprechen: false, tasten_ansagen: false },
  lesezeit: { an: false, minuten: 0, ruhe_an: false, ruhe_von: "", ruhe_bis: "", vorlesen_zaehlt: false },
  katze: { an: false, name: "", schnurren: false },
  gestaltung: "klein",
  uhr: "zeiger",
};

/** Der erste Wert, der angegeben ist; null zählt als Angabe */
const ersterGenannter = <T>(...werte: (T | undefined)[]): T => werte.find((w) => w !== undefined) as T;

/** Die Einstellungen eines Kindes: eigene vor den Vorgaben der Stufe */
export function einstellungenVon(p: Pick<Profil, "stufe" | "einstellungen">, stufen: readonly Stufenangabe[]): Profileinstellungen {
  const vorgabe = stufen.find((s) => s.schluessel === p.stufe)?.vorgaben ?? {};
  const eigen = p.einstellungen ?? {};
  return {
    lesehilfen: { ...OHNE.lesehilfen, ...vorgabe.lesehilfen, ...eigen.lesehilfen },
    lesezeit: { ...OHNE.lesezeit, ...vorgabe.lesezeit, ...eigen.lesezeit },
    katze: { ...OHNE.katze, ...vorgabe.katze, ...eigen.katze },
    gestaltung: ersterGenannter(eigen.gestaltung, vorgabe.gestaltung, OHNE.gestaltung),
    uhr: ersterGenannter(eigen.uhr, vorgabe.uhr, OHNE.uhr),
  };
}

export const GESTALTUNGEN: [Gestaltung, string][] = [
  ["klein", "Klein"],
  ["gross", "Groß"],
];

export const gestaltungText = (g: Gestaltung | null): string => GESTALTUNGEN.find(([w]) => w === g)?.[1] ?? "";

export const KOPFUHREN: [Kopfuhr, string][] = [
  ["zeiger", "Zeiger"],
  ["zahl", "Zahl"],
];

export const LESESCHRIFTEN: [Leseschrift, string][] = [
  ["normal", "Normal"],
  ["kinderschrift", "Kinderschrift"],
];

export const leseschriftText = (s: Leseschrift): string => LESESCHRIFTEN.find(([w]) => w === s)?.[1] ?? s;
