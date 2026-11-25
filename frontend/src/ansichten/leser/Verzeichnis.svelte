<script lang="ts">
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  let { sitzung }: { sitzung: Lesesitzung } = $props();

  function zeige(knoten: HTMLElement) {
    knoten.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: "center" });
  }
</script>

<h2>Inhalt</h2>
<div use:zeige>
  {#each sitzung.kapitel as k, n (n)}
    <button type="button" class="punkt" style:padding-left="{0.5 + k.tiefe * 0.875}rem" aria-pressed={n === sitzung.kapitelJetzt} onclick={() => { sitzung.griffe?.zumKapitel(k); if (schale.telefon) sitzung.feld = ""; }}>
      <span class="name">{k.titel}</span>{#if k.marke}<span class="zahl">{k.marke}</span>{/if}
    </button>
  {/each}
</div>
