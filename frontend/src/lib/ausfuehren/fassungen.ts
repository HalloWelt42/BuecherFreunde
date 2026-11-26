// Fassungen einer Sprache (PHP) wie in Nachschlag: welche Fassung der Sandbox zu einem Wunsch passt, und je Fassung der
// Bestand an Funktionen für den Editor (was es dort nicht gibt, wird markiert und sagt, wo es das gibt).
import type { Funktionsbestand } from "appkern-oberflaeche/code";

/** Zahlen einer Fassung zum Vergleichen: "8.3" -> [8, 3] */
function zahlen(fassung: string): number[] {
  return fassung.split(".").map((t) => Number.parseInt(t, 10) || 0);
}

export function vergleich(a: string, b: string): number {
  const x = zahlen(a);
  const y = zahlen(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) if ((x[i] ?? 0) !== (y[i] ?? 0)) return (x[i] ?? 0) - (y[i] ?? 0);
  return 0;
}

/** Die Fassung der Sandbox zu einem Wunsch: genau sie, sonst die neueste ihrer Reihe ("8" -> 8.5), sonst die nächstältere,
 *  sonst die älteste; ohne Wunsch die neueste. `fassungen` neueste zuerst; ohne Wahl leer. */
export function passendeFassung(fassungen: readonly string[], wunsch: string): string {
  if (!fassungen.length) return "";
  if (!wunsch) return fassungen[0];
  return fassungen.find((f) => f === wunsch || f.startsWith(`${wunsch}.`)) ?? fassungen.find((f) => vergleich(f, wunsch) <= 0) ?? fassungen[fassungen.length - 1];
}

/** Bestand einer Fassung für den Editor; was keine Fassung kennt (Erweiterungen), bleibt unmarkiert */
export function bestandFuer(produkt: string, fassung: string, alle: Record<string, string[]>): Funktionsbestand | null {
  const eigene = alle[fassung];
  if (!eigene) return null;
  const mengen = Object.entries(alle).map(([f, namen]) => [f, new Set(namen)] as const);
  const hier = new Set(eigene);
  return {
    funktionen: eigene,
    pruefe: (name) => {
      if (hier.has(name)) return null;
      const mit = mengen.filter(([, m]) => m.has(name)).map(([f]) => f).sort(vergleich);
      if (!mit.length) return null;
      const aelter = mit.filter((f) => vergleich(f, fassung) < 0);
      const neuer = mit.filter((f) => vergleich(f, fassung) > 0);
      if (!aelter.length) return `${name}() gibt es erst ab ${produkt} ${neuer[0]}, gewählt ist ${produkt} ${fassung}`;
      if (!neuer.length) return `${name}() gibt es nur bis ${produkt} ${aelter[aelter.length - 1]}, gewählt ist ${produkt} ${fassung}`;
      return `${name}() gibt es in ${produkt} ${fassung} nicht, wohl aber in ${mit.map((f) => `${produkt} ${f}`).join(", ")}`;
    },
  };
}
