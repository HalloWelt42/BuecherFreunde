// Kopplungscode und Gerätename, ohne Oberfläche
export const CODE_LAENGE = 8;
const LINK_MARKE = "koppeln=";

export function codeNormal(text: string): string {
  return text.replace(/[^0-9a-z]/gi, "").toUpperCase().slice(0, CODE_LAENGE);
}

/** Code aus dem Anker der Adresse (#koppeln=CODE), sonst leer */
export function codeAusAnker(anker: string): string {
  const marke = anker.replace(/^#/, "");
  return marke.startsWith(LINK_MARKE) ? codeNormal(marke.slice(LINK_MARKE.length)) : "";
}

export function geraetename(kennung: string, finger: number): string {
  if (/iPad|Tablet/i.test(kennung) || (/Macintosh/.test(kennung) && finger > 1)) return "Tablet";
  if (/iPhone|Mobile/i.test(kennung)) return "Telefon";
  return /Android/i.test(kennung) ? "Tablet" : "Rechner";
}

export function geraeteart(): "webapp" | "browser" {
  const eigenstaendig = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return eigenstaendig || matchMedia("(display-mode: standalone)").matches ? "webapp" : "browser";
}
