/**
 * Hilfsfunktionen rund ums Lesen / Lesefortschritt.
 */

/**
 * Berechnet den Lesefortschritt (0-100) aus einer reading_position.
 * Unterstuetzte Formate: pdf, epub, page, percent.
 */
export function parseProgress(position, pageCount) {
  if (!position) return 0;
  try {
    if (position.startsWith("pdf:")) {
      const data = JSON.parse(position.slice(4));
      if (data.page && pageCount > 0) {
        return Math.round((data.page / pageCount) * 100);
      }
    }
    if (position.startsWith("epub:")) {
      const data = JSON.parse(position.slice(5));
      if (data.percent > 0) return data.percent;
    }
    if (position.startsWith("page:")) {
      return Math.min(Number(position.slice(5)) || 0, 100);
    }
    if (position.startsWith("percent:")) {
      return Number(position.slice(8)) || 0;
    }
  } catch { /* ungueltige Position ignorieren */ }
  return 0;
}
