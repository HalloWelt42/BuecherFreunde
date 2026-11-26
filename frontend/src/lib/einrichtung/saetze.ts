// Sätze der Einrichtung (BF-82), ohne Oberfläche: Zeilen der Sicherungen, Folgen vor dem Wiederherstellen, Übernehmen und dem
// Schalter "Persönliches in der Kellerwolke", Zahlen der Aufträge. Was es nicht gibt, steht nicht da.
import type { Aenderung, Auftragsstand, Auftragsteil, Persoenlichfolgen, Sicherung, Wiederherstellfolgen } from "../api/einrichtung";
import { anzahl, datumZeit, groesse, vonGesamt, zahl, zeitpunkt } from "../format";

/** "26.11.2026, 03:00, 184 MB, 4.731 Bücher, 4 Profile" */
export function sicherungszeile(s: Sicherung): string {
  return [
    datumZeit(s.angelegt_am),
    s.groesse ? groesse(s.groesse) : "",
    s.buecher === null ? "" : anzahl(s.buecher, "Buch", "Bücher"),
    s.profile === null ? "" : anzahl(s.profile, "Profil", "Profile"),
  ].filter(Boolean).join(", ");
}

const punkt = (satz: string) => (/[.!?]$/.test(satz) ? satz : `${satz}.`);

/**
 * Folgen vor dem Einspielen: was kommt, was ersetzt wird, was bleibt. `laufend`: Zurückspielen auf einer eingerichteten
 * Installation, dort ersetzt die Sicherung den Bestand.
 */
export function wiederherstellfolgen(f: Wiederherstellfolgen, laufend = false): string[] {
  return [
    "Bestand, Einstellungen, Profile, Notizen und Lesestände kommen aus der Sicherung.",
    laufend ? "Die Originale bleiben, wo sie sind." : "Die Originale bleiben, wo sie sind. Danach prüft die App jedes einzelne.",
    ...(f.ersetzt.length ? f.ersetzt.map(punkt) : ["Hier liegt noch nichts: Es wird nichts überschrieben und nichts gelöscht."]),
    // Nennt der Server die Sicherung davor schon, steht sie nur einmal da
    ...(f.vorher_sichern && !f.ersetzt.some((e) => e.startsWith("Vorher")) ? ["Vorher entsteht eine Sicherung des jetzigen Stands im Sicherungsordner."] : []),
    ...(f.vorher_sichern ? ["Gelöscht wird nichts."] : []),
  ];
}

/** Was "Übernehmen" unter Wartung tut: jede angehakte Änderung, dann was bleibt */
export function uebernehmensfolgen(gewaehlt: readonly Aenderung[]): string[] {
  return [...gewaehlt.map((a) => punkt(a.was)), "Alles andere bleibt, wie es ist. Gelöscht wird nichts."];
}

/** "Zwei Änderungen übernehmen?" bis zwölf in Worten, darüber als Zahl */
const WORTE = ["Keine", "Eine", "Zwei", "Drei", "Vier", "Fünf", "Sechs", "Sieben", "Acht", "Neun", "Zehn", "Elf", "Zwölf"];
export function aenderungenZahl(n: number): string {
  return `${WORTE[n] ?? zahl(n)} ${n === 1 ? "Änderung" : "Änderungen"}`;
}

/** "2.934 von 4.731 geprüft"; ohne Gesamtzahl nur, was fertig ist */
export function auftragszahl(a: Pick<Auftragsstand, "fertig" | "gesamt">, wort: string): string {
  return a.gesamt ? `${vonGesamt(a.fertig, a.gesamt)} ${wort}` : `${zahl(a.fertig)} ${wort}`;
}

export function teilzahl(t: Auftragsteil): string {
  return t.gesamt ? vonGesamt(t.fertig, t.gesamt) : zahl(t.fertig);
}

/** Das Teil eines Auftrags, 0 wenn es fehlt */
export function teilwert(a: Auftragsstand | null, schluessel: string): number {
  return a?.teile.find((t) => t.schluessel === schluessel)?.fertig ?? 0;
}

export const laeuftNoch = (a: Auftragsstand | null): boolean => !!a && ["wartet", "laeuft", "pause"].includes(a.stand);

/** "bis 20:46 Uhr, für einen Umzug" */
export function umzugGilt(bis: string | null): string {
  const d = zeitpunkt(bis);
  return d ? `bis ${d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })} Uhr, für einen Umzug` : "für einen Umzug";
}

/** "12 Lesestände, 3 Notizen" aus den Zahlen der Folgen; leer, wenn nichts da ist */
function inhalt(f: Persoenlichfolgen): string {
  const teile: [number, string, string][] = [
    [f.lesestaende, "Lesestand", "Lesestände"],
    [f.vorlesestellen, "Vorlesestelle", "Vorlesestellen"],
    [f.notizen, "Notiz", "Notizen"],
    [f.markierungen, "Markierung", "Markierungen"],
    [f.etiketten, "Etikett", "Etiketten"],
    [f.private, "Buch nur für ein Profil", "Bücher nur für ein Profil"],
    [f.freigaben, "Freigabe", "Freigaben"],
  ];
  return teile.filter(([n]) => n).map(([n, eins, viele]) => anzahl(n, eins, viele)).join(", ");
}

/** Vor dem Einschalten: was in die Kellerwolke geschrieben wird */
export function persoenlichEinFolgen(f: Persoenlichfolgen): string[] {
  const was = inhalt(f);
  return [
    f.buecher
      ? `${anzahl(f.buecher, "Buch bekommt", "Bücher bekommen")} in der Kellerwolke eine kleine Datei mit dem Persönlichen je Profil${was ? `: ${was}` : ""}.`
      : "Noch hat kein Buch Persönliches; jede neue Notiz, Markierung und jeder Lesestand kommt danach dazu.",
    `Dazu die Datei der Profile ${f.profile_datei}, ohne PIN und Bild-PIN.`,
    "Wer die Kellerwolke verwaltet, könnte es lesen. In der App bleibt alles, wie es ist.",
  ];
}

/** Vor dem Ausschalten: was bleibt; ob die Dateien in den Papierkorb gehen, wählt man darunter */
export function persoenlichAusFolgen(f: Persoenlichfolgen): string[] {
  return [
    "Neue Lesestände, Notizen und Markierungen gehen nicht mehr in die Kellerwolke.",
    f.buecher
      ? `Die vorhandenen ${anzahl(f.buecher, "Datei", "Dateien")} und die Datei der Profile bleiben dort, außer du legst sie unten in den Papierkorb.`
      : "In der Kellerwolke liegt dazu nur die Datei der Profile.",
    "In der App bleibt alles, wie es ist.",
  ];
}

export function papierkorbText(f: Persoenlichfolgen): string {
  return `${f.buecher ? `${anzahl(f.buecher, "Datei", "Dateien")} und die` : "Die"} Datei der Profile in den Papierkorb der Kellerwolke (dort zurückzuholen)`;
}
