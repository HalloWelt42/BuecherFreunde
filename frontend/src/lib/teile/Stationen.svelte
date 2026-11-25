<script lang="ts">
  // Sechs Stationen einer Aufnahme als Balken
  import type { Station } from "../annahme/zeilen";
  let { stationen, prozent }: { stationen: Station[]; prozent: number } = $props();
  const namen = ["Prüfen", "Wolke", "Lesen", "Angaben", "Regal", "Wissen"];
</script>

{#if stationen.length}
  <div class="weg" style:--p="{prozent}%" role="img" aria-label={stationen.map((s, n) => `${namen[n]} ${s}`).join(", ")}>
    {#each stationen as s, n (n)}<span class={s === "offen" ? "" : s} title={namen[n]}></span>{/each}
  </div>
{/if}
