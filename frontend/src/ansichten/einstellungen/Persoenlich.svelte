<script lang="ts">
  // Schalter "Persönliches in der Kellerwolke" (BF-82): Notizen, Markierungen, Etiketten, Lesestand und Freigaben je Buch und
  // Profil zusätzlich als kleine Datei neben dem Original, dazu die Datei der Profile, damit ein Neuaufbau sie zurückholt.
  // Ein- und Ausschalten erst nach der Folgenvorschau; ausgeschaltet bleibt in der Kellerwolke alles, außer man legt die
  // Dateien ausdrücklich in ihren Papierkorb. In der App bleibt immer alles.
  import { ApiError } from "../../lib/api/client";
  import { ladeKellerwolkeneinstellungen, ladePersoenlichfolgen, setzePersoenlich } from "../../lib/api/einrichtung";
  import { papierkorbText, persoenlichAusFolgen, persoenlichEinFolgen } from "../../lib/einrichtung/saetze";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Schalter from "../../lib/teile/Schalter.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";

  let an = $state<boolean | null>(null);
  let laeuft = $state(false);

  $effect(() => {
    ladeKellerwolkeneinstellungen().then((e) => (an = e.persoenlich)).catch(() => {});
  });

  async function schalte(neu: boolean) {
    laeuft = true;
    try {
      for (;;) {
        const f = await ladePersoenlichfolgen();
        let entfernen = false;
        const ja = await frage(
          neu
            ? { titel: "Persönliches in der Kellerwolke einschalten?", folgen: persoenlichEinFolgen(f), ja: "Einschalten", symbol: "cloud-arrow-up", gefahr: false }
            : {
                titel: "Persönliches in der Kellerwolke ausschalten?",
                folgen: persoenlichAusFolgen(f),
                wahl: { text: papierkorbText(f), an: false, onwahl: (w) => (entfernen = w) },
                ja: "Ausschalten",
                symbol: "power-off",
                gefahr: false,
              },
        );
        if (!ja) return;
        try {
          an = (await setzePersoenlich(neu, f.stand, entfernen)).persoenlich;
          melde.gut(neu ? "Eingeschaltet, die Dateien entstehen nach und nach" : entfernen ? "Ausgeschaltet, die Dateien liegen im Papierkorb der Kellerwolke" : "Ausgeschaltet");
          return;
        } catch (e) {
          // Seit der Vorschau hat sich etwas geändert: die neuen Folgen zeigen und erneut fragen
          if (e instanceof ApiError && e.status === 409) {
            melde.info("Seither hat sich etwas geändert, hier die neuen Folgen");
            continue;
          }
          throw e;
        }
      }
    } catch (e) {
      melde.schlecht(e, "Nicht geschaltet");
    } finally {
      laeuft = false;
    }
  }
</script>

{#if an !== null}
  <div class="wegzeile">
    <Symbol name="user-pen" />
    <span>Persönliches in der Kellerwolke<small>Notizen, Markierungen, Etiketten, Lesestand und Freigaben je Buch und Profil, damit ein Neuaufbau sie zurückholt. Wer die Kellerwolke verwaltet, könnte sie lesen.</small></span>
    <Schalter {an} name="Persönliches in der Kellerwolke" gesperrt={laeuft} onwahl={(w) => void schalte(w)} />
  </div>
{/if}
