// Wohin der Leser beim Öffnen springt: aus der Adresse, dann aus dem gemerkten Stand
import type { Lesewerte } from "../lesestand";

export interface Leseziel {
  seite: number;
  zoom: number;
  ansicht: string;
  papier: string;
  cfi: string;
  prozent: number;
  /** Suchbegriff, dessen erster Treffer gezeigt wird */
  wort: string;
  /** Wortlaut einer Fundstelle auf der Seite (etwa aus dem Assistenten) */
  stelle: string;
  /** "Von vorn": nur die Stelle zählt nicht, Schrift und Farben bleiben */
  vonVorn: boolean;
}

export function leseziel(suche: string): Leseziel {
  const p = new URLSearchParams(suche);
  const cfi = p.get("cfi") ?? "";
  // Verweise auf Markierungen eines PDF nennen die Seite als cfi=page:N, die eines Textes als cfi=percent:N
  const seite = cfi.match(/^page:(\d+)/);
  const prozent = cfi.match(/^percent:([\d.]+)/);
  return {
    seite: Number(p.get("page")) || Number(seite?.[1]) || 0,
    zoom: Number(p.get("zoom")) || 0,
    ansicht: p.get("ansicht") ?? "",
    papier: p.get("papier") ?? "",
    cfi: seite || prozent ? "" : cfi,
    prozent: Number(p.get("percent")) || Number(p.get("pos")) || Number(prozent?.[1]) || 0,
    wort: p.get("q") ?? "",
    stelle: p.get("stelle") ?? "",
    vonVorn: p.get("restart") === "1",
  };
}

/** Nennt die Adresse selbst eine Stelle? Dann gilt der gemerkte Stand nicht. */
export function nenntStelle(z: Leseziel): boolean {
  return z.seite > 0 || z.prozent > 0 || !!z.cfi || !!z.wort;
}

/** Der gemerkte Stand ohne Stelle, wenn von vorn gelesen wird */
export function gemerkt(z: Leseziel, w: Lesewerte): Lesewerte {
  if (!z.vonVorn) return w;
  const { page: _seite, cfi: _cfi, percent: _prozent, scrollPct: _rollen, ...rest } = w;
  return rest;
}
