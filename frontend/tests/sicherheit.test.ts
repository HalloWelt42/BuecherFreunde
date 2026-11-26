// BF-5: Bücher sind fremder Inhalt. Die Richtlinie steht an einer Stelle (docker/sicherheit.conf) und darf nie so weich
// werden, dass ein Skript aus einem Buch läuft; nginx bindet sie in jedem Ort ein, der eigene Köpfe setzt.
// Die Dateien als Text, über den Bau selbst gelesen
const dateien = import.meta.glob<string>(["../../docker/sicherheit.conf", "../../docker/nginx.conf", "../Dockerfile"], { query: "?raw", import: "default", eager: true });
const datei = (name: string): string => Object.entries(dateien).find(([p]) => p.endsWith(name))?.[1] ?? "";
const richtlinie = datei("sicherheit.conf").match(/add_header Content-Security-Policy "([^"]+)" always;/)?.[1] ?? "";
const direktiven = new Map<string, string[]>(
  richtlinie.split(";").map((d: string) => d.trim().split(/\s+/)).filter((t: string[]) => t[0]).map(([n, ...w]: string[]) => [n, w] as [string, string[]]),
);

describe("Content-Security-Policy", () => {
  it("lässt nur Skripte der App zu: kein Inline, kein eval, kein blob:", () => {
    expect(direktiven.get("default-src")).toEqual(["'none'"]);
    expect(direktiven.get("script-src")).toEqual(["'self'", "'wasm-unsafe-eval'"]);
    expect(richtlinie).not.toMatch(/'unsafe-eval'|script-src[^;]*'unsafe-inline'|script-src[^;]*blob:/);
  });

  it("Kapitel nur als blob:-Rahmen, keine Einbettungen, nichts von fremden Adressen", () => {
    expect(direktiven.get("frame-src")).toEqual(["blob:"]);
    expect(direktiven.get("object-src")).toEqual(["'none'"]);
    expect(direktiven.get("frame-ancestors")).toEqual(["'none'"]);
    for (const [name, werte] of direktiven) for (const w of werte) expect(`${name} ${w}`).toMatch(/'[a-z-]+'|blob:$|data:$/);
  });

  it("gilt in jedem Ort von nginx, der eigene Köpfe setzt (add_header im Ort hebt die des Servers auf)", () => {
    const nginx = datei("nginx.conf");
    expect(nginx).toMatch(/^ {4}include \/etc\/nginx\/snippets\/sicherheit\.conf;/m);
    const orte = [...nginx.matchAll(/location [^{]+\{([^}]*)\}/g)].map((m) => m[1]);
    expect(orte.length).toBeGreaterThan(2);
    for (const ort of orte) if (/add_header/.test(ort)) expect(ort).toContain("include /etc/nginx/snippets/sicherheit.conf;");
    expect(datei("Dockerfile")).toContain("COPY docker/sicherheit.conf /etc/nginx/snippets/sicherheit.conf");
  });
});
