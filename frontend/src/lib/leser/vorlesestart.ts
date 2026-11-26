// Vorlesen aus dem offenen Buch starten, eine Stelle für das Feld Vorlesen und das Kontextmenü im Leser: welcher Umfang,
// ab wo, und das Werk für die Anzeige der Medien. Liest es aus dem Buch, merkt der Server die Stelle (BF-37).
import { coverUrl } from "../api/books";
import { melde } from "../stand/meldungen.svelte";
import { vorlesen } from "../stand/vorlesen.svelte";
import type { Buchquelle, Strecke } from "../vorlesen/typen";
import type { Lesesitzung } from "./sitzung.svelte";

export type Umfang = "seite" | "kapitel" | "hier" | "buch";

export async function strecke(quelle: Buchquelle, u: Umfang): Promise<Strecke | null> {
  if (u === "buch") return { von: { einheit: 0, zeichen: 0 }, bis: null };
  if (u === "hier") return { von: await quelle.hier(), bis: null };
  return u === "seite" ? quelle.seite() : quelle.kapitel();
}

/** Liest die Strecke aus dem Buch der Sitzung; ohne Strecke eine kurze Meldung. Erst entsperren, noch im Tippen. */
export function liesAus(sitzung: Lesesitzung, s: Strecke | null, name: string): void {
  const quelle = sitzung.quelle;
  if (!s || !quelle) return void melde.info("Hier gibt es nichts zum Vorlesen");
  const b = sitzung.buch;
  vorlesen.liesBuch(quelle, s, name, { titel: b.title, autor: b.authors.map((a) => a.name).join(", "), bild: coverUrl(b.id) }, b.id);
}

/** Ab der Stelle, an der man gerade liest */
export async function liesAbHier(sitzung: Lesesitzung): Promise<void> {
  vorlesen.entsperre();
  const quelle = sitzung.quelle;
  liesAus(sitzung, quelle ? await strecke(quelle, "hier") : null, "Ab hier");
}
