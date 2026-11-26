<script lang="ts">
  // Eine Kategorie des Katalogs suchen und wählen (BF-69), nach Bereichen geordnet. Verborgene stehen mit darin: wer ein Buch
  // einordnet, macht sie damit sichtbar.
  import { farbeVon } from "../katalog";
  import type { Katalogbereich, Katalogkategorie } from "../typen";
  import Katalogzeichen from "./Katalogzeichen.svelte";

  let { bereiche, ohne = [], onwahl }: { bereiche: readonly Katalogbereich[]; ohne?: number[]; onwahl: (kategorie: Katalogkategorie, bereich: Katalogbereich) => void } = $props();
  let suche = $state("");

  let gruppen = $derived.by(() => {
    const wort = suche.trim().toLocaleLowerCase("de");
    return bereiche
      .map((b) => ({ bereich: b, kategorien: b.kategorien.filter((k) => k.id !== undefined && !ohne.includes(k.id) && (!wort || `${k.name} ${b.name}`.toLocaleLowerCase("de").includes(wort))) }))
      .filter((g) => g.kategorien.length);
  });

  function abschicken(e: SubmitEvent) {
    e.preventDefault();
    const erste = gruppen[0];
    if (erste) onwahl(erste.kategorien[0], erste.bereich);
  }
</script>

<form class="feld" onsubmit={abschicken}><input class="eingabe" type="search" placeholder="Kategorie suchen" aria-label="Kategorie suchen" bind:value={suche} data-fokus /></form>
<div class="liste">
  {#each gruppen as g (g.bereich.schluessel)}
    <h2 class="gruppe">{g.bereich.name}</h2>
    {#each g.kategorien as k (k.id)}
      <button type="button" class="punkt" onclick={() => onwahl(k, g.bereich)}><Katalogzeichen name={k.zeichen} farbe={farbeVon(k, g.bereich)} groesse="klein" /><span class="name">{k.name}</span></button>
    {/each}
  {:else}<p class="leise">Keine Kategorie heißt so.</p>{/each}
</div>

<style>
  .liste {
    display: grid;
    max-height: 18rem;
    overflow: auto;
    margin-top: 0.5rem;
  }
  .gruppe {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--tinte-3);
    padding: 0.375rem 0.5rem 0.125rem;
    margin: 0;
  }
</style>
