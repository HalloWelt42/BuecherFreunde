// Kategorien aus Importen (BF-69): alte Regale, die im Katalog aufgehen. Regeln und KI schlagen je Regal eine Kategorie vor
// oder ein Schlagwort am Buch; eine Zeile fasst die Regale mit demselben Ziel zusammen.
import { GRAUTON, farbeVon, findeKategorie } from "../../../lib/katalog";
import type { AltesRegal, Altziel, Katalog } from "../../../lib/typen";

export interface Altzeile {
  /** "k12" für Kategorie 12, "s" für Schlagwort, "?" ohne Ziel */
  schluessel: string;
  ziel: Altziel | null;
  alte: AltesRegal[];
  name: string;
  /** Bereich der Kategorie, beim Schlagwort der Grund */
  unter: string;
  zeichen: string;
  farbe: string;
}

/** Das Ziel eines alten Regals: eigene Wahl vor dem Vorschlag */
export function zielVon(alt: AltesRegal, gewaehlt: ReadonlyMap<number, Altziel>): Altziel | null {
  const eigen = gewaehlt.get(alt.id);
  if (eigen) return eigen;
  if (alt.vorschlag.art === "schlagwort") return { schlagwort: true };
  return alt.vorschlag.kategorie_id === null ? null : { kategorie_id: alt.vorschlag.kategorie_id };
}

export const zielSchluessel = (ziel: Altziel | null): string => (!ziel ? "?" : "schlagwort" in ziel ? "s" : `k${ziel.kategorie_id}`);

/** Zeilen in der Reihenfolge des Katalogs, Schlagworte und Regale ohne Ziel zuletzt */
export function altzeilen(alte: readonly AltesRegal[], katalog: Katalog | null, gewaehlt: ReadonlyMap<number, Altziel>): Altzeile[] {
  const zeilen = new Map<string, Altzeile>();
  for (const alt of alte) {
    const ziel = zielVon(alt, gewaehlt);
    const schluessel = zielSchluessel(ziel);
    const zeile = zeilen.get(schluessel) ?? { schluessel, ziel, alte: [], ...beschreibe(ziel, katalog, alt.vorschlag.grund) };
    zeile.alte.push(alt);
    zeilen.set(schluessel, zeile);
  }
  const stelle = (z: Altzeile) => {
    if (!z.ziel || "schlagwort" in z.ziel) return Number.MAX_SAFE_INTEGER - (z.ziel ? 1 : 0);
    const id = z.ziel.kategorie_id;
    const alle = (katalog?.bereiche ?? []).flatMap((b) => b.kategorien.map((k) => k.id));
    const n = alle.indexOf(id);
    return n < 0 ? Number.MAX_SAFE_INTEGER - 2 : n;
  };
  return [...zeilen.values()].sort((a, b) => stelle(a) - stelle(b));
}

function beschreibe(ziel: Altziel | null, katalog: Katalog | null, grund: string): Pick<Altzeile, "name" | "unter" | "zeichen" | "farbe"> {
  if (!ziel) return { name: "Noch ohne Ziel", unter: grund, zeichen: "circle-question", farbe: GRAUTON };
  if ("schlagwort" in ziel) return { name: "Schlagwort am Buch", unter: grund, zeichen: "tag", farbe: GRAUTON };
  const fund = findeKategorie(katalog, ziel.kategorie_id);
  if (!fund) return { name: "Kategorie fehlt", unter: grund, zeichen: "circle-question", farbe: GRAUTON };
  return { name: fund.kategorie.name, unter: fund.bereich.name, zeichen: fund.kategorie.zeichen, farbe: farbeVon(fund.kategorie, fund.bereich) };
}
