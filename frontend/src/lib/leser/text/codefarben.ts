// Codeblöcke einfärben und zum Kopieren anbieten; die Sprachen kommen einzeln, wenn ein Block sie braucht
import type { LanguageFn } from "highlight.js";

const SPRACHEN: Record<string, () => Promise<{ default: LanguageFn }>> = {
  javascript: () => import("highlight.js/lib/languages/javascript"), typescript: () => import("highlight.js/lib/languages/typescript"),
  python: () => import("highlight.js/lib/languages/python"), bash: () => import("highlight.js/lib/languages/bash"),
  shell: () => import("highlight.js/lib/languages/shell"), json: () => import("highlight.js/lib/languages/json"),
  xml: () => import("highlight.js/lib/languages/xml"), css: () => import("highlight.js/lib/languages/css"),
  sql: () => import("highlight.js/lib/languages/sql"), java: () => import("highlight.js/lib/languages/java"),
  c: () => import("highlight.js/lib/languages/c"), cpp: () => import("highlight.js/lib/languages/cpp"),
  csharp: () => import("highlight.js/lib/languages/csharp"), go: () => import("highlight.js/lib/languages/go"),
  rust: () => import("highlight.js/lib/languages/rust"), ruby: () => import("highlight.js/lib/languages/ruby"),
  php: () => import("highlight.js/lib/languages/php"), yaml: () => import("highlight.js/lib/languages/yaml"),
  markdown: () => import("highlight.js/lib/languages/markdown"), dockerfile: () => import("highlight.js/lib/languages/dockerfile"),
  ini: () => import("highlight.js/lib/languages/ini"), diff: () => import("highlight.js/lib/languages/diff"),
  plaintext: () => import("highlight.js/lib/languages/plaintext"),
};
const ANDERS: Record<string, string> = { js: "javascript", ts: "typescript", py: "python", sh: "bash", yml: "yaml", html: "xml" };
const UEBLICH = ["javascript", "python", "bash", "json", "xml", "css", "sql"];

function spracheVon(block: Element): string {
  const klasse = [...block.classList].find((c) => c.startsWith("language-"))?.slice(9) ?? "";
  return ANDERS[klasse] ?? klasse;
}

export async function faerbeCode(flaeche: HTMLElement): Promise<void> {
  const bloecke = [...flaeche.querySelectorAll<HTMLElement>("pre code")].filter((b) => !b.dataset.highlighted);
  if (!bloecke.length) return;
  const { default: hljs } = await import("highlight.js/lib/core");
  const genannt = new Set(bloecke.map(spracheVon).filter(Boolean));
  for (const s of genannt.size ? genannt : UEBLICH) {
    if (!SPRACHEN[s] || hljs.getLanguage(s)) continue;
    hljs.registerLanguage(s, (await SPRACHEN[s]()).default);
  }
  for (const b of bloecke) {
    const s = spracheVon(b);
    // Unbekannte Sprache: der Block bleibt schlichter Text, statt eine Warnung zu werfen
    if (s && !hljs.getLanguage(s)) continue;
    hljs.highlightElement(b);
  }
}

const KOPIERT_MS = 2000;

export function kopierknoepfe(flaeche: HTMLElement): void {
  for (const pre of flaeche.querySelectorAll<HTMLElement>("pre")) {
    const code = pre.querySelector("code");
    if (!code || pre.querySelector(".code-kopieren")) continue;
    const knopf = document.createElement("button");
    knopf.type = "button";
    knopf.className = "code-kopieren";
    knopf.title = "Code kopieren";
    knopf.setAttribute("aria-label", "Code kopieren");
    const zeichen = document.createElement("i");
    zeichen.className = "fa-solid fa-copy";
    zeichen.setAttribute("aria-hidden", "true");
    knopf.append(zeichen);
    knopf.addEventListener("click", async () => {
      await navigator.clipboard.writeText(code.textContent ?? "");
      zeichen.className = "fa-solid fa-check";
      setTimeout(() => (zeichen.className = "fa-solid fa-copy"), KOPIERT_MS);
    });
    pre.append(knopf);
  }
}
