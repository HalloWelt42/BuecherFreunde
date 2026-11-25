// Glas rollt nie selbst (stil/glas.css): keine Glasscheibe ist zugleich Rollfläche, weder im Markup noch im Stil
// Die Quellen als Text, über den Bau selbst gelesen
const svelte = Object.entries(import.meta.glob<string>("../src/**/*.svelte", { query: "?raw", import: "default", eager: true }));
const css = Object.entries(import.meta.glob<string>("../src/stil/*.css", { query: "?raw", import: "default", eager: true }));
const STUFEN = new Set(["glas", "klar", "milch", "dicht"]);

/** Klassen, die zusammen mit "glas" an einem Element stehen; nur: in dieser Datei (Stil einer Komponente gilt nur dort) */
function glasklassen(nur?: string): Map<string, string> {
  const aus = new Map<string, string>();
  for (const [p, t] of svelte) {
    if (nur && p !== nur) continue;
    for (const m of t.matchAll(/class="([^"]*)"/g)) {
      const k = m[1].split(/\s+/).filter((x: string) => x && !x.includes("{"));
      if (k.includes("glas")) for (const x of k) if (!STUFEN.has(x)) aus.set(x, p);
    }
  }
  return aus;
}

function stilregeln(): { wo: string; auswahl: string; inhalt: string }[] {
  const texte = [...css, ...svelte.map(([p, t]) => [p, t.match(/<style[^>]*>([\s\S]*?)<\/style>/)?.[1] ?? ""] as const)];
  const aus: { wo: string; auswahl: string; inhalt: string }[] = [];
  for (const [wo, t] of texte) {
    const ohne = t.replace(/\/\*[\s\S]*?\*\//g, "");
    for (const m of ohne.matchAll(/([^{}]+)\{([^{}]*)\}/g)) aus.push({ wo, auswahl: m[1].trim(), inhalt: m[2] });
  }
  return aus;
}

describe("Glas", () => {
  it("rollt nie selbst: keine Scheibe trägt zugleich .rollen", () => {
    const beides = svelte.flatMap(([p, t]) => [...t.matchAll(/class="([^"]*)"/g)].filter((m) => /\bglas\b/.test(m[1]) && /\brollen\b/.test(m[1])).map((m) => `${p}: ${m[1]}`));
    expect(beides).toEqual([]);
  });

  it("keine Glasfläche hat im Stil eine eigene Rollfläche", () => {
    const alle = glasklassen();
    expect(alle.size).toBeGreaterThan(10);
    const falsch: string[] = [];
    for (const r of stilregeln()) {
      const glas = r.wo.endsWith(".svelte") ? glasklassen(r.wo) : alle;
      if (!/overflow(-y|-x)?\s*:\s*(auto|scroll)/.test(r.inhalt)) continue;
      for (const auswahl of r.auswahl.split(",")) {
        // Nur das Element selbst zählt, nicht was in ihm liegt
        const letzte = auswahl.trim().split(/\s+|>|\+|~/).filter(Boolean).at(-1) ?? "";
        const klassen = [...letzte.matchAll(/\.([\w-]+)/g)].map((m) => m[1]);
        const treffer = klassen.find((k) => glas.has(k));
        if (treffer) falsch.push(`${r.wo}: ${auswahl.trim()} (Glas in ${glas.get(treffer)})`);
      }
    }
    expect(falsch).toEqual([]);
  });
});
