// Buchauszüge der Suche: nur <mark> (und das alte <b>) gilt als Auszeichnung, alles andere ist Text.

export interface Stueck {
  text: string;
  markiert: boolean;
}

export function zerlege(auszug: string | null | undefined): Stueck[] {
  const stuecke: Stueck[] = [];
  let markiert = false;
  for (const teil of (auszug ?? "").split(/(<\/?(?:mark|b)>)/i)) {
    if (/^<(mark|b)>$/i.test(teil)) markiert = true;
    else if (/^<\/(mark|b)>$/i.test(teil)) markiert = false;
    else if (teil) stuecke.push({ text: teil, markiert });
  }
  return stuecke;
}

/** Das erste hervorgehobene Wort, für den Sprung an die Stelle */
export function ersteMarkierung(auszug: string | null | undefined): string {
  return zerlege(auszug).find((s) => s.markiert)?.text ?? "";
}
