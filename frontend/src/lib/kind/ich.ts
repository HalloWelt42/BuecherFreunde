// Aus der Antwort von GET /api/familie/ich ein vollständiges Ich: was fehlt, kommt aus den Vorgaben der Stufe (vorgaben.json),
// Unbekanntes fällt weg. Nur hier wird die Rohform gelesen; alle Ansichten rechnen mit dem fertigen Ich.
import vorgaben from "./vorgaben.json";
import { STUFEN, type Faehigkeit, type Ich, type Katzenstand, type Kinderdarstellung, type Kinderprofil, type Lesezeitstand, type Stufe } from "./typen";

type Roh = Record<string, unknown>;

interface Stufenvorgabe {
  faehigkeiten: string[];
  darstellung: Kinderdarstellung;
}

const VORGABEN = vorgaben.stufen as Record<Stufe, Stufenvorgabe>;
const BEKANNT: Faehigkeit[] = ["lesen", "vorlesen", "lesezeichen", "suche", "favoriten", "gelesen", "markierungen", "notizen"];

export const KATZENNAMEN: readonly string[] = vorgaben.katzennamen;

const objekt = (w: unknown): Roh => (w && typeof w === "object" && !Array.isArray(w) ? (w as Roh) : {});
const text = (w: unknown, vorgabe: string): string => (typeof w === "string" ? w : vorgabe);
const zahl = (w: unknown, vorgabe: number): number => (typeof w === "number" && Number.isFinite(w) ? w : vorgabe);
const schalter = (w: unknown, vorgabe: boolean): boolean => (typeof w === "boolean" ? w : vorgabe);
const zahlOderNichts = (w: unknown): number | null => (typeof w === "number" && Number.isFinite(w) ? w : null);

export function stufeAus(w: unknown): Stufe | null {
  return STUFEN.includes(w as Stufe) ? (w as Stufe) : null;
}

/**
 * Fähigkeiten als Liste ["lesen", ...] oder als Schalter {lesen: true, ...}; fehlt die Angabe, gilt die Stufe. Der Rückblick
 * "Gelesen" gehört zu den eigenen Regalen: nennt der Server ihn nicht eigens, kommt er mit den Lieblingen.
 */
export function faehigkeitenAus(roh: unknown, stufe: Stufe): Set<Faehigkeit> {
  const benannt = Array.isArray(roh) || (!!roh && typeof roh === "object");
  const namen = Array.isArray(roh)
    ? roh.filter((n): n is string => typeof n === "string")
    : roh && typeof roh === "object"
      ? Object.entries(roh as Roh).filter(([, an]) => an === true).map(([n]) => n)
      : VORGABEN[stufe].faehigkeiten;
  const kennt = (f: string) => (Array.isArray(roh) ? roh.includes(f) : benannt ? f in (roh as Roh) : true);
  const aus = new Set(BEKANNT.filter((f) => namen.includes(f)));
  if (!kennt("gelesen") && aus.has("favoriten")) aus.add("gelesen");
  return aus;
}

/** Schriftgröße, die die Eltern je Kind wählen, gemessen an der Größe der Stufe */
const SCHRIFTSTUFE: Record<string, number> = { klein: 0.85, mittel: 1, gross: 1.2 };
/** Ein CSS-Millimeter in Pixeln */
const MM_PX = 96 / 25.4;
/** Eine Schrift, die nur als Familie gemeint ist ("andika"), wird zur ganzen Angabe */
const familie = (w: string, v: string) => (!w ? v : w.includes(",") || w.includes('"') ? w : w.toLowerCase() === "andika" ? v : `"${w}", system-ui, sans-serif`);

/**
 * Die Darstellung des Kindes: aus ich.darstellung (Schrift, Größe, Wörter je Zeile, Tippflächen, so wie die Stufe sie nennt) und
 * den Lesehilfen der Eltern (ich.darstellung selbst oder profil.einstellungen.lesehilfen). Beide Schreibweisen der Größen gelten:
 * groesse oder groesse_px, tippflaeche_mm oder tippflaeche_px; woerter_je_zeile null heißt nur nach Breite.
 */
export function darstellungAus(roh: unknown, stufe: Stufe, lesehilfen: unknown = {}): Kinderdarstellung {
  const r = objekt(roh);
  const h = { ...r, ...objekt(lesehilfen) };
  const v = VORGABEN[stufe].darstellung;
  const groesse = zahl(r.groesse, zahl(r.groesse_px, v.groesse)) * (SCHRIFTSTUFE[text(h.schrift_groesse ?? h.schrift, "")] ?? 1);
  const tippflaeche = typeof r.tippflaeche_mm === "number" ? r.tippflaeche_mm : typeof r.tippflaeche_px === "number" ? r.tippflaeche_px / MM_PX : v.tippflaeche_mm;
  return {
    schrift: familie(text(r.schrift, ""), v.schrift),
    groesse: Math.round(groesse),
    fett: schalter(r.fett, v.fett),
    zeilenabstand: zahl(r.zeilenabstand, v.zeilenabstand),
    woerter_je_zeile: r.woerter_je_zeile === null ? 0 : Math.max(0, Math.round(zahl(r.woerter_je_zeile, v.woerter_je_zeile))),
    zeichen_je_zeile: Math.max(12, Math.round(zahl(r.zeichen_je_zeile, v.zeichen_je_zeile))),
    abstand_absatz: zahl(r.abstand_absatz, v.abstand_absatz),
    abstand_buchstabe: zahl(r.abstand_buchstabe, v.abstand_buchstabe),
    abstand_wort: zahl(r.abstand_wort, v.abstand_wort),
    tippflaeche_mm: Math.max(11.6, Math.round(tippflaeche * 10) / 10),
    silben: schalter(h.silben, v.silben),
    lesezeile: schalter(h.lesezeile, v.lesezeile),
    mitlesen: schalter(h.mitlesen, v.mitlesen),
    tempo: Math.min(1.5, Math.max(0.6, zahl(h.tempo, v.tempo))),
    vorlesen_von_selbst: schalter(h.vorlesen_von_selbst, v.vorlesen_von_selbst),
  };
}

export function lesezeitAus(roh: unknown): Lesezeitstand {
  const r = objekt(roh);
  return {
    heute_s: Math.max(0, zahl(r.heute_s, 0)),
    rest_s: zahlOderNichts(r.rest_s),
    ruht: r.ruht === true,
    ruhe_bis: typeof r.ruhe_bis === "string" && r.ruhe_bis ? r.ruhe_bis : null,
    ruhe_ab: typeof r.ruhe_ab === "string" && r.ruhe_ab ? r.ruhe_ab : typeof r.ruhe_von === "string" && r.ruhe_von ? r.ruhe_von : null,
    hinweis_ab_s: zahlOderNichts(r.hinweis_ab_s),
  };
}

export function katzeAus(roh: unknown): Katzenstand {
  const r = objekt(roh);
  return { an: r.an !== false, name: text(r.name, "").trim(), schnurren: r.schnurren === true };
}

function profilAus(roh: unknown): Kinderprofil {
  const r = objekt(roh);
  const rolle = r.rolle === "verwaltung" || r.rolle === "erwachsen" ? r.rolle : "kind";
  return { id: text(r.id, ""), name: text(r.name, ""), zeichen: text(r.zeichen, "") || "face-smile", farbe: text(r.farbe, "") || "#2f6fb3", rolle, stufe: stufeAus(r.stufe) };
}

export function ichAus(roh: unknown): Ich {
  const r = objekt(roh);
  const profil = profilAus(r.profil);
  const stufe = profil.stufe ?? "vorlesen";
  const einstellungen = objekt(objekt(r.profil).einstellungen);
  return {
    profil,
    faehigkeiten: faehigkeitenAus(r.faehigkeiten, stufe),
    darstellung: darstellungAus(r.darstellung, stufe, einstellungen.lesehilfen),
    lesezeit: lesezeitAus(r.lesezeit),
    katze: katzeAus(r.katze),
  };
}

/** Den Kinderbereich nutzen Kinder bis zur Stufe Schule; in der Stufe Jugend lesen sie im normalen Leser */
export function nutztKinderbereich(ich: Pick<Ich, "profil">): boolean {
  return ich.profil.rolle === "kind" && ich.profil.stufe !== "jugend";
}
