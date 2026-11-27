// Suchsprache: was man eintippen kann und wie man einen Filter wieder herausnimmt

export const beispiele: [string, string][] = [
  ['"exakter Satz"', "genau diese Wörter hintereinander"],
  ["wort*", "alles, was so anfängt"],
  ["haus AND garten", "beide Wörter"],
  ["haus OR hütte", "eines von beiden"],
  ["haus NOT boot", "das eine ohne das andere"],
  ["autor:HalloWelt42", "nur von diesem Autor, auch author:"],
  ["format:epub", "nur dieses Format: pdf, epub, mobi, txt, md"],
  ["datum:2023", "erschienen in diesem Jahr, auch date:"],
  ["datum:2018-2026", "erschienen zwischen den Jahren"],
  ["datum:>=2020", "ab diesem Jahr, auch > < <="],
];

const MUSTER: Record<string, RegExp> = {
  autor: /\b(?:autor|author):(?:"[^"]*"|\S+)/gi,
  format: /\bformat:\S+/gi,
  datum: /\b(?:datum|date):\S+/gi,
};

const NAMEN: Record<string, string> = { autor: "autor", format: "format", jahr: "datum", zeitraum: "datum", ab: "datum ab", bis: "datum bis" };

export function filtername(art: string): string {
  return NAMEN[art] ?? art;
}

/** Suchwort ohne diesen Filter; autor, format oder ein Datum */
export function ohneFilter(frage: string, art: string): string {
  const muster = MUSTER[art] ?? MUSTER.datum;
  return frage.replace(muster, " ").replace(/\s+/g, " ").trim();
}

/** Nur der freie Text, für die Suche nach Bedeutung */
export function nurText(frage: string): string {
  return Object.keys(MUSTER).reduce(ohneFilter, frage).replace(/["*]/g, " ").replace(/\s+/g, " ").trim();
}
