/**
 * Suchverlauf im Speicher des Browsers, geteilt von der Suchleiste am Rechner und der Telefonansicht.
 */

const SCHLUESSEL = "search_history";
const HOECHSTENS = 50;

/** @returns {string[]} */
export function ladeVerlauf() {
  try {
    const roh = localStorage.getItem(SCHLUESSEL);
    return roh ? JSON.parse(roh) : [];
  } catch {
    return [];
  }
}

/** @param {string[]} verlauf */
function speichere(verlauf) {
  try {
    localStorage.setItem(SCHLUESSEL, JSON.stringify(verlauf));
  } catch { /* Speicher voll oder gesperrt */ }
}

/**
 * Begriff vorne einreihen (ohne Doppel) und den neuen Verlauf liefern.
 * @param {string[]} verlauf
 * @param {string} begriff
 * @returns {string[]}
 */
export function merkeBegriff(verlauf, begriff) {
  const sauber = begriff.trim();
  if (sauber.length < 2) return verlauf;
  const neu = [sauber, ...verlauf.filter((b) => b !== sauber)].slice(0, HOECHSTENS);
  speichere(neu);
  return neu;
}

/**
 * @param {string[]} verlauf
 * @param {string} begriff
 * @returns {string[]}
 */
export function vergissBegriff(verlauf, begriff) {
  const neu = verlauf.filter((b) => b !== begriff);
  speichere(neu);
  return neu;
}

/** @returns {string[]} */
export function leereVerlauf() {
  speichere([]);
  return [];
}
