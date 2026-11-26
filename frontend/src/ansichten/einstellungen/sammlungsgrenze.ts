// Ab wie vielen Büchern eine Sammlung als ein Eintrag steht (BF-66); die Grenzen wie am Server
export const GRENZE_AB = 2;
export const GRENZE_BIS = 1000;

/** Eine ganze Zahl in den Grenzen, sonst null */
export function grenzeAus(wert: unknown): number | null {
  const n = typeof wert === "number" ? wert : Number(String(wert ?? "").trim());
  return Number.isInteger(n) && n >= GRENZE_AB && n <= GRENZE_BIS ? n : null;
}
