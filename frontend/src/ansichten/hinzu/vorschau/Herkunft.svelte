<script lang="ts">
  // Woher ein Vorschlag kommt (BF-80): kleines Zeichen hinter dem Wert, als Text mit Namen in Fenstern
  import { HERKUNFT } from "../../../lib/annahme/vorschau";
  import type { Herkunft } from "../../../lib/annahme/vorschautypen";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  let { herkunft, mitText = false }: { herkunft: Herkunft | null; mitText?: boolean } = $props();
  let h = $derived(herkunft ? HERKUNFT[herkunft] : null);
</script>

{#if h}
  {#if mitText}
    <span class="hktext" class:du={herkunft === "nutzer"}><Symbol name={h.symbol} />{h.name}</span>
  {:else}
    <span class="hk" class:du={herkunft === "nutzer"} title={h.name}><Symbol name={h.symbol} /><span class="nur-vorlesen">{h.name}</span></span>
  {/if}
{/if}
