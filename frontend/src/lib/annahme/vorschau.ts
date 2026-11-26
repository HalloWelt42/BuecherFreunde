// Was die Vorschau (BF-80) aus der Antwort des Servers zeigt, ohne Oberfläche: Herkunft je Feld, Filter und Zahlen, Fuß,
// Wahl beim Doppel, Zeichen einer Datei, Folgen des Verwerfens. Die Ansicht steht in ansichten/hinzu/vorschau.
import { anzahl, groesse } from "../format";
import type { Annahmestand, Vorschaukurz } from "./typen";
import type { Doppel, Doppelwahl, Herkunft, Verwerffolgen, Vorschau, Vorschauart, Vorschauzaehler, Vorschauzeile } from "./vorschautypen";

/** Zeichen und Name je Herkunft, in der Reihenfolge der Legende */
export const HERKUNFT: Record<Herkunft, { symbol: string; name: string }> = {
  regel: { symbol: "ruler-combined", name: "Regel" },
  ki: { symbol: "robot", name: "KI" },
  ordner: { symbol: "folder", name: "Ordner" },
  datei: { symbol: "file-lines", name: "Datei" },
  luecke: { symbol: "puzzle-piece", name: "Lücke" },
  bestand: { symbol: "book-bookmark", name: "Bestand" },
  nutzer: { symbol: "user-pen", name: "von dir" },
};
export const LEGENDE = Object.keys(HERKUNFT) as Herkunft[];

/** Arten unter Besonderes (BF-77), wie am Server (models/book.py) */
export const BESONDERES = ["dokument", "heft", "katalog", "broschuere", "anleitung"] as const;
export const istBesonderes = (art: string): boolean => (BESONDERES as readonly string[]).includes(art);

/** Wird noch hochgeladen, gelesen oder ausgepackt */
const IN_ARBEIT: readonly Annahmestand[] = ["wartet", "laedt", "angehalten", "liest", "angaben", "entpacken"];
export const laeuftNoch = (z: Pick<Vorschauzeile, "stand">): boolean => IN_ARBEIT.includes(z.stand);
/** Wartet auf die Bestätigung; nur dann lässt sich die Zuordnung ändern */
export const wartet = (z: Pick<Vorschauzeile, "stand">): boolean => z.stand === "bestaetigen";
export const aenderbar = (z: Pick<Vorschauzeile, "stand">): boolean => wartet(z) || laeuftNoch(z);

export type Vorschaufilter = "alle" | "buecher" | "besonderes" | "material" | "doppel";
export const FILTER: [Vorschaufilter, string][] = [["alle", "Alle"], ["buecher", "Bücher"], ["besonderes", "Besonderes"], ["material", "Material"], ["doppel", "Doppel"]];

/** Die Liste oben: Werke, Material und Doppel, dazu was noch läuft; die ZIP selbst steht im Kopf, der Rest darunter */
export const inDerListe = (z: Vorschauzeile): boolean => z.rolle === "buch" || z.rolle === "material" || z.rolle === "doppel" || (z.rolle !== "zip" && laeuftNoch(z));
export const nichtUebernommen = (z: Vorschauzeile): boolean => z.rolle === "rest" && !laeuftNoch(z);

export function passt(z: Vorschauzeile, f: Vorschaufilter): boolean {
  const art = z.felder?.art.wert ?? "";
  if (f === "alle") return true;
  if (f === "material") return z.rolle === "material";
  if (f === "doppel") return z.rolle === "doppel" || (!!z.felder && z.felder.doppel.art !== "neu");
  if (f === "besonderes") return z.rolle !== "material" && istBesonderes(art);
  return z.rolle !== "material" && art === "buch";
}

export function filterzahlen(zeilen: readonly Vorschauzeile[]): Record<Vorschaufilter, number> {
  const liste = zeilen.filter(inDerListe);
  return Object.fromEntries(FILTER.map(([f]) => [f, liste.filter((z) => passt(z, f)).length])) as Record<Vorschaufilter, number>;
}

/** "Werkstatt-Ablage.zip, 14 Dateien, 41,8 MB" */
export function kopfzeile(v: Pick<Vorschaukurz, "name" | "dateien" | "groesse">): string {
  const zahl = anzahl(v.dateien, "Datei", "Dateien");
  return [v.name === zahl ? "" : v.name, zahl, groesse(v.groesse)].filter(Boolean).join(", ");
}

/** "11 übernehmen, 1 weglassen, 2 nicht übernommen" */
export function fusstext(z: Vorschauzaehler): string {
  return [`${z.uebernehmen} übernehmen`, z.weglassen ? `${z.weglassen} weglassen` : "", z.nicht ? `${z.nicht} nicht übernommen` : ""].filter(Boolean).join(", ");
}

/** Was beim Doppel zur Wahl steht; die gewählte immer dabei. Dieselbe Datei gibt es nur einmal: nur Weglassen. */
export function doppelwerte(d: Doppel): [Doppelwahl, string][] {
  const namen: Record<Doppelwahl, string> = { neu: "Neu", weglassen: "Weglassen", format: "Weiteres Format", eigenes: "Als eigenes Buch" };
  const grund: Doppelwahl[] = d.art === "gleich" ? ["weglassen"] : d.art === "format" ? ["format", "eigenes"] : ["neu", "weglassen"];
  const werte = grund.includes(d.wahl) ? grund : [...grund, d.wahl];
  return werte.map((w) => [w, namen[w]]);
}

/** Welche Wahl beim Doppel für alle angehakten Dateien geht (der Server prüft dasselbe) */
export function doppelFuerAlle(zeilen: readonly Vorschauzeile[]): Record<Doppelwahl, boolean> {
  const d = zeilen.map((z) => z.felder?.doppel).filter((x): x is Doppel => !!x);
  const da = d.length === zeilen.length && d.length > 0;
  return {
    weglassen: da,
    eigenes: da && d.every((x) => x.art !== "gleich"),
    format: da && d.every((x) => x.art === "format"),
    neu: da && d.every((x) => x.art === "neu"),
  };
}

/** Zeichen, Wort und Unterart einer Zeile; die Namen der Arten kommen vom Server (stand/arten) */
export function artAnzeige(art: string, typName: (id: string) => string): { symbol: string; text: string; klein: string } {
  if (art === "material") return { symbol: "paperclip", text: "Material", klein: "" };
  if (art === "buch") return { symbol: "book", text: "Buch", klein: "" };
  if (istBesonderes(art)) return { symbol: "shapes", text: "Besonderes", klein: typName(art) };
  return { symbol: "circle-question", text: "Offen", klein: "" };
}

export const ARTWAHL: Vorschauart[] = ["buch", ...BESONDERES];

/** Der Teil eines Namens nach dem des Buchs, zu dem die Datei gehört: "Holz - Schaltpläne.pdf" zu "Holz.pdf" ist "Schaltpläne" */
export function zusatz(name: string, zu: string): string {
  const stamm = (n: string) => n.replace(/\.[^./]+$/, "");
  const eigener = stamm(name);
  const vorn = stamm(zu);
  if (!vorn || !eigener.toLowerCase().startsWith(vorn.toLowerCase())) return "";
  return eigener.slice(vorn.length).replace(/^[\s\-_.([\]]+|[\s)\]]+$/g, "");
}

/** Endung groß, etwa "PNG" */
export const endung = (name: string): string => (/\.([^./]+)$/.exec(name)?.[1] ?? "").toUpperCase();

const ZEICHEN: [RegExp, string][] = [
  [/\.pdf$/i, "file-pdf"], [/\.(epub|mobi|azw3)$/i, "book"], [/\.(zip|tar|gz|tgz|bz2|xz|7z|rar)$/i, "file-zipper"],
  [/\.(jpe?g|png|gif|webp|svg|avif)$/i, "file-image"], [/\.(mp3|ogg|oga|opus|wav|m4a|flac|aac)$/i, "file-audio"],
  [/\.(mp4|webm|mkv|mov|m4v)$/i, "file-video"], [/\.(csv|tsv|xlsx?|ods)$/i, "table-cells"], [/\.(docx?|odt|rtf)$/i, "file-word"],
  [/\.(pptx?|odp|key)$/i, "file-powerpoint"], [/\.(txt|md|markdown)$/i, "file-lines"],
  [/\.(py|js|ts|c|h|cpp|hpp|java|kt|rs|go|rb|php|sh|ino|html|css|json|xml|ya?ml|toml|sql|ipynb)$/i, "file-code"],
];

/** Zeichen einer Datei ohne Umschlag nach ihrer Endung */
export const dateizeichen = (name: string): string => ZEICHEN.find(([m]) => m.test(name))?.[1] ?? "file";

/** Hat jemand in dieser Vorschau schon etwas von Hand zugeordnet? Dann geht es beim Verwerfen verloren. */
export function vonHand(v: Pick<Vorschau, "zeilen">): boolean {
  return v.zeilen.some((z) => {
    const f = z.felder;
    if (!f) return false;
    return [f.art, f.kategorien, f.etiketten, f.sammlung, f.band, f.sprache, f.doppel].some((w) => w.herkunft === "nutzer");
  });
}

const zaehle = (n: number, alle: number, eins: string, mehr: string) => (n === alle && n > 1 ? `Alle ${n} ${mehr}` : anzahl(n, eins, mehr));

/** Die Folgen des Verwerfens als ganze Sätze, nur was es gibt */
export function verwerfsaetze(f: Verwerffolgen, mitHand: boolean): string[] {
  const mit = f.dateien.filter((d) => d.wirkung !== "nichts").length;
  const aus: string[] = [];
  if (f.papierkorb) aus.push(`${zaehle(f.papierkorb, mit, "Datei", "Dateien")} ${f.papierkorb === 1 ? "kommt" : "kommen"} in den Papierkorb der Kellerwolke und ${f.papierkorb === 1 ? "lässt" : "lassen"} sich dort zurückholen.`);
  if (f.endgueltig) aus.push(`${zaehle(f.endgueltig, mit, "Datei", "Dateien")} ${f.endgueltig === 1 ? "wird" : "werden"} auf diesem Gerät endgültig gelöscht und ${f.endgueltig === 1 ? "lässt" : "lassen"} sich nicht zurückholen.`);
  if (f.bleibt) aus.push(`${zaehle(f.bleibt, mit, "Datei", "Dateien")} ${f.bleibt === 1 ? "bleibt" : "bleiben"} im Ordner, wo ${f.bleibt === 1 ? "sie liegt" : "sie liegen"}.`);
  aus.push("Ins Regal kommt nichts, im Bestand ändert sich nichts.");
  if (mitHand) aus.push("Deine Änderungen an der Zuordnung gehen verloren.");
  return aus;
}

/** Jede Datei mit ihrem Ordner in der ZIP, unter dem Ort, an dem alle liegen (gemeinsamer Ordner ihrer Pfade) */
export function verwerfliste(f: Verwerffolgen): { titel: string; eintraege: string[] } {
  const dateien = f.dateien.filter((d) => d.wirkung !== "nichts");
  const ordner = dateien.map((d) => d.pfad.split("/").slice(0, -1));
  let gemeinsam = ordner[0] ?? [];
  for (const o of ordner) {
    let n = 0;
    while (n < gemeinsam.length && n < o.length && gemeinsam[n] === o[n]) n++;
    gemeinsam = gemeinsam.slice(0, n);
  }
  return { titel: gemeinsam.join("/"), eintraege: dateien.map((d) => [d.ordner, d.name].filter(Boolean).join("/")) };
}

/** Wohin die Datei kommt, als Satz für die Angaben */
export function ablagetext(a: Vorschauzeile["ablage"]): string {
  if (!a) return "";
  const pfad = [a.ordner, a.name].filter(Boolean).join("/");
  return a.ort === "kellerwolke" ? `Kellerwolke, ${pfad}` : a.ort === "geraet" ? `Auf diesem Gerät, ${pfad}` : `Bleibt liegen, ${a.ordner}`;
}
