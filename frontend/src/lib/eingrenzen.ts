// Lange Listen in der Leiste und im Filterfeld: erst ab VIELE Einträgen gibt es eine Suche, bei wenigen bleibt alles wie es ist.
// Gezeigt werden höchstens `hoechstens` Treffer, Gewähltes immer, in der Reihenfolge der Liste.
export const VIELE = 12;

export interface Eingegrenzt<T> {
  gezeigt: T[];
  /** Treffer, die nicht gezeigt werden: Suche verfeinern */
  weitere: number;
  mitSuche: boolean;
}

export function eingrenzen<T>(liste: readonly T[], name: (t: T) => string, wort: string, gewaehlt: (t: T) => boolean, hoechstens: number): Eingegrenzt<T> {
  if (liste.length <= VIELE) return { gezeigt: [...liste], weitere: 0, mitSuche: false };
  const w = wort.trim().toLocaleLowerCase("de");
  const passt = w ? liste.filter((t) => name(t).toLocaleLowerCase("de").includes(w)) : [...liste];
  const nimm = new Set(passt.slice(0, hoechstens));
  return { gezeigt: liste.filter((t) => nimm.has(t) || gewaehlt(t)), weitere: Math.max(0, passt.length - hoechstens), mitSuche: true };
}
