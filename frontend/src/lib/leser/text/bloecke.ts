// Reinen Text in Blöcke teilen, ohne dass eine Leerzeile verloren geht: geschnitten wird vor einer Leerzeile. Ein Block
// endet nie mit einer Leerzeile, die der Browser am Ende eines Blocks nicht zeichnete.
const ZEILEN = 40;
const HOECHSTENS = 400;

const leer = (z: string) => z.trim() === "";

export function inBloecke(text: string): string[] {
  const zeilen = text.replace(/\r\n?/g, "\n").split("\n");
  const aus: string[] = [];
  let anfang = 0;
  for (let n = 1; n < zeilen.length; n++) {
    const lang = n - anfang;
    const schnitt = (lang >= ZEILEN && leer(zeilen[n]) && !leer(zeilen[n - 1])) || (lang >= HOECHSTENS && !leer(zeilen[n]) && !leer(zeilen[n - 1]));
    if (!schnitt) continue;
    aus.push(zeilen.slice(anfang, n).join("\n"));
    anfang = n;
  }
  aus.push(zeilen.slice(anfang).join("\n"));
  return aus;
}
