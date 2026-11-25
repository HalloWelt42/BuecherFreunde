<script lang="ts">
  import Symbol from "./Symbol.svelte";
  // Mit onwahl bedienbar: derselbe Stern noch einmal nimmt die Bewertung zurück
  let { wert, onwahl = undefined }: { wert: number; onwahl?: (n: number) => void } = $props();
  const stufen = [1, 2, 3, 4, 5];
</script>

{#if onwahl}
  <span class="sterne waehlbar" role="group" aria-label="Bewertung, {wert} von 5 Sternen">
    {#each stufen as n (n)}
      <button type="button" aria-label="{n} {n === 1 ? 'Stern' : 'Sterne'}" aria-pressed={n === wert} title={n === wert ? "Bewertung zurücknehmen" : `${n} von 5 Sternen`} onclick={() => onwahl(n === wert ? 0 : n)}><Symbol name="star" klasse={n > wert ? "leer" : ""} /></button>
    {/each}
  </span>
{:else}
  <span class="sterne" role="img" aria-label="{wert} von 5 Sternen">{#each stufen as n (n)}<Symbol name="star" klasse={n > wert ? "leer" : ""} />{/each}</span>
{/if}
