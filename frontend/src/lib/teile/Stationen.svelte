<script lang="ts">
  // Die Stationen einer Aufnahme als Balken; welche es gibt, hängt davon ab, was angeschlossen ist
  import { stationsnamen, type Station } from "../annahme/zeilen";
  import { anschluesse } from "../stand/anschluesse.svelte";
  let { stationen, prozent }: { stationen: Station[]; prozent: number } = $props();
  let namen = $derived(stationsnamen(anschluesse.jetzt));
  let gezeigt = $derived(stationen.slice(0, namen.length));
</script>

{#if gezeigt.length}
  <div class="weg" style:--p="{prozent}%" role="img" aria-label={gezeigt.map((s, n) => `${namen[n]} ${s}`).join(", ")}>
    {#each gezeigt as s, n (n)}<span class={s === "offen" ? "" : s} title={namen[n]}></span>{/each}
  </div>
{/if}
