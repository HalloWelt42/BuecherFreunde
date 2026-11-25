// Reiter der Einstellungen. Alte Adressen führen zum neuen Reiter und rollen dort an ihre Stelle.

export type Reiter = "darstellung" | "verbindungen" | "regale" | "wartung" | "mehr";

export const reiter: [Reiter, string, string][] = [
  ["darstellung", "Darstellung", "palette"],
  ["verbindungen", "Verbindungen", "plug"],
  ["regale", "Regale und Sammlungen", "folder-tree"],
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

export function reiterAus(pfad: string): { reiter: Reiter; stelle: string } {
  const teil = pfad.replace(/^\/settings\/?/, "").split("/")[0];
  if (ALT[teil]) return { reiter: ALT[teil][0], stelle: ALT[teil][1] };
  const bekannt = reiter.find(([r]) => r === teil)?.[0];
  return { reiter: bekannt ?? "darstellung", stelle: "" };
}
