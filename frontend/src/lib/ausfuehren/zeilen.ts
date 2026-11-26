// Code als gefärbte Zeilen für das Blatt am Telefon (BF-29): dort gibt es keinen Editor, nur lesend, Zeile für Zeile. Gefärbt
// wird mit highlight.js wie die Codeblöcke im Text; eine Hervorhebung über mehrere Zeilen wird an jedem Zeilenende
// geschlossen und in der nächsten wieder geöffnet.
import type { Codesprache } from "../api/ausfuehren";

const SPRACHEN: Record<Codesprache, () => Promise<{ default: import("highlight.js").LanguageFn }>> = {
  python: () => import("highlight.js/lib/languages/python"),
  javascript: () => import("highlight.js/lib/languages/javascript"),
  php: () => import("highlight.js/lib/languages/php"),
};

/** HTML einer Färbung in Zeilen teilen, offene Spannen je Zeile schließen und wieder öffnen */
export function inZeilen(html: string): string[] {
  const zeilen: string[] = [];
  const offen: string[] = [];
  let jetzt = "";
  for (const teil of html.split(/(<span[^>]*>|<\/span>|\n)/)) {
    if (teil === "\n") {
      zeilen.push(jetzt + "</span>".repeat(offen.length));
      jetzt = offen.join("");
    } else if (teil.startsWith("<span")) {
      offen.push(teil);
      jetzt += teil;
    } else if (teil === "</span>") {
      offen.pop();
      jetzt += teil;
    } else jetzt += teil;
  }
  zeilen.push(jetzt + "</span>".repeat(offen.length));
  return zeilen;
}

const maskiere = (t: string) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** Gefärbte Zeilen; ohne Färbung (Fehler beim Laden) die Zeilen als schlichter Text */
export async function faerbeZeilen(code: string, sprache: Codesprache): Promise<string[]> {
  try {
    const { default: hljs } = await import("highlight.js/lib/core");
    if (!hljs.getLanguage(sprache)) hljs.registerLanguage(sprache, (await SPRACHEN[sprache]()).default);
    return inZeilen(hljs.highlight(code, { language: sprache, ignoreIllegals: true }).value);
  } catch {
    return code.split("\n").map(maskiere);
  }
}
