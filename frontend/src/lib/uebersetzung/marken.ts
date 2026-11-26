// Text mit Marken (BF-71, backend/app/uebersetzung/marken.py) zum Zeigen: Klammermarken <t1>..</t1> tragen Auszeichnungen
// (kursiv, fett, Verweis) und fallen weg, ihr Text bleibt; Platzhalter <x2/> stehen für Unantastbares (Code, Formeln, Bilder,
// Fußnotenzeichen), dessen Inhalt nicht im Text steht. Text kommt mit &lt; &gt; &amp;.

export type Stueck = { art: "text"; text: string; markiert: boolean } | { art: "platz"; markiert: boolean };

const MARKE = /<(\/?)t(\d+)>|<x(\d+)\/>/g;
const ZEICHEN: Record<string, string> = { "&lt;": "<", "&gt;": ">", "&amp;": "&", "&quot;": '"', "&#39;": "'", "&#x27;": "'" };

function klar(text: string): string {
  return text.replace(/&(?:lt|gt|amp|quot|#39|#x27);/g, (e) => ZEICHEN[e]);
}

function geschuetzt(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Wo die Stelle im Text steht: wörtlich, sonst so, wie sie im Text geschützt stünde; [-1, -1] ohne Fund */
function bereich(text: string, stelle: string): [number, number] {
  const s = stelle.trim();
  if (!s) return [-1, -1];
  for (const form of [s, geschuetzt(s)]) {
    const a = text.indexOf(form);
    if (a >= 0) return [a, a + form.length];
  }
  return [-1, -1];
}

/** Der Text als Stücke; was in `stelle` steht, ist markiert (die erste Fundstelle) */
export function stuecke(text: string, stelle = ""): Stueck[] {
  const [von, bis] = bereich(text, stelle);
  const aus: Stueck[] = [];
  const textstueck = (roh: string, markiert: boolean) => {
    if (!roh) return;
    const letztes = aus[aus.length - 1];
    if (letztes?.art === "text" && letztes.markiert === markiert) letztes.text += klar(roh);
    else aus.push({ art: "text", text: klar(roh), markiert });
  };
  /** Text von a bis b, an den Grenzen der Stelle geteilt */
  const text_ = (a: number, b: number) => {
    const schnitte = [a, ...[von, bis].filter((x) => x > a && x < b), b];
    for (let n = 0; n < schnitte.length - 1; n++) textstueck(text.slice(schnitte[n], schnitte[n + 1]), schnitte[n] >= von && schnitte[n] < bis);
  };
  let pos = 0;
  for (const m of text.matchAll(MARKE)) {
    const a = m.index ?? 0;
    text_(pos, a);
    if (m[3]) aus.push({ art: "platz", markiert: a >= von && a < bis });
    pos = a + m[0].length;
  }
  text_(pos, text.length);
  return aus;
}

/** Nur der Text, ohne Marken, etwa für Suche und Beschriftung */
export function klartext(text: string): string {
  return stuecke(text).map((s) => (s.art === "text" ? s.text : "…")).join("");
}
