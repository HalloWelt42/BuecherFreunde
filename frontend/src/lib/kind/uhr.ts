// Die Kinderuhr (BF-78, Entwurf Runde 3): eine Zeigeruhr ohne Sekundenzeiger, die restliche Lesezeit als farbiges Stück vom
// Minutenzeiger bis zum Punkt am Rand. Ist der große Zeiger am Punkt, ist die Lesezeit um. Mehr als 60 Minuten füllen den Kreis;
// beginnt die Ruhezeit früher, endet das Stück dort. Alles in einem Zifferblatt mit viewBox 0 0 100 100, Mitte 50 50.

export const RAND = 44;
export const ZAHLEN = 30;
export const STUNDENZEIGER = 21;
export const MINUTENZEIGER = 35;

export type Punkt = [number, number];

const rund = (x: number) => Math.round(x * 100) / 100;

/** Ort auf dem Zifferblatt bei einer Minute (0 oben, im Uhrzeigersinn) und einem Abstand zur Mitte */
export function ort(minute: number, r: number): Punkt {
  const w = (minute / 60) * 2 * Math.PI - Math.PI / 2;
  return [rund(50 + r * Math.cos(w)), rund(50 + r * Math.sin(w))];
}

/** Winkel der Zeiger in Grad ab 12 Uhr; über den Tag stetig wachsend, so dreht ein Übergang nie rückwärts */
export function zeigerwinkel(stunde: number, minute: number): { stunde: number; minute: number } {
  const minuten = stunde * 60 + minute;
  return { stunde: minuten * 0.5, minute: minuten * 6 };
}

/** Wie viele Minuten das farbige Stück zeigt: der Rest, höchstens bis zur Ruhezeit und höchstens eine Stunde */
export function stueckMinuten(rest: number, bisRuhe: number | null): number {
  return Math.max(0, Math.min(60, rest, bisRuhe ?? Infinity));
}

/** Das farbige Stück als Pfad; null, wenn es den ganzen Kreis füllt oder nichts zu zeigen ist */
export function stueckPfad(minute: number, dauer: number): string | null {
  if (dauer <= 0 || dauer >= 60) return null;
  const [ax, ay] = ort(minute, RAND);
  const [ex, ey] = ort(minute + dauer, RAND);
  return `M50 50L${ax} ${ay}A${RAND} ${RAND} 0 ${dauer > 30 ? 1 : 0} 1 ${ex} ${ey}Z`;
}

/** Ein Strich je Minute (große Uhr) oder nur die zwölf Stundenstriche (kleine Uhr) */
export function striche(gross: boolean): { von: Punkt; bis: Punkt; stunde: boolean }[] {
  const aus: { von: Punkt; bis: Punkt; stunde: boolean }[] = [];
  for (let i = 0; i < 60; i++) {
    const stunde = i % 5 === 0;
    if (stunde || gross) aus.push({ von: ort(i, stunde ? 38.5 : 41.5), bis: ort(i, RAND), stunde });
  }
  return aus;
}

/** Die Zahlen 1 bis 12 an ihren Orten */
export const zahlen = (): { zahl: number; bei: Punkt }[] => Array.from({ length: 12 }, (_, i) => ({ zahl: i + 1, bei: ort((i + 1) * 5, ZAHLEN) }));

/** Minuten bis zur Ruhezeit ab jetzt; "19:30" oder ein Zeitpunkt; null ohne Angabe */
export function minutenBis(ruheAb: string | null, jetzt: Date): number | null {
  if (!ruheAb) return null;
  const uhrzeit = /^(\d{1,2}):(\d{2})$/.exec(ruheAb);
  let ziel: Date;
  if (uhrzeit) {
    ziel = new Date(jetzt.getFullYear(), jetzt.getMonth(), jetzt.getDate(), Number(uhrzeit[1]), Number(uhrzeit[2]));
    if (ziel.getTime() <= jetzt.getTime()) ziel = new Date(ziel.getTime() + 86_400_000);
  } else ziel = new Date(ruheAb);
  if (Number.isNaN(ziel.getTime())) return null;
  return Math.max(0, Math.floor((ziel.getTime() - jetzt.getTime()) / 60_000));
}

/** "Es ist 4 Uhr 35, noch 25 Minuten lesen" */
export function uhrtext(stunde: number, minute: number, rest: number): string {
  const s = stunde % 12 || 12;
  const zeit = minute ? `${s} Uhr ${minute}` : `${s} Uhr`;
  return `Es ist ${zeit}, noch ${rest} ${rest === 1 ? "Minute" : "Minuten"} lesen`;
}

/** Restliche Minuten zum Anzeigen: angefangene zählen mit, so steht bei 30 Sekunden noch "1" */
export const restMinuten = (sekunden: number): number => Math.max(0, Math.ceil(sekunden / 60));
