// Reiter der Einstellungen. Alte Adressen führen zum neuen Reiter und rollen dort an ihre Stelle. Welche ein Profil sieht,
// folgt seinen Fähigkeiten (BF-78): Familie für Verwaltung und Eltern, alles andere nur mit "einstellungen".
import type { Faehigkeit } from "../../lib/api/familie";

export type Reiter = "darstellung" | "familie" | "verbindungen" | "regale" | "katalog" | "wartung" | "mehr";

export const reiter: [Reiter, string, string][] = [
  ["darstellung", "Darstellung", "palette"],
  ["familie", "Familie", "people-roof"],
  ["verbindungen", "Verbindungen", "plug"],
  ["regale", "Regale und Sammlungen", "folder-tree"],
  ["katalog", "Katalog", "sitemap"],
  ["wartung", "Wartung und Sicherung", "screwdriver-wrench"],
  ["mehr", "KI, Rechtliches, Über", "circle-info"],
];

/** alter letzter Teil der Adresse -> Reiter und Stelle darin */
const ALT: Record<string, [Reiter, string]> = {
  categories: ["regale", "regale"],
  sammlungen: ["regale", "sammlungen"],
  system: ["wartung", ""],
  ai: ["mehr", "ki"],
  legal: ["mehr", "rechtliches"],
};

/** Ein Reiter erscheint, wenn das Profil eine dieser Fähigkeiten hat */
const BRAUCHT: Record<Reiter, Faehigkeit[]> = {
  darstellung: ["einstellungen"],
  familie: ["profile", "freigeben"],
  verbindungen: ["einstellungen"],
  regale: ["einstellungen"],
  katalog: ["einstellungen"],
  wartung: ["einstellungen"],
  mehr: ["einstellungen"],
};

export function sichtbareReiter(darf: (f: Faehigkeit) => boolean): [Reiter, string, string][] {
  return reiter.filter(([r]) => BRAUCHT[r].some(darf));
}

/** Reiter und Stelle aus der Adresse; ein Reiter, den das Profil nicht sieht, führt zum ersten, den es sieht */
export function reiterAus(pfad: string, erlaubt: readonly Reiter[] = reiter.map(([r]) => r)): { reiter: Reiter; stelle: string } {
  const teil = pfad.replace(/^\/settings\/?/, "").split("/")[0];
  const vorn = erlaubt[0] ?? "darstellung";
  if (ALT[teil]) return erlaubt.includes(ALT[teil][0]) ? { reiter: ALT[teil][0], stelle: ALT[teil][1] } : { reiter: vorn, stelle: "" };
  const bekannt = erlaubt.find((r) => r === teil);
  return { reiter: bekannt ?? vorn, stelle: "" };
}
