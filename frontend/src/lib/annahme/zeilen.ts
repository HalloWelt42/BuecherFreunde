// Aus Einträgen des Servers und laufenden Hochladungen eine Liste für die Ansicht
import { groesse as alsGroesse } from "../format";
import type { AnnahmeEintrag, Hochladung } from "./typen";

export type Gruppe = "laeuft" | "klaeren" | "da" | "fertig";
export type Ton = "info" | "warn" | "schlecht" | "gut";
export type Handlung = "anhalten" | "weiter" | "jetzt" | "waehlen" | "erneut" | "buch" | "entfernen";
export type Station = "fertig" | "jetzt" | "wartet" | "halt" | "offen";

export interface Annahmezeile {
  schluessel: string;
  id: number | null;
  hochladung: string | null;
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

interface Lage {
  gruppe: Gruppe;
  symbol: string;
  ton: Ton;
  wort: string;
  handlungen: Handlung[];
}

const LAGEN: Record<string, Lage> = {
  wartet: { gruppe: "laeuft", symbol: "hourglass-half", ton: "info", wort: "Wartet", handlungen: [] },
  laeuft: { gruppe: "laeuft", symbol: "circle-notch", ton: "info", wort: "Läuft", handlungen: [] },
  angehalten: { gruppe: "laeuft", symbol: "circle-pause", ton: "warn", wort: "Angehalten", handlungen: ["waehlen", "entfernen"] },
  wissen: { gruppe: "fertig", symbol: "moon", ton: "info", wort: "Wartet auf Bedeutung", handlungen: ["buch"] },
  fertig: { gruppe: "fertig", symbol: "circle-check", ton: "gut", wort: "Fertig", handlungen: ["buch"] },
  ohne_text: { gruppe: "klaeren", symbol: "image", ton: "warn", wort: "Ohne Text", handlungen: ["buch"] },
  da: { gruppe: "da", symbol: "clone", ton: "info", wort: "Schon da", handlungen: ["buch"] },
  format: { gruppe: "klaeren", symbol: "ban", ton: "schlecht", wort: "Nicht möglich", handlungen: ["entfernen"] },
  kaputt: { gruppe: "klaeren", symbol: "file-circle-xmark", ton: "schlecht", wort: "Nicht möglich", handlungen: ["entfernen"] },
  fehler: { gruppe: "klaeren", symbol: "triangle-exclamation", ton: "schlecht", wort: "Gescheitert", handlungen: ["erneut", "entfernen"] },
};

const AM_SERVER = ["liest", "angaben", "regal"];
const OHNE_STATIONEN = ["da", "format", "kaputt"];

function lageFuer(stand: string): Lage {
  return AM_SERVER.includes(stand) || stand === "laedt" ? LAGEN.laeuft : (LAGEN[stand] ?? LAGEN.fehler);
}

function stationen(schritt: number, jetzt: Station): Station[] {
  return Array.from({ length: 6 }, (_, n) => (n < schritt ? "fertig" : n === schritt ? jetzt : "offen"));
}

function vomServer(e: AnnahmeEintrag): Annahmezeile {
  // Der Server nimmt Teile an, dieser Browser schickt aber keine: hier fehlt die Datei
  const verwaist = e.stand === "laedt" || e.stand === "angehalten" || (e.stand === "wartet" && e.empfangen < e.groesse);
  const lage = verwaist ? LAGEN.angehalten : lageFuer(e.stand);
  const jetzt: Station = ["wissen", "ohne_text"].includes(e.stand) ? "wartet" : e.stand === "fehler" ? "halt" : "jetzt";
  const prozent = Math.round((verwaist && e.groesse ? e.empfangen / e.groesse : e.anteil) * 100);
  return {
    ...lage,
    schluessel: `eintrag-${e.id}`,
    id: e.id,
    hochladung: null,
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
  const grund: Pick<Annahmezeile, "schluessel" | "id" | "hochladung" | "name" | "groesse" | "buch"> = {
    schluessel: h.schluessel, id: h.eintrag?.id ?? null, hochladung: h.schluessel, name: h.name, groesse: alsGroesse(h.groesse), buch: null,
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

/** Was dieser Browser bearbeitet, steht oben; der Rest folgt in der Reihenfolge des Servers (neueste zuerst). */
export function fuegeZusammen(eintraege: AnnahmeEintrag[], hochladungen: Hochladung[]): Annahmezeile[] {
  const eigene = hochladungen.filter((h) => h.lage !== "beim_server");
  const ueberdeckt = new Set(eigene.map((h) => h.eintrag?.id).filter((id) => id !== undefined));
  return [...eigene.map(vomBrowser), ...eintraege.filter((e) => !ueberdeckt.has(e.id)).map(vomServer)];
}
