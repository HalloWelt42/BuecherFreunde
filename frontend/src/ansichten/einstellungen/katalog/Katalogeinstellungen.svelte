<script lang="ts">
  // Einstellungen des Katalogs (BF-69): Stapel, Bücher je Anfrage an die KI, vorab angehakt, Teilen im Vorschlag. Jedes Feld
  // speichert beim Verlassen, wie die Grenze der Sammlungen.
  import { ladeKatalogeinstellungen, speichereKatalogeinstellungen } from "../../../lib/api/katalog";
  import { zahl } from "../../../lib/format";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Karte from "../../../lib/teile/Karte.svelte";
  import type { Katalogeinstellungen } from "../../../lib/typen";
  import { EINSTELLUNGEN, einstellungAus, type Einstellung } from "./einstellungen";

  let werte = $state<Katalogeinstellungen | null>(null);
  let gespeichert: Katalogeinstellungen | null = null;

  $effect(() => {
    ladeKatalogeinstellungen()
      .then((e) => {
        werte = { ...e };
        gespeichert = e;
      })
      .catch(() => (werte = null));
  });

  async function speichere(feld: Einstellung) {
    if (!werte || !gespeichert) return;
    const n = einstellungAus(feld, werte[feld]);
    const grenzen = EINSTELLUNGEN.find(([f]) => f === feld)!;
    if (n === null) {
      melde.warn(`${grenzen[1]}: eine ganze Zahl von ${zahl(grenzen[2])} bis ${zahl(grenzen[3])}`);
      werte[feld] = gespeichert[feld];
      return;
    }
    if (n === gespeichert[feld]) return;
    try {
      gespeichert = await speichereKatalogeinstellungen({ ...gespeichert, [feld]: n });
      werte = { ...gespeichert };
      melde.gut("Gespeichert");
    } catch (e) {
      melde.schlecht(e, "Nicht gespeichert");
      werte[feld] = gespeichert[feld];
    }
  }
</script>

{#if werte}
  <Karte titel="Einstellungen des Katalogs" symbol="sliders" breit id="katalog-einstellungen">
    <div class="katalogeinstellungen">
      {#each EINSTELLUNGEN as [feld, name, von, bis] (feld)}
        <label class="feld">{name}<input class="eingabe zahl" type="number" min={von} max={bis} step="1" bind:value={werte[feld]} onchange={() => void speichere(feld)} /></label>
      {/each}
    </div>
  </Karte>
{/if}
