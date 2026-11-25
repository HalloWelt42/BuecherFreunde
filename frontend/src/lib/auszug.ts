// Buchauszüge der Suche: nur <mark> (und das alte <b>) gilt als Auszeichnung, alles andere ist Text. Der Server maskiert
// &, < und > im Text; hier werden sie wieder zu Zeichen und landen als Text in der Seite, nie als HTML.

export interface Stueck {
  text: string;
  markiert: boolean;
}

const ZEICHEN: Record<string, string> = { "&lt;": "<", "&gt;": ">", "&amp;": "&", "&quot;": '"', "&#x27;": "'", "&#39;": "'" };

function entmaskiere(text: string): string {
  return text.replace(/&(?:lt|gt|amp|quot|#x27|#39);/g, (z) => ZEICHEN[z]);
}

export function zerlege(auszug: string | null | undefined): Stueck[] {
  const stuecke: Stueck[] = [];
  let markiert = false;
  for (const teil of (auszug ?? "").split(/(<\/?(?:mark|b)>)/i)) {
    if (/^<(mark|b)>$/i.test(teil)) markiert = true;
    else if (/^<\/(mark|b)>$/i.test(teil)) markiert = false;
    else if (teil) stuecke.push({ text: entmaskiere(teil), markiert });
  }
  return stuecke;
}

/** Das erste hervorgehobene Wort, für den Sprung an die Stelle */
export function ersteMarkierung(auszug: string | null | undefined): string {
  return zerlege(auszug).find((s) => s.markiert)?.text ?? "";
}
