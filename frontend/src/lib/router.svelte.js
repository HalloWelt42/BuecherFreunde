/**
 * SPA-Router mit History API und Svelte 5 Runes.
 * $state in .svelte.js = universelle Reaktivitaet.
 */

// --- Reaktiver State (direkt exportiert) ---

export const route = $state({
  path: window.location.pathname || "/",
  qs: window.location.search ? window.location.search.slice(1) : "",
  params: Object.fromEntries(new URLSearchParams(window.location.search || "")),
});

// --- Interne Hilfsfunktion ---

function updateFromLocation() {
  route.path = window.location.pathname || "/";
  route.qs = window.location.search ? window.location.search.slice(1) : "";
  route.params = Object.fromEntries(new URLSearchParams(route.qs));
}

// --- Navigation ---

/**
 * Zu einem Pfad navigieren.
 * @param {string} path - z.B. "/settings" oder "/book/42?page=5"
 * @param {boolean} [replaceHistory=false]
 */
export function navigate(path, replaceHistory = false) {
  if (replaceHistory) {
    history.replaceState(null, "", path);
  } else {
    history.pushState(null, "", path);
  }
  updateFromLocation();
}

/** Alias */
export const push = navigate;

/**
 * Aktuellen Eintrag ersetzen.
 * @param {string} path
 */
export function replace(path) {
  navigate(path, true);
}

// --- Browser Back/Forward ---

if (typeof window !== "undefined") {
  window.addEventListener("popstate", updateFromLocation);
}

// --- Link-Click Handler ---

/**
 * Link-Klick abfangen fuer SPA-Navigation.
 * @param {MouseEvent} event
 */
export function handleLinkClick(event) {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

  const anchor = /** @type {HTMLElement} */ (event.target).closest("a[href]");
  if (!anchor) return;

  const href = anchor.getAttribute("href");
  if (!href) return;
  if (href.startsWith("http") || href.startsWith("mailto:") || href.startsWith("tel:")) return;

  event.preventDefault();
  navigate(href);
}

// --- Route Matching ---

/**
 * Matcht eine Route-Definition gegen einen Pfad.
 * @param {string} pattern - z.B. "/book/:id"
 * @param {string} path - z.B. "/book/42"
 * @returns {Record<string, string> | null}
 */
export function matchRoute(pattern, path) {
  if (pattern === path) return {};

  const patternParts = pattern.split("/");
  const pathParts = path.split("/");

  if (patternParts.length !== pathParts.length) {
    if (patternParts[patternParts.length - 1] === "*") {
      if (pathParts.length < patternParts.length - 1) return null;
    } else {
      return null;
    }
  }

  const params = {};
  for (let i = 0; i < patternParts.length; i++) {
    const pp = patternParts[i];
    if (pp === "*") return params;
    if (pp.startsWith(":")) {
      params[pp.slice(1)] = decodeURIComponent(pathParts[i]);
    } else if (pp !== pathParts[i]) {
      return null;
    }
  }
  return params;
}
