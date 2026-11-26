<script lang="ts">
  // Fassungen eines Buchs als abgerundete Flaggenlabels (BF-71, Entwurf Abschnitt 1): das gewählte bestimmt, was "Lesen"
  // öffnet. Ein englisches Buch ohne deutsche Fassung bekommt das Label "Ins Deutsche übersetzen" mit Rückfrage.
  import Flagge from "../../lib/teile/Flagge.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import { labeltext } from "../../lib/uebersetzung/texte";
  import { uebersetzbar, type Buchfassungen } from "./fassungen.svelte";
  import Uebersetzungsfrage from "./Uebersetzungsfrage.svelte";

  let { buch, fassungen }: { buch: BuchEinzeln; fassungen: Buchfassungen } = $props();

  let fragt = $state(false);
  let neu = $derived(uebersetzbar(buch, fassungen.liste));
  // Nur das Original allein braucht kein Label
  let zeigen = $derived(fassungen.liste.length > 1 || neu);
</script>

{#if zeigen}
  <div class="fassungen" role="group" aria-label="Fassungen">
    {#each fassungen.liste as f (f.id ?? "original")}
      {@const t = labeltext(f, buch.page_count)}
      <button class="flaggenlabel" class:laeuft={f.stand === "laeuft" && !f.original} type="button" aria-pressed={f.gewaehlt} disabled={fassungen.waehlt} onclick={() => void fassungen.waehle(f)}>
        <Flagge sprache={f.sprache} /><span><b>{t.name}</b><small>{t.stand}</small></span>
      </button>
    {/each}
    {#if neu}
      <button class="flaggenlabel neu" type="button" onclick={() => (fragt = true)}>
        <Flagge sprache="de" /><span><b>Ins Deutsche übersetzen</b><small>noch nicht auf Deutsch</small></span>
      </button>
    {/if}
  </div>
{/if}

{#if fragt}
  <Uebersetzungsfrage {buch} onschliessen={() => (fragt = false)} ongestartet={() => { fragt = false; void fassungen.laden(); }} />
{/if}
