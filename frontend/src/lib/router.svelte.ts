// Echte Pfade in der Adresse, ohne Neuladen der Seite

interface Ort {
  path: string;
  /** Adressteil hinter dem Fragezeichen */
  qs: string;
  params: Record<string, string>;
}

function jetzt(): Ort {
  const qs = window.location.search.slice(1);
  return { path: window.location.pathname || "/", qs, params: Object.fromEntries(new URLSearchParams(qs)) };
}

export const route = $state<Ort>(jetzt());

function uebernimm(): void {
  Object.assign(route, jetzt());
}

export function navigate(pfad: string, ersetzen = false): void {
  if (ersetzen) history.replaceState(null, "", pfad);
  else history.pushState(null, "", pfad);
  uebernimm();
}

if (typeof window !== "undefined") addEventListener("popstate", uebernimm);

/** Verweise innerhalb der App abfangen. Cmd, Strg, Umschalt, Alt und die mittlere Taste gehören dem Browser. */
export function handleLinkClick(e: MouseEvent): void {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const verweis = (e.target as Element).closest?.("a[href]");
  const href = verweis?.getAttribute("href");
  if (!verweis || !href || !href.startsWith("/") || href.startsWith("//") || href.startsWith("/api/")) return;
  if (verweis.hasAttribute("download") || verweis.getAttribute("target") === "_blank") return;
  e.preventDefault();
  navigate(href);
}

/** Passt der Pfad zum Muster ("/book/:id", "/settings/*")? Dann die Bestandteile, sonst null. */
export function matchRoute(muster: string, pfad: string): Record<string, string> | null {
  if (muster === pfad) return {};
  const m = muster.split("/");
  const p = pfad.split("/");
  const offen = m[m.length - 1] === "*";
  if (offen ? p.length < m.length - 1 : p.length !== m.length) return null;
  const bestandteile: Record<string, string> = {};
  for (let n = 0; n < m.length; n++) {
    if (m[n] === "*") return bestandteile;
    if (m[n].startsWith(":")) bestandteile[m[n].slice(1)] = decodeURIComponent(p[n]);
    else if (m[n] !== p[n]) return null;
  }
  return bestandteile;
}
