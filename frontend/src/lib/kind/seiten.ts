// Die Seiten des Kinderlesers: eine Einheit des Buchs wird in Seiten geteilt, die ganz auf den Schirm passen, ohne Rollen. Ein
// Bild beginnt eine neue Seite; der Text danach steht neben ihm (quer) oder darunter (hochkant), was nicht mehr passt, auf den
// nächsten Seiten in voller Breite. Eine Überschrift bleibt nie allein unten stehen.
import { zeilenende, type Breitenmass } from "./umbruch";
import type { Bild, Kinderblock, Wort } from "./typen";

export interface Zeile {
  woerter: Wort[];
  art: "titel" | "absatz";
  /** Erste Zeile eines Absatzes: davor steht der Absatzabstand */
  neuerAbsatz: boolean;
}

export interface Kinderseite {
  einheit: number;
  /** Höchstens ein Bild je Seite */
  bild: Bild | null;
  zeilen: Zeile[];
  /** Lage im Text der Einheit: von einschließlich, bis ausschließlich */
  von: number;
  bis: number;
}

export interface Flaeche {
  breite: number;
  hoehe: number;
}

export interface Seitenmass {
  /** Platz für Text auf einer Seite ohne Bild */
  text: Flaeche;
  /** Platz für Text auf einer Seite mit Bild */
  textMitBild: Flaeche;
  zeile: number;
  titelzeile: number;
  absatz: number;
  woerter: number;
  leer: number;
  /** Breitenmaß für Absätze und eines für Überschriften */
  mass: Breitenmass;
  titelmass: Breitenmass;
}

interface Entstehend extends Kinderseite {
  frei: number;
  breite: number;
}

export function seitenAus(einheit: number, bloecke: Kinderblock[], m: Seitenmass): Kinderseite[] {
  const seiten: Entstehend[] = [];
  const neu = (bild: Bild | null, von: number): Entstehend => {
    const f = bild ? m.textMitBild : m.text;
    const s: Entstehend = { einheit, bild, zeilen: [], von, bis: von, frei: f.hoehe, breite: f.breite };
    seiten.push(s);
    return s;
  };

  /** Zeilen auf die letzte Seite legen, umbrochen in ihrer Breite */
  const lege = (woerter: Wort[], art: Zeile["art"], s: Entstehend) => {
    for (let ab = 0; ab < woerter.length; ) {
      const ende = zeilenende(woerter, ab, { woerter: art === "titel" ? 0 : m.woerter, breite: s.breite, leer: m.leer }, art === "titel" ? m.titelmass : m.mass);
      s.zeilen.push({ woerter: woerter.slice(ab, ende), art, neuerAbsatz: ab === 0 });
      s.frei -= (art === "titel" ? m.titelzeile : m.zeile) + (ab === 0 && s.zeilen.length > 1 ? m.absatz : 0);
      s.bis = woerter[ende - 1].bis;
      ab = ende;
    }
  };

  for (const b of bloecke) {
    if (b.art === "bild") {
      // Steht auf der Seite bisher nur eine Überschrift, kommt das Bild zu ihr: die Überschrift steht dann über dem Text daneben
      const letzte = seiten.at(-1);
      if (letzte && !letzte.bild && letzte.zeilen.length && letzte.zeilen.every((z) => z.art === "titel")) {
        seiten.pop();
        lege(letzte.zeilen.flatMap((z) => z.woerter), "titel", neu(b.bild, letzte.von));
      } else neu(b.bild, b.von);
      continue;
    }
    if (!b.woerter.length) continue;
    const titel = b.art === "titel";
    const hoehe = titel ? m.titelzeile : m.zeile;
    const mass = titel ? m.titelmass : m.mass;
    let ab = 0;
    while (ab < b.woerter.length) {
      const s = seiten.at(-1) ?? neu(null, b.woerter[0].von);
      const erste = ab === 0;
      const abstand = erste && s.zeilen.length ? m.absatz : 0;
      // Eine Überschrift braucht unter sich noch Platz für eine Zeile Text
      const braucht = abstand + hoehe + (titel && erste ? m.absatz + m.zeile : 0);
      if (s.frei < braucht && (s.zeilen.length || s.bild)) {
        neu(null, b.woerter[ab].von);
        continue;
      }
      const ende = zeilenende(b.woerter, ab, { woerter: titel ? 0 : m.woerter, breite: s.breite, leer: m.leer }, mass);
      s.zeilen.push({ woerter: b.woerter.slice(ab, ende), art: b.art, neuerAbsatz: erste });
      s.frei -= abstand + hoehe;
      s.bis = b.woerter[ende - 1].bis;
      ab = ende;
    }
  }
  if (!seiten.length) seiten.push({ einheit, bild: null, zeilen: [], von: 0, bis: 0, frei: 0, breite: 0 });
  return seiten.map(({ frei: _f, breite: _b, ...seite }) => seite);
}

/** Die Seite, auf der ein Zeichen steht; davor die erste, danach die letzte */
export function seiteBei(seiten: Kinderseite[], zeichen: number): number {
  let nr = 0;
  for (let i = 0; i < seiten.length; i++) if (seiten[i].von <= zeichen) nr = i;
  return nr;
}

/** Alle Wörter einer Seite in Lesefolge */
export const woerterDer = (seite: Kinderseite): Wort[] => seite.zeilen.flatMap((z) => z.woerter);

