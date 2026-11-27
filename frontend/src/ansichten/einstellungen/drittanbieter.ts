// Bausteine Dritter (BF-90), je aus einer Wahrheit: die Pakete der Oberfläche schreibt der Bau (vite.config.js, build.license)
// samt Lizenztexten nach __LIZENZLISTE__, die des Servers liest der Server aus seinen installierten Paketen
// (backend/app/drittanbieter). Hier steht nur, wie die Seite sie zeigt; wofür ein Paket da ist, steht in zwecke.json.
import { get } from "../../lib/api/client";
import zwecke from "./zwecke.json";

/** Ein Eintrag der Liste, die der Bau schreibt */
export interface Baueintrag {
  name: string;
  version: string;
  identifier?: string;
  text?: string;
  adresse: string;
  /** Pakete aus package.json, über die es ins Bündel kommt; nur es selbst, wenn es dort steht */
  ueber: string[];
}

/** Ein Paket des Servers (GET /api/config/drittanbieter) */
export interface Serverpaket {
  name: string;
  fassung: string;
  lizenz: string;
  adresse: string;
  /** Pakete aus requirements.txt, über die es installiert ist; nur es selbst, wenn es dort steht */
  ueber: string[];
}

/** Eine Zeile der Seite */
export interface Paket {
  schluessel: string;
  name: string;
  fassung: string;
  lizenz: string;
  adresse: string;
  zweck: string;
}

type Zwecke = Record<string, string>;

/** Namen des Servers vergleicht pip klein, mit - statt _ und . (PEP 503) */
export const pythonName = (name: string): string => name.toLowerCase().replace(/[-_.]+/g, "-");

/** Wofür: ein eingetragenes Paket mit seinem Zweck, jedes andere für die eingetragenen, über die es kommt */
export function zweckAus(name: string, ueber: string[], eigene: Zwecke, normiert: (n: string) => string = (n) => n): string {
  if (ueber.length === 1 && normiert(ueber[0]) === normiert(name)) return eigene[normiert(name)] ?? "";
  return ueber.length ? `für ${ueber.join(", ")}` : "";
}

const EIGENE_DATEI = /^SEE LICENSE IN (\S+)$/i;

/** Wie die Seite eine Lizenz nennt: die Kennung des Pakets, eine eigene Datei als "siehe ..." */
export function lizenzName(kennung: string | undefined): string {
  const roh = kennung?.trim() ?? "";
  const datei = EIGENE_DATEI.exec(roh)?.[1];
  return datei ? `siehe ${datei}` : roh || "ohne Kennung";
}

export const oberflaechenzeilen = (liste: Baueintrag[]): Paket[] =>
  liste.map((e) => ({
    schluessel: `${e.name}@${e.version}`, name: e.name, fassung: e.version, lizenz: lizenzName(e.identifier), adresse: e.adresse,
    zweck: zweckAus(e.name, e.ueber, zwecke.oberflaeche),
  }));

export const serverzeilen = (liste: Serverpaket[]): Paket[] =>
  liste.map((p) => ({
    schluessel: `${p.name}@${p.fassung}`, name: p.name, fassung: p.fassung, lizenz: lizenzName(p.lizenz), adresse: p.adresse,
    zweck: zweckAus(p.name, p.ueber, zwecke.server, pythonName),
  }));

/** Die Pakete der Oberfläche; die Liste gibt es nur in einer gebauten Oberfläche */
export async function ladeOberflaeche(): Promise<Paket[]> {
  let liste: unknown = null;
  try {
    const antwort = await fetch(__LIZENZLISTE__);
    if (antwort.ok && antwort.headers.get("content-type")?.includes("json")) liste = await antwort.json();
  } catch {
    throw new Error("Die Liste der Oberfläche kam nicht an");
  }
  if (!Array.isArray(liste)) throw new Error("Die Liste der Oberfläche entsteht erst beim Bau");
  return oberflaechenzeilen(liste as Baueintrag[]);
}

export const ladeServer = async (): Promise<Paket[]> => serverzeilen(await get<Serverpaket[]>("/api/config/drittanbieter"));

export type Strenge = "gut" | "warn" | "schlecht" | "";

const STARK = /\bA?GPL|Affero|(?<!Lesser |Library )General Public License/i;
const SCHWACH = /\bLGPL|Lesser General Public|Library General Public|\bMPL\b|Mozilla Public|\bEPL\b|Eclipse Public|\bCDDL\b/i;
const FREI = /\bMIT\b|\bBSD\b|\b0BSD\b|\bISC\b|Apache|\bOFL\b|SIL Open Font|\bCC-BY-\d|\bCC BY \d|\bCC0\b|\bPSF\b|Python Software Foundation|\bZlib\b|Unlicense|Public Domain|\bCMU\b/i;
const STUFEN: Strenge[] = ["gut", "warn", "schlecht"];

/** Eine Lizenz ohne Verknüpfung; leer: eigene oder unbekannte, dazu sagt die Seite nichts */
function einzeln(lizenz: string): Strenge {
  if (STARK.test(lizenz)) return "schlecht";
  if (SCHWACH.test(lizenz)) return "warn";
  return FREI.test(lizenz) ? "gut" : "";
}

/** Bei OR gilt die freieste Wahl, die eine bekannte Lizenz bietet; bei AND die strengste, und eine unbekannte lässt offen */
function verknuepft(teile: Strenge[], und: boolean): Strenge {
  const bekannt = teile.filter((t) => t !== "");
  if (!bekannt.length || (und && bekannt.length < teile.length)) return "";
  const rang = bekannt.map((t) => STUFEN.indexOf(t));
  return STUFEN[und ? Math.max(...rang) : Math.min(...rang)];
}

/** Zerlegt einen Ausdruck mit OR, AND und Klammern (SPDX: AND bindet stärker); "or" in Worten gilt ebenso, eine Klammer
 *  nach Worten gehört zum Namen, etwa "GNU General Public License v3 (GPLv3)" */
function bewerte(zeichen: string[]): Strenge {
  let stelle = 0;
  const oder = (): Strenge => {
    const teile = [und()];
    while (/^or$/i.test(zeichen[stelle] ?? "")) {
      stelle++;
      teile.push(und());
    }
    return teile.length > 1 ? verknuepft(teile, false) : teile[0];
  };
  const und = (): Strenge => {
    const teile = [eines()];
    while (/^and$/i.test(zeichen[stelle] ?? "")) {
      stelle++;
      teile.push(eines());
    }
    return teile.length > 1 ? verknuepft(teile, true) : teile[0];
  };
  const eines = (): Strenge => {
    if (zeichen[stelle] === "(") {
      stelle++;
      const innen = oder();
      if (zeichen[stelle] === ")") stelle++;
      return innen;
    }
    const worte: string[] = [];
    for (let tiefe = 0; stelle < zeichen.length; stelle++) {
      const z = zeichen[stelle];
      if (tiefe === 0 && (z === ")" || /^(?:or|and)$/i.test(z))) break;
      tiefe += z === "(" ? 1 : z === ")" ? -1 : 0;
      worte.push(z);
    }
    return einzeln(worte.join(" "));
  };
  return oder();
}

/** gut: frei nutzbar, warn: schwaches, schlecht: starkes Copyleft, leer: eigene oder unbekannte Lizenz */
export function strenge(lizenz: string): Strenge {
  return bewerte(lizenz.split(/(\(|\)|\s+)/).filter((z) => z.trim()));
}
