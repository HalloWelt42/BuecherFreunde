<script lang="ts">
  import type { Suchvorschlag as Vorschlag } from "../api/search";
  import { suche } from "../stand/suche.svelte";
  import Auszug from "../teile/Auszug.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Symbol from "../teile/Symbol.svelte";

  let { verlauf, vorschlaege, gewaehlt, onsuche, onoeffne }: { verlauf: string[] | null; vorschlaege: Vorschlag[]; gewaehlt: number; onsuche: (wort: string) => void; onoeffne: (v: Vorschlag) => void } = $props();
</script>

<div class="liste glas dicht">
  {#if verlauf}
    <div class="reihe kopfzeile"><span class="leise">Zuletzt gesucht</span><span class="schiebt"><Knopf text="Verlauf löschen" symbol="trash" klein frei onclick={() => suche.leere()} /></span></div>
    {#each verlauf as wort, n (wort)}
      <div class="eintrag" class:gewaehlt={n === gewaehlt}>
        <button type="button" class="haupt" onclick={() => onsuche(wort)}><Symbol name="clock-rotate-left" /><span>{wort}</span></button>
        <Knopf text="Aus dem Verlauf nehmen" symbol="xmark" nur klein frei onclick={() => suche.vergiss(wort)} />
      </div>
    {/each}
  {:else}
    {#each vorschlaege as v, n (v.id)}
      <div class="eintrag" class:gewaehlt={n === gewaehlt}>
        <button type="button" class="haupt" onclick={() => onoeffne(v)}><Symbol name="book" /><span><Auszug text={v.titel} /><br /><span class="leise"><Auszug text={v.autor} /></span></span></button>
      </div>
    {/each}
  {/if}
</div>

<style>
  .liste {
    position: absolute;
    z-index: 45;
    top: calc(100% + 6px);
    left: 0;
    right: 0;
    max-height: min(26rem, 60vh);
    overflow: auto;
    padding: 0.375rem;
  }
  .kopfzeile {
    padding: 0 0.25rem 0.25rem 0.5rem;
  }
  .eintrag {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    border-radius: var(--r2);
  }
  .eintrag:hover,
  .eintrag.gewaehlt {
    background: var(--messing-hauch);
  }
  .haupt {
    display: grid;
    grid-template-columns: 1.25rem minmax(0, 1fr);
    gap: 0.5rem;
    align-items: center;
    min-height: 2.5rem;
    padding: 0.25rem 0.5rem;
    overflow-wrap: anywhere;
  }
</style>
