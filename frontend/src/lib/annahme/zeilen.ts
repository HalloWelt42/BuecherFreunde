// Aus Einträgen des Servers und laufenden Hochladungen eine Liste für die Ansicht; was in einer offenen Vorschau auf die
// Bestätigung wartet, steht als eine Zeile für die ganze Vorschau (BF-80)
import { anzahl, groesse as alsGroesse, seitWann } from "../format";
import type { AnnahmeEintrag, Hochladung, Vorschaukurz } from "./typen";

export type Gruppe = "bestaetigen" | "laeuft" | "klaeren" | "da" | "fertig";
export type Ton = "info" | "warn" | "schlecht" | "gut";
export type Handlung = "anhalten" | "weiter" | "jetzt" | "waehlen" | "erneut" | "buch" | "entfernen" | "ansehen";
export type Station = "fertig" | "jetzt" | "wartet" | "halt" | "offen";

export interface Annahmezeile {
  schluessel: string;
  id: number | null;
  hochladung: string | null;
  /** Die Vorschau, für die diese Zeile steht (Gruppe "bestaetigen") */
  vorschau: string | null;
  name: string;
  groesse: string;
  gruppe: Gruppe;
  symbol: string;
  ton: Ton;
  wort: string;
  text: string;
  stationen: Station[];
  /** Füllstand der laufenden Station in Prozent */
  prozent: number;
  buch: number | null;
  handlungen: Handlung[];
}

/** Die Stationen einer Aufnahme beim Namen; die letzte gibt es nur mit der Suche nach Bedeutung. */
export function stationsnamen(a: { ablage: "kellerwolke" | "geraet"; bedeutung: boolean }): string[] {
  return ["Prüfen", a.ablage === "kellerwolke" ? "Wolke" : "Ablage", "Lesen", "Angaben", "Regal", ...(a.bedeutung ? ["Wissen"] : [])];
}

/** Geht es von selbst voran, oder wartet die Zeile auf jemanden? */
export function laeuftVonSelbst(z: Annahmezeile): boolean {
  return z.gruppe === "laeuft" && !z.handlungen.some((h) => h === "waehlen" || h === "weiter");
}

interface Lage {
  gruppe: Gruppe;
  symbol: string;
  ton: Ton;
  wort: string;
  handlungen: Handlung[];
}

const LAGEN: Record<string, Lage> = {
  neu: { gruppe: "laeuft", symbol: "plus", ton: "info", wort: "Neu", handlungen: [] },
  wartet: { gruppe: "laeuft", symbol: "hourglass-half", ton: "info", wort: "Wartet", handlungen: [] },
  laeuft: { gruppe: "laeuft", symbol: "circle-notch", ton: "info", wort: "Läuft", handlungen: [] },
  angehalten: { gruppe: "laeuft", symbol: "circle-pause", ton: "warn", wort: "Pause", handlungen: ["waehlen", "entfernen"] },
  bestaetigen: { gruppe: "bestaetigen", symbol: "list-check", ton: "info", wort: "Zum Bestätigen", handlungen: [] },
  wissen: { gruppe: "fertig", symbol: "moon", ton: "info", wort: "Wartet auf Bedeutung", handlungen: ["buch"] },
  fertig: { gruppe: "fertig", symbol: "circle-check", ton: "gut", wort: "Fertig", handlungen: ["buch"] },
  ohne_text: { gruppe: "klaeren", symbol: "image", ton: "warn", wort: "Ohne Text", handlungen: ["buch"] },
  da: { gruppe: "da", symbol: "clone", ton: "info", wort: "Schon da", handlungen: ["buch"] },
  entpackt: { gruppe: "fertig", symbol: "file-zipper", ton: "info", wort: "Ausgepackt", handlungen: [] },
  verworfen: { gruppe: "fertig", symbol: "trash", ton: "info", wort: "Verworfen", handlungen: [] },
  format: { gruppe: "klaeren", symbol: "ban", ton: "schlecht", wort: "Nicht möglich", handlungen: ["entfernen"] },
  kaputt: { gruppe: "klaeren", symbol: "file-circle-xmark", ton: "schlecht", wort: "Nicht möglich", handlungen: ["entfernen"] },
  fehler: { gruppe: "klaeren", symbol: "triangle-exclamation", ton: "schlecht", wort: "Gescheitert", handlungen: ["erneut", "entfernen"] },
};

const AM_SERVER = ["liest", "angaben", "entpacken", "regal"];
const OHNE_STATIONEN = ["da", "format", "kaputt", "entpackt", "verworfen"];
/** Läuft noch, auch wenn es zu einer Vorschau gehört; alles andere einer offenen Vorschau steht in ihrer Zeile */
const NOCH_UNTERWEGS = ["wartet", "laedt", "angehalten", "liest", "angaben", "entpacken"];

/** Zeichen, Ton und Wort zu einem Stand vom Server; "neu" heißt: gefunden, aber noch nicht aufgenommen. */
export function lageFuer(stand: string): Lage {
  return AM_SERVER.includes(stand) || stand === "laedt" ? LAGEN.laeuft : (LAGEN[stand] ?? LAGEN.fehler);
}

function stationen(schritt: number, jetzt: Station): Station[] {
  return Array.from({ length: 6 }, (_, n) => (n < schritt ? "fertig" : n === schritt ? jetzt : "offen"));
}

function vomServer(e: AnnahmeEintrag): Annahmezeile {
  // Der Server nimmt Teile an, dieser Browser schickt aber keine: hier fehlt die Datei
  const verwaist = e.stand === "laedt" || e.stand === "angehalten" || (e.stand === "wartet" && e.empfangen < e.groesse);
  const lage = verwaist ? LAGEN.angehalten : lageFuer(e.stand);
  const jetzt: Station = ["wissen", "ohne_text", "bestaetigen"].includes(e.stand) ? "wartet" : e.stand === "fehler" ? "halt" : "jetzt";
  const prozent = Math.round((verwaist && e.groesse ? e.empfangen / e.groesse : e.anteil) * 100);
  return {
    ...lage,
    schluessel: `eintrag-${e.id}`,
    id: e.id,
    hochladung: null,
    vorschau: null,
    name: e.name,
    groesse: alsGroesse(e.groesse),
    text: verwaist ? `${alsGroesse(e.empfangen)} von ${alsGroesse(e.groesse)} liegen schon da. Datei noch einmal wählen, dann geht es dort weiter.` : e.text,
    stationen: OHNE_STATIONEN.includes(e.stand) ? [] : stationen(e.schritt, jetzt),
    prozent,
    buch: e.buch_id,
    handlungen: lage.handlungen.filter((h) => h !== "buch" || e.buch_id !== null),
  };
}

function vomBrowser(h: Hochladung): Annahmezeile {
  const grund: Pick<Annahmezeile, "schluessel" | "id" | "hochladung" | "vorschau" | "name" | "groesse" | "buch"> = {
    schluessel: h.schluessel, id: h.eintrag?.id ?? null, hochladung: h.schluessel, vorschau: null, name: h.name, groesse: alsGroesse(h.groesse), buch: null,
  };
  const prozent = Math.round(h.anteil * 100);
  const schritt = h.eintrag ? 1 : 0;
  if (h.lage === "fehler") return { ...grund, ...LAGEN.fehler, text: h.text, stationen: stationen(schritt, "halt"), prozent, handlungen: ["weiter", "entfernen"] };
  if (h.lage === "ohne_verbindung") return { ...grund, gruppe: "laeuft", symbol: "plug-circle-xmark", ton: "warn", wort: "Wartet auf Verbindung", text: h.text, stationen: stationen(schritt, "jetzt"), prozent, handlungen: ["jetzt", "entfernen"] };
  if (h.lage === "angehalten") return { ...grund, ...LAGEN.angehalten, text: `${h.text}, ${prozent} %`, stationen: stationen(schritt, "jetzt"), prozent, handlungen: ["weiter", "entfernen"] };
  const text = h.lage === "laedt" ? `${h.text}, ${alsGroesse(h.gesendet)} von ${alsGroesse(h.groesse)}` : h.text;
  const lage = h.lage === "ansteht" ? LAGEN.wartet : LAGEN.laeuft;
  return { ...grund, ...lage, text, stationen: stationen(schritt, h.lage === "ansteht" ? "wartet" : "jetzt"), prozent, handlungen: ["anhalten"] };
}

/** Eine offene Vorschau als eine Zeile: wartet vor dem Regal, bis jemand übernimmt oder verwirft */
export function vorschauzeile(v: Vorschaukurz, jetzt = new Date()): Annahmezeile {
  const teile = [anzahl(v.dateien, "Datei", "Dateien"), v.laeuft ? `${v.laeuft} ${v.laeuft === 1 ? "läuft" : "laufen"} noch` : "", seitWann(v.angelegt_am, jetzt)];
  return {
    ...LAGEN.bestaetigen,
    schluessel: `vorschau-${v.id}`, id: null, hochladung: null, vorschau: v.id, name: v.name, groesse: alsGroesse(v.groesse),
    text: teile.filter(Boolean).join(", "), stationen: stationen(4, "wartet"), prozent: 0, buch: null, handlungen: ["ansehen"],
  };
}

/** Gehört der Eintrag in die Zeile einer offenen Vorschau? Was noch hochgeladen, gelesen oder ausgepackt wird, läuft für sich. */
export const inVorschau = (e: AnnahmeEintrag, offen: ReadonlySet<string>): boolean => !!e.vorschau && offen.has(e.vorschau) && !NOCH_UNTERWEGS.includes(e.stand);

/**
 * Offene Vorschauen zuerst, dann was dieser Browser bearbeitet, dann der Rest in der Reihenfolge des Servers (neueste zuerst).
 * Was zu einer offenen Vorschau gehört und nicht mehr läuft, steht nur in ihrer Zeile.
 */
export function fuegeZusammen(eintraege: AnnahmeEintrag[], hochladungen: Hochladung[], vorschauen: readonly Vorschaukurz[] = []): Annahmezeile[] {
  const offen = new Set(vorschauen.map((v) => v.id));
  const eigene = hochladungen.filter((h) => h.lage !== "beim_server");
  const ueberdeckt = new Set(eigene.map((h) => h.eintrag?.id).filter((id) => id !== undefined));
  const uebrige = eintraege.filter((e) => !ueberdeckt.has(e.id) && !inVorschau(e, offen));
  return [...vorschauen.map((v) => vorschauzeile(v)), ...eigene.map(vomBrowser), ...uebrige.map(vomServer)];
}
