<script lang="ts">
  // Zeichen für ein Regal wählen
  import { findeSymbole, symbole } from "./symbole";
  import Knopf from "./Knopf.svelte";
  import Symbol from "./Symbol.svelte";

  let { wert, farbe = undefined, onwahl }: { wert: string; farbe?: string; onwahl: (name: string) => void } = $props();
  let wort = $state("");
  let passend = $derived(findeSymbole(wort));
</script>

<div class="symbolwahl">
  <div class="reihe">
    <input class="eingabe suche-symbol" type="search" placeholder="Symbol suchen ({symbole.length})" aria-label="Symbol suchen" bind:value={wort} />
    {#if wert}<Knopf text="Ohne Symbol" symbol="xmark" klein frei onclick={() => onwahl("")} />{/if}
  </div>
  <div class="gitter">
    {#each passend as [name, stichworte] (name)}
      <button type="button" aria-label={stichworte} title={stichworte} aria-pressed={wert === name} onclick={() => onwahl(name)}><Symbol {name} farbe={wert === name ? farbe : undefined} /></button>
    {:else}<p class="leise">Kein Symbol passt.</p>{/each}
  </div>
</div>

<style>
  .symbolwahl {
    display: grid;
    gap: 0.5rem;
    grid-template-columns: minmax(0, 1fr);
  }
  .suche-symbol {
    flex: 1;
    width: auto;
    min-width: 9rem;
  }
  .gitter {
    display: grid;
    gap: 0.25rem;
    grid-template-columns: repeat(auto-fill, minmax(2.25rem, 1fr));
    max-height: 11rem;
    overflow: auto;
    padding: 2px;
  }
  .gitter button {
    height: 2.25rem;
    display: grid;
    place-items: center;
    border-radius: var(--r1);
    color: var(--tinte-2);
  }
  .gitter button:hover {
    background: var(--hauch);
  }
  .gitter button[aria-pressed="true"] {
    background: var(--messing-hauch);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--messing) 50%, transparent);
  }
  .gitter p {
    grid-column: 1 / -1;
  }
</style>
