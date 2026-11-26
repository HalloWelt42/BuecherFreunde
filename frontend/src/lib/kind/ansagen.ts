// Die Schlüssel der Ansagen an einer Stelle. Die Sätze legt backend/app/familie/ansagen.json fest (tasten, hinweise, bausteine,
// dinge); GET /api/familie/ansagen liefert sie als fertige Töne unter "Gruppe.Name": tasten.weiter, hinweise.frag_eltern,
// uhr.4, minute.35, noch.25, heute.45, titel.{Buch}, katze, profil.{Profil}, ruhezeit. Eine Ansage ist eine Folge von
// Schlüsseln, die ohne Pause hintereinander klingen; zusammengesetzt wird nur die Uhr. Wie die Schlüssel heißen, steht nur hier.

export type Ansagefolge = string[];

const taste = (name: string) => `tasten.${name}`;
const hinweis = (name: string) => `hinweise.${name}`;

export const TASTE = {
  zurueck: taste("zurueck"),
  weiter: taste("weiter"),
  vorlesen: taste("vorlesen"),
  pause: taste("pause"),
  /** Nach der Pause weiterhören: dasselbe Wort wie Weiter */
  weiterHoeren: taste("weiter"),
  silbenAn: taste("silben_an"),
  silbenAus: taste("silben_aus"),
  zeileAn: taste("zeile_an"),
  zeileAus: taste("zeile_aus"),
  meinRegal: taste("mein_regal"),
  lieblinge: taste("lieblinge"),
  gelesen: taste("gelesen"),
  schloss: taste("schloss"),
  zumRegal: taste("zum_regal"),
  // Ab Stufe Schule (dort sind Ansagen von selbst aus) und am Ende eines Buchs; ohne Ton am Server bleiben sie still
  stiftAn: taste("stift_an"),
  stiftAus: taste("stift_aus"),
  gemerkt: taste("gemerkt"),
  lesezeichenWeg: taste("lesezeichen_weg"),
  notiz: taste("notiz"),
  lieblingsbuch: taste("lieblingsbuch"),
  keinLieblingsbuch: taste("kein_lieblingsbuch"),
  fertig: taste("fertig"),
} as const;

export const HINWEIS = {
  /** Fünf Minuten vor dem Ende */
  lesezeitBald: hinweis("lesezeit_gleich_um"),
  /** Die Lesezeit ist um: auf dem Ruheschirm */
  lesezeitUm: hinweis("lesezeit_um"),
  fragEltern: hinweis("frag_eltern"),
  katzeBenennen: hinweis("katze_benennen"),
  // Ohne Ton am Server bleiben sie still
  buchFertig: hinweis("buch_fertig"),
  regalLeer: hinweis("regal_leer"),
  lieblingeLeer: hinweis("lieblinge_leer"),
  gelesenLeer: hinweis("gelesen_leer"),
  sucheLeer: hinweis("suche_leer"),
} as const;

/** "Jetzt ist Ruhezeit. Ab 6:30 kannst du wieder lesen." mit der Uhrzeit des Kindes */
export const RUHEZEIT = "ruhezeit";
/** Der Titel eines freigegebenen Buchs */
export const buch = (id: number): string => `titel.${id}`;
/** Der Name der Katze */
export const KATZE = "katze";
/** Ein Vorschlag für den Namen der Katze; den Ton gibt es nur, wenn der Server ihn spricht */
export const katzenvorschlag = (name: string): string => `katze.${name}`;
export const profil = (id: string): string => `profil.${id}`;

/** "Es ist vier Uhr" + "fünfunddreißig" + "Noch fünfundzwanzig Minuten"; volle Stunden ohne Minutenwort */
export function uhrfolge(stunde: number, minute: number, rest: number | null): Ansagefolge {
  const aus = [`uhr.${stunde % 12 || 12}`];
  if (minute > 0) aus.push(`minute.${minute}`);
  if (rest !== null && rest > 0) aus.push(noch(rest));
  return aus;
}

/** "Noch fünf Minuten" */
export const noch = (minuten: number): string => `noch.${Math.min(120, Math.max(1, minuten))}`;
export const heute = (minuten: number): string => `heute.${Math.min(120, Math.max(1, minuten))}`;
