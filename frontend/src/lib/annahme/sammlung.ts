// Aufträge aus vielen Einträgen derselben Herkunft als ein Stand: Ordner einlesen, gemeinfreie Bücher holen. Die Annahme
// führt dafür keine eigene Liste; es sind ihre Einträge, nach Quelle zusammengefasst.
import type { AnnahmeEintrag, Annahmequelle, Quellenzahlen } from "./typen";

/** Einzeln gezeigt (Aufnahmen, Aufträge im Kopf): was jemand hochlädt oder in den Eingangsordner legt */
export const EINZELN: readonly Annahmequelle[] = ["hochladen", "eingangsordner"];
export const EINLESEN: readonly Annahmequelle[] = ["ordner", "extern"];
export const GEMEINFREI: readonly Annahmequelle[] = ["gemeinfrei"];

const BEIM_SERVER = ["liest", "angaben", "regal"];
const IM_REGAL = ["wissen", "fertig", "ohne_text"];
const GESCHEITERT = ["fehler", "kaputt", "format"];
/** Was nicht mehr ansteht: zum Aufräumen am Server (DELETE /api/annahme nach Quelle und Stand) */
export const ERLEDIGT = [...IM_REGAL, "da", ...GESCHEITERT];
/** Was aus einem Ordner oder als gemeinfreies Buch noch auf die Annahme wartet; der laufende bleibt beim Server dabei */
export const WARTEND = ["liest"];

export type Sammellage = "wartet" | "laeuft" | "fertig" | "da" | "fehler";

export interface Sammelstand {
  /** Älteste zuerst, in der Reihenfolge der Arbeit; nur die gelieferten (die neuesten 300 aller Quellen) */
  eintraege: AnnahmeEintrag[];
  /** Einträge, die nicht geliefert sind, aber mitzählen */
  weitere: number;
  lagen: ReadonlyMap<number, Sammellage>;
  gesamt: number;
  /** Im Regal, schon da oder gescheitert */
  erledigt: number;
  imRegal: number;
  da: number;
  gescheitert: number;
  wartend: number;
  /** Was die Annahme gerade bearbeitet, wenn es hierher gehört */
  aktuell: AnnahmeEintrag | null;
  laeuft: boolean;
}

export const gehoertZu = (e: AnnahmeEintrag, quellen: readonly Annahmequelle[]): boolean => quellen.includes(e.quelle ?? "hochladen");

/** Die Annahme arbeitet einen Eintrag nach dem anderen ab, nach Nummer (annahme/dienst.py): der kleinste beim Server läuft */
export function inArbeit(alle: readonly AnnahmeEintrag[]): number | null {
  let nr: number | null = null;
  for (const e of alle) if (BEIM_SERVER.includes(e.stand) && (nr === null || e.id < nr)) nr = e.id;
  return nr;
}

export function lageVon(e: AnnahmeEintrag, aktiv: number | null): Sammellage {
  if (BEIM_SERVER.includes(e.stand)) return e.id === aktiv ? "laeuft" : "wartet";
  if (IM_REGAL.includes(e.stand)) return "fertig";
  if (e.stand === "da") return "da";
  if (GESCHEITERT.includes(e.stand)) return "fehler";
  return "wartet";
}

/**
 * Ein Auftrag aus den Einträgen der Quellen. Mit den Zahlen des Servers je Quelle zählt er alle Einträge, auch die über die
 * gelieferten hinaus; ohne sie nur die gelieferten.
 */
export function sammle(alle: readonly AnnahmeEintrag[], quellen: readonly Annahmequelle[], zahlen?: Partial<Record<Annahmequelle, Quellenzahlen>>): Sammelstand {
  const aktiv = inArbeit(alle);
  const eintraege = alle.filter((e) => gehoertZu(e, quellen)).sort((a, b) => a.id - b.id);
  const lagen = new Map(eintraege.map((e) => [e.id, lageVon(e, aktiv)]));
  const aktuell = eintraege.find((e) => e.id === aktiv) ?? null;
  const zahl = (lage: Sammellage) => [...lagen.values()].filter((l) => l === lage).length;
  const vomServer = zahlen && quellen.some((q) => zahlen[q]);
  const summe = (feld: keyof Quellenzahlen) => quellen.reduce((s, q) => s + (zahlen?.[q]?.[feld] ?? 0), 0);
  const gesamt = vomServer ? summe("gesamt") : eintraege.length;
  const [imRegal, da, gescheitert] = vomServer ? [summe("fertig"), summe("da"), summe("gescheitert")] : [zahl("fertig"), zahl("da"), zahl("fehler")];
  const wartend = vomServer ? Math.max(0, summe("laeuft") - (aktuell ? 1 : 0)) : zahl("wartet");
  return { eintraege, weitere: Math.max(0, gesamt - eintraege.length), lagen, gesamt, erledigt: imRegal + da + gescheitert, imRegal, da, gescheitert, wartend, aktuell, laeuft: !!aktuell || wartend > 0 };
}

