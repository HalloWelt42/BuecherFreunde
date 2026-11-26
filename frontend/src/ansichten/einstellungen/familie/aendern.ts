// Ein Profil im Elternbereich ändern (BF-78): die Änderung steht sofort da, kommt danach vom Server; geht sie schief, gilt
// wieder der alte Stand. Einstellungen gehen immer ganz an den Server (eigene Werte vor den Vorgaben der Stufe), damit er
// nichts zusammenfügen muss.
import { aendereProfil, type Profil, type Profilangaben, type Profileinstellungen } from "../../../lib/api/familie";
import { einstellungenVon } from "../../../lib/familie";
import { familie } from "../../../lib/stand/familie.svelte";
import { melde } from "../../../lib/stand/meldungen.svelte";

export async function aendere(p: Profil, angaben: Profilangaben): Promise<void> {
  const gesendet = { ...p, ...angaben, einstellungen: { ...p.einstellungen, ...angaben.einstellungen } } as Profil;
  familie.ersetze(gesendet);
  try {
    const antwort = await aendereProfil(p.id, angaben);
    familie.ersetze({ ...gesendet, ...antwort, einstellungen: antwort.einstellungen ?? gesendet.einstellungen });
  } catch (e) {
    familie.ersetze(p);
    melde.schlecht(e, "Nicht gespeichert");
  }
}

/** Ein Teil der Einstellungen eines Kindes, etwa die Lesezeit */
export function setze<B extends keyof Profileinstellungen>(p: Profil, bereich: B, teil: Partial<Profileinstellungen[B]>): Promise<void> {
  const jetzt = einstellungenVon(p, familie.stufen.stufen);
  return aendere(p, { einstellungen: { ...jetzt, [bereich]: { ...jetzt[bereich], ...teil } } });
}
