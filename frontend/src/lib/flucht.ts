// Esc schließt immer das zuletzt Geöffnete, genau eines je Druck
type Schliessen = () => void;

const stapel: Schliessen[] = [];

/** Anmelden, solange etwas offen ist; liefert das Abmelden. */
export function beiEsc(schliessen: Schliessen): () => void {
  stapel.push(schliessen);
  return () => {
    const n = stapel.lastIndexOf(schliessen);
    if (n >= 0) stapel.splice(n, 1);
  };
}

if (typeof document !== "undefined") {
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || e.defaultPrevented || !stapel.length) return;
    e.preventDefault();
    stapel[stapel.length - 1]();
  });
}

/** Liegt der Fokus in einem Feld, gehören ihm die Tasten. */
export function schreibtGerade(e: Event): boolean {
  const ziel = e.target instanceof HTMLElement ? e.target : null;
  return !!ziel && (ziel.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(ziel.tagName));
}
