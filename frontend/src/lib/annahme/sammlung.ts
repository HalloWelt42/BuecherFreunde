// Aufträge aus vielen Einträgen derselben Herkunft als ein Stand: Ordner einlesen, gemeinfreie Bücher holen. Die Annahme
// führt dafür keine eigene Liste; es sind ihre Einträge, nach Quelle zusammengefasst.
import type { AnnahmeEintrag, Annahmequelle } from "./typen";

/** Einzeln gezeigt (Aufnahmen, Aufträge im Kopf): was jemand hochlädt oder in den Eingangsordner legt */
export const EINZELN: readonly Annahmequelle[] = ["hochladen", "eingangsordner"];
export const EINLESEN: readonly Annahmequelle[] = ["ordner", "extern"];
export const GEMEINFREI: readonly Annahmequelle[] = ["gemeinfrei"];

const BEIM_SERVER = ["liest", "angaben", "regal"];
const IM_REGAL = ["wissen", "fertig", "ohne_text"];
const GESCHEITERT = ["fehler", "kaputt", "format"];

export type Sammellage = "wartet" | "laeuft" | "fertig" | "da" | "fehler";

export interface Sammelstand {
  /** Älteste zuerst, in der Reihenfolge der Arbeit */
  eintraege: AnnahmeEintrag[];
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

export const istErledigt = (lage: Sammellage | undefined): boolean => lage === "fertig" || lage === "da" || lage === "fehler";

export function sammle(alle: readonly AnnahmeEintrag[], quellen: readonly Annahmequelle[]): Sammelstand {
  const aktiv = inArbeit(alle);
  const eintraege = alle.filter((e) => gehoertZu(e, quellen)).sort((a, b) => a.id - b.id);
  const lagen = new Map(eintraege.map((e) => [e.id, lageVon(e, aktiv)]));
  const zahl = (lage: Sammellage) => [...lagen.values()].filter((l) => l === lage).length;
  const aktuell = eintraege.find((e) => e.id === aktiv) ?? null;
  const [imRegal, da, gescheitert, wartend] = [zahl("fertig"), zahl("da"), zahl("fehler"), zahl("wartet")];
  return { eintraege, lagen, gesamt: eintraege.length, erledigt: imRegal + da + gescheitert, imRegal, da, gescheitert, wartend, aktuell, laeuft: !!aktuell || wartend > 0 };
}

/** Was nicht mehr ansteht (zum Aufräumen) und was noch wartet (zum Anhalten) */
export const erledigte = (s: Sammelstand): AnnahmeEintrag[] => s.eintraege.filter((e) => istErledigt(s.lagen.get(e.id)));
export const wartende = (s: Sammelstand): AnnahmeEintrag[] => s.eintraege.filter((e) => s.lagen.get(e.id) === "wartet");
