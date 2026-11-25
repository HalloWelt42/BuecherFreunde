// Wortlaut in zerstückeltem Text finden: verglichen ohne Leerraum, weil Textebene und Volltext ihn verschieden setzen

export interface Bereich {
  von: number;
  bis: number;
}

const KURZ = [60, 30, 15];
const HOECHSTENS = 160;

const ohneLeer = (t: string) => t.replace(/\s+/g, "");

/**
 * Die Stücke, die zum gesuchten Wortlaut gehören, als Bereich der Nummern [von, bis). Findet sich nicht alles, zählt ein
 * kürzerer Anfang. ab: erst ab diesem Anteil (0 bis 1) des Textes suchen, sonst von vorn.
 */
export function findeStuecke(stuecke: string[], wortlaut: string, ab = 0): Bereich | null {
  const gesucht = ohneLeer(wortlaut).toLowerCase();
  if (gesucht.length < 2) return null;
  const teile = stuecke.map((s) => ohneLeer(s).toLowerCase());
  const anfaenge: number[] = [];
  let laenge = 0;
  for (const t of teile) {
    anfaenge.push(laenge);
    laenge += t.length;
  }
  const alles = teile.join("");
  const nach = Math.floor(ab * alles.length);
  const suche = (w: string) => {
    const spaeter = alles.indexOf(w, nach);
    return spaeter >= 0 || nach === 0 ? spaeter : alles.indexOf(w);
  };
  let stelle = suche(gesucht);
  let umfang = gesucht.length;
  for (const kurz of KURZ) {
    if (stelle >= 0) break;
    if (gesucht.length <= kurz) continue;
    stelle = suche(gesucht.slice(0, kurz));
    umfang = Math.min(gesucht.length, HOECHSTENS);
  }
  if (stelle < 0) return null;
  const ende = Math.min(stelle + umfang, alles.length);
  const beruehrt = teile.map((t, i) => t.length > 0 && anfaenge[i] < ende && anfaenge[i] + t.length > stelle);
  const von = beruehrt.indexOf(true);
  return von < 0 ? null : { von, bis: beruehrt.lastIndexOf(true) + 1 };
}

export interface Zeichenstelle {
  knoten: Text;
  versatz: number;
}

/** Wortlaut als Anfang und Ende in Textknoten, zeichengenau; naechstes: die Fundstelle, die diesem Anteil am nächsten liegt */
export function findeZeichen(knoten: Text[], wortlaut: string, anteil: number | null): { von: Zeichenstelle; bis: Zeichenstelle } | null {
  const gesucht = ohneLeer(wortlaut).toLowerCase();
  if (gesucht.length < 2) return null;
  const stellen: Zeichenstelle[] = [];
  let alles = "";
  for (const k of knoten) {
    for (let i = 0; i < k.data.length; i++) {
      if (/\s/.test(k.data[i])) continue;
      stellen.push({ knoten: k, versatz: i });
      alles += k.data[i].toLowerCase()[0];
    }
  }
  const ziel = anteil === null ? 0 : anteil * alles.length;
  let beste = -1;
  for (let i = alles.indexOf(gesucht); i >= 0; i = alles.indexOf(gesucht, i + 1)) {
    if (beste < 0 || Math.abs(i - ziel) < Math.abs(beste - ziel)) beste = i;
    else break;
  }
  if (beste < 0) return null;
  const letzte = stellen[beste + gesucht.length - 1];
  return { von: stellen[beste], bis: { knoten: letzte.knoten, versatz: letzte.versatz + 1 } };
}
