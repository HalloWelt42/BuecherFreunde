// Die Schlüssel der Ansagen an einer Stelle (docs/neubau/SCHNITTSTELLE.md, Feste Ansagen; Sätze in
// backend/app/familie/ansagen.json). GET /api/familie/ansagen liefert sie als fertige Töne unter "gruppe.name": tasten.weiter,
// hinweise.frag_eltern, uhr.4, minute.35, noch.25, heute.45, titel.<buch>, katze, katze.<vorschlag>, ruhezeit, profil.<profil>.
// Eine Ansage ist eine Folge von Schlüsseln, die ohne Pause hintereinander klingen. Wie die Schlüssel heißen, steht nur hier.

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
  stiftAn: taste("stift_an"),
  stiftAus: taste("stift_aus"),
  gemerkt: taste("gemerkt"),
  lesezeichenWeg: taste("lesezeichen_weg"),
  notiz: taste("notiz"),
  lieblingsbuch: taste("lieblingsbuch"),
  keinLieblingsbuch: taste("kein_lieblingsbuch"),
  fertig: taste("fertig"),
  kinderschriftAn: taste("kinderschrift_an"),
  kinderschriftAus: taste("kinderschrift_aus"),
} as const;

export const HINWEIS = {
  /** Fünf Minuten vor dem Ende */
  lesezeitBald: hinweis("lesezeit_gleich_um"),
  /** Die Lesezeit ist um: auf dem Ruheschirm */
  lesezeitUm: hinweis("lesezeit_um"),
  fragEltern: hinweis("frag_eltern"),
  katzeBenennen: hinweis("katze_benennen"),
  werLiest: hinweis("wer_liest"),
  /** "Tippe drei Bilder an." */
  bildPin: hinweis("bild_pin"),
  bildPinFalsch: hinweis("bild_pin_falsch"),
  buchFertig: hinweis("buch_fertig"),
  regalLeer: hinweis("regal_leer"),
  lieblingeLeer: hinweis("lieblinge_leer"),
  gelesenLeer: hinweis("gelesen_leer"),
  sucheLeer: hinweis("suche_leer"),
} as const;

/** "Jetzt ist Ruhezeit. Ab sechs Uhr dreißig kannst du wieder lesen.", ein ganzer Satz je Kind mit dem Ende seiner Ruhezeit */
export const RUHEZEIT = "ruhezeit";
/** Der Titel eines freigegebenen Buchs */
export const buch = (id: number): string => `titel.${id}`;
/** Der Name der Katze */
export const KATZE = "katze";
/** Ein Vorschlag für den Namen der Katze im Vorlesealter (stufen.json, katze.vorschlaege) */
export const katzenvorschlag = (name: string): string => `katze.${name}`;
/** Der Name eines Profils für "Wer liest?", in der Stimme der Familie */
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
