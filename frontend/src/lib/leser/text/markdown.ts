// Markdown: Hinweiskästen und sichere Darstellung. Nur wenige Tags ohne Merkmale gelten, jedes andere HTML ist Text.

/** Hinweisarten (auch die erweiterten Namen) auf fünf Grundarten */
const ARTEN: Record<string, string> = {
  note: "note", info: "note", abstract: "note", summary: "note", tldr: "note", example: "note", quote: "note", cite: "note",
  tip: "tip", hint: "tip", success: "tip", check: "tip", done: "tip",
  important: "important", faq: "important", question: "important",
  warning: "warning", attention: "warning", todo: "warning",
  caution: "caution", danger: "caution", error: "caution", failure: "caution", bug: "caution",
};

interface Kasten {
  type: "alert";
  raw: string;
  text: string;
  alertType: string;
}

/** > [!art] Text (eine Zeile) oder > [!art] mit Folgezeilen */
export function hinweiskasten() {
  return {
    extensions: [{
      name: "alert",
      level: "block" as const,
      start: (src: string) => src.match(/>\s*\[!/)?.index,
      tokenizer(src: string): Kasten | undefined {
        const m = src.match(/^>\s*\[!(\w+)\][ \t]*(.*?)(?:\n((?:>\s?[^\n]*(?:\n|$))*))?(?:\n|$)/);
        const art = m ? ARTEN[m[1].toLowerCase()] : undefined;
        if (!m || !art) return undefined;
        const rest = (m[3] ?? "").split("\n").map((z) => z.replace(/^>\s?/, "")).join("\n").trim();
        return { type: "alert", raw: m[0], text: [(m[2] ?? "").trim(), rest].filter(Boolean).join("\n"), alertType: art };
      },
    }],
  };
}

const ERLAUBT = /^<\/?(?:br|hr|b|i|em|strong|u|s|sub|sup|kbd|mark|small|details|summary)\s*\/?>$/i;
const VERWEIS = /^<(?:https?:\/\/|mailto:)[^\s>]+>$/i;
/** Codezäune und Code im Satz bleiben unberührt */
const CODE = /(^(?:```|~~~)[^\n]*\n[\s\S]*?^(?:```|~~~)[ \t]*$|`[^`\n]+`)/m;

/** Jedes andere Tag bekommt einen Rückstrich davor und steht damit als Text da */
export function entschaerfe(quelle: string): string {
  return quelle
    .split(new RegExp(CODE.source, "gm"))
    .map((teil, n) => (n % 2 ? teil : teil.replace(/<[!/?a-zA-Z][^>]*>?/g, (t) => (ERLAUBT.test(t) || VERWEIS.test(t) ? t : t.replace(/</g, "\\<")))))
    .join("");
}

export const mitDiagramm = (quelle: string) => /^(?:```|~~~)\s*mermaid/m.test(quelle);

/** Nur Adressen, die nichts ausführen */
export function sichereAdresse(href: string): string {
  return /^(?:https?:|mailto:|#)/i.test(href.trim()) ? href.trim() : "";
}
