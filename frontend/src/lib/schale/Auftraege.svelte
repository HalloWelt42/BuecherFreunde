<script lang="ts">
  // Alles, was gerade läuft: Aufnahmen, Einlesen von Ordnern, Ergänzen, Aufträge der Ansichten; ganz oben, was vor dem Regal
  // auf die Bestätigung wartet (BF-80), auch über Tage
  import { vorschauzeile } from "../annahme/zeilen";
  import { annahme } from "../stand/annahme.svelte";
  import { auftraege } from "../stand/auftraege.svelte";
  import { ich } from "../stand/ich.svelte";
  import { melde } from "../stand/meldungen.svelte";
  import { schale } from "../stand/schale.svelte";
  import Balken from "../teile/Balken.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Stationen from "../teile/Stationen.svelte";
  import Symbol from "../teile/Symbol.svelte";
  import Einleseauftrag from "./Einleseauftrag.svelte";
  import Ergaenzungsauftrag from "./Ergaenzungsauftrag.svelte";

  let leer = $derived(!annahme.vorschauen.length && !annahme.laufend.length && !auftraege.laufend && !annahme.einlesen.gesamt && !auftraege.ergaenzungFertig && !auftraege.alleEigenen.length);
  let ruhig = $derived(!auftraege.einlesenLaeuft && !auftraege.ergaenzung.laeuft && (annahme.einlesen.gesamt > 0 || auftraege.ergaenzungFertig));

  async function bereinigen() {
    try {
      await auftraege.bereinigen();
    } catch (e) {
      melde.schlecht(e);
    }
  }
</script>

{#if annahme.vorschauen.length}
  <div class="gruppe">
    <div class="gruppenkopf"><Symbol name="list-check" />Zum Bestätigen <span class="leise zahl">{annahme.vorschauen.length}</span></div>
    {#each annahme.vorschauen as v (v.id)}
      <div class="auftrag">
        <div class="reihe"><b>{v.name}</b><span class="schiebt"><Knopf text="Ansehen" symbol="eye" klein frei href="/import/vorschau/{v.id}" onclick={() => schale.schliesseAlles()} /></span></div>
        <span class="leise zahl">{vorschauzeile(v).text}</span>
      </div>
    {/each}
  </div>
{/if}
{#each annahme.laufend as z (z.schluessel)}
  <div class="auftrag"><b>{z.name}</b><Stationen stationen={z.stationen} prozent={z.prozent} /><span class="marke-text {z.ton}"><Symbol name={z.symbol} />{z.text}</span></div>
{/each}
{#if auftraege.ergaenzung.laeuft || auftraege.ergaenzungFertig}<Ergaenzungsauftrag />{/if}
{#each auftraege.alleEigenen as a (a.id)}
  <div class="auftrag">
    <div class="reihe"><b>{a.titel}</b>{#if a.pause && a.laeuft}<span class="schiebt"><Knopf text="Pause" symbol="pause" klein frei onclick={a.pause} /></span>{:else if a.fortsetzen && a.pausiert}<span class="schiebt"><Knopf text="Fortsetzen" symbol="play" klein frei onclick={a.fortsetzen} /></span>{:else if a.abbrechen && a.laeuft}<span class="schiebt"><Knopf text="Anhalten" symbol="stop" klein frei onclick={a.abbrechen} /></span>{:else if !a.laeuft}<span class="schiebt"><Knopf text="Ausblenden" symbol="xmark" nur klein frei onclick={() => auftraege.entferne(a.id)} /></span>{/if}</div>
    {#if a.anteil !== null}<Balken anteil={a.anteil} name={a.titel} />{/if}
    <span class="leise zahl">{a.text}</span>
    {#if a.weg}<div><Knopf text="Anzeigen" symbol="arrow-right" klein frei href={a.weg} onclick={() => schale.schliesseAlles()} /></div>{/if}
  </div>
{/each}
{#if annahme.einlesen.gesamt}<Einleseauftrag />{/if}
{#if leer}<p class="leise">Gerade läuft nichts.</p>{/if}

<div class="reihe fuss">
  {#if ich.darf("hinzufuegen")}<Knopf text="Alle Aufnahmen" symbol="list-check" href="/import" onclick={() => schale.schliesseAlles()} />{/if}
  {#if ruhig}<Knopf text="Fertige ausblenden" symbol="broom" frei onclick={bereinigen} />{/if}
</div>

<style>
  .auftrag {
    display: grid;
    gap: 0.375rem;
    padding: 0.5rem 0;
    border-top: 1px solid var(--linie);
    overflow-wrap: anywhere;
  }
  .fuss {
    padding-top: 0.5rem;
  }
  .gruppenkopf {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--tinte-2);
    padding: 0.25rem 0;
  }
  .gruppenkopf > :global(i) {
    color: var(--messing);
  }
</style>
