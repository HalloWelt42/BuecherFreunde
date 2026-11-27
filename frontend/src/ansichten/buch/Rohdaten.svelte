<script lang="ts">
  // Alles, was das Verzeichnis geliefert hat; Listen lassen sich als Regale übernehmen
  import { anzahl } from "../../lib/format";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import { alsListe } from "./angaben";

  let { daten, gewaehlt, onwahl }: { daten: Record<string, unknown>; gewaehlt: string[]; onwahl: (name: string, an: boolean) => void } = $props();
  let offen = $state(false);
  let eintraege = $derived(Object.entries(daten));
</script>

<div class="reihe"><Knopf text="Alle Daten, {anzahl(eintraege.length, 'Feld', 'Felder')}" symbol={offen ? "chevron-down" : "chevron-right"} klein frei aufgeklappt={offen} onclick={() => (offen = !offen)} /></div>
{#if offen}
  <dl class="angaben roh">
    {#each eintraege as [name, wert] (name)}
      <dt>{name}</dt>
      <dd>
        {#if alsListe(wert).length}
          {alsListe(wert).join(", ")}
          <Haekchen text="als Regale" an={gewaehlt.includes(name)} onwahl={(an) => onwahl(name, an)} />
        {:else if typeof wert === "object" && wert !== null}<code>{JSON.stringify(wert)}</code>
        {:else}{String(wert)}{/if}
      </dd>
    {/each}
  </dl>
{/if}

<style>
  .roh {
    max-height: 20rem;
    overflow: auto;
    font-size: 0.875rem;
  }
  code {
    font-family: var(--codeschrift);
    font-size: 0.8125rem;
  }
  dd :global(.haekchen) {
    display: flex;
  }
</style>
