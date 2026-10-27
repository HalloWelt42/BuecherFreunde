/**
 * Gemeinsame Darstellung der Leser am Telefon (Textansicht eines PDF und EPUB): Bereiche für Schriftgröße und
 * Zeilenabstand und die wählbaren Schriftarten.
 */

export const SCHRIFTGROESSE = { min: 60, max: 300, schritt: 5, vorgabe: 110 };
export const ZEILENABSTAND = { min: 1.2, max: 2.4, schritt: 0.1, vorgabe: 1.6 };

// Schriftnamen sind technische Bezeichner der gebündelten Schriften
export const SCHRIFTARTEN = [
  { kennung: "literata", name: "Literata", familie: '"Literata", Georgia, serif' },
  { kennung: "atkinson", name: "Atkinson Hyperlegible", familie: '"Atkinson Hyperlegible", system-ui, sans-serif' },
  { kennung: "georgia", name: "Georgia", familie: 'Georgia, "Times New Roman", serif' },
  { kennung: "barlow", name: "Barlow", familie: "Barlow, system-ui, sans-serif" },
  { kennung: "system", name: "System", familie: "system-ui, -apple-system, sans-serif" },
];

/**
 * Wert in den Bereich holen.
 * @param {number} wert
 * @param {{min: number, max: number}} bereich
 */
export function klemme(wert, { min, max }) {
  return Math.min(max, Math.max(min, wert));
}
