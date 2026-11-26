// Ein Buch löschen (BF-60): die Folgen kommen vom Server, die Sätze entstehen hier; erst ein Ja in der Rückfrage löst aus
import { loescheBuch, loeschfolgen } from "../../lib/api/books";
import { groesse, zahl } from "../../lib/format";
import { navigate } from "../../lib/router.svelte";
import { bestand } from "../../lib/stand/bestand.svelte";
import { buecher } from "../../lib/stand/buecher.svelte";
import { filter } from "../../lib/stand/filter.svelte";
import { melde } from "../../lib/stand/meldungen.svelte";
import { frage } from "../../lib/stand/rueckfrage.svelte";
import { wahl } from "../../lib/stand/wahl.svelte";
import type { Loeschfolgen } from "../../lib/typen";

const anzahl = (n: number, eins: string, mehr: string) => `${zahl(n)} ${n === 1 ? eins : mehr}`;

function aufzaehlung(teile: string[]): string {
  return teile.length < 2 ? (teile[0] ?? "") : `${teile.slice(0, -1).join(", ")} und ${teile.at(-1)}`;
}

/** Nur die Folgen, die es bei diesem Buch gibt, als ganze Sätze */
export function folgensaetze(f: Loeschfolgen): string[] {
  const aus: string[] = [];
  const eigenes = [
    f.notizen && anzahl(f.notizen, "Notiz", "Notizen"),
    f.markierungen && anzahl(f.markierungen, "Markierung", "Markierungen"),
    f.etiketten && anzahl(f.etiketten, "Etikett", "Etiketten"),
  ].filter((t): t is string => !!t);
  const einzeln = eigenes.length === 1 && f.notizen + f.markierungen + f.etiketten === 1;
  if (eigenes.length) aus.push(`${aufzaehlung(eigenes)} ${einzeln ? "geht" : "gehen"} verloren.`);
  if (f.lesestand && f.vorlesestelle) aus.push("Der Lesestand und die Stelle, an der das Vorlesen stehen blieb, gehen verloren.");
  else if (f.lesestand) aus.push("Der Lesestand geht verloren.");
  else if (f.vorlesestelle) aus.push("Die Stelle, an der das Vorlesen stehen blieb, geht verloren.");
  if (f.regale) aus.push(`Das Buch fehlt danach in ${anzahl(f.regale, "Regal", "Regalen")}.`);
  if (f.datei?.papierkorb) aus.push(`Die Datei kommt in den Papierkorb der Kellerwolke und lässt sich dort zurückholen: ${f.datei.pfad}, ${groesse(f.datei.groesse)}.`);
  else if (f.datei) aus.push(`Die Datei liegt nur auf diesem Gerät und ist danach fort: ${f.datei.pfad}, ${groesse(f.datei.groesse)}.`);
  if (f.abschnitte) aus.push(`Die Suche nach Bedeutung vergisst das Buch (${anzahl(f.abschnitte, "Abschnitt", "Abschnitte")}).`);
  return aus;
}

/** Fragt mit allen Folgen nach und löscht erst nach dem Ja; danach zurück in die Bibliothek, wie sie zuletzt war */
export async function buchLoeschen(id: number): Promise<boolean> {
  let f: Loeschfolgen;
  try {
    f = await loeschfolgen(id);
  } catch (e) {
    melde.schlecht(e, "Folgen nicht ermittelt, nichts gelöscht");
    return false;
  }
  const ja = await frage({ titel: "Buch löschen?", text: [f.titel, f.autor].filter(Boolean).join(", "), folgen: folgensaetze(f), ja: "Löschen" });
  if (!ja) return false;
  try {
    await loescheBuch(id);
  } catch (e) {
    melde.schlecht(e);
    return false;
  }
  melde.gut(f.datei?.papierkorb ? `${f.titel} gelöscht. Die Datei liegt im Papierkorb der Kellerwolke.` : `${f.titel} gelöscht.`);
  wahl.vergiss(id);
  buecher.entferne(id);
  void bestand.laden();
  navigate(filter.letzteAdresse, true);
  return true;
}
