<script lang="ts">
  // Alles, was gerade läuft: Aufnahmen, Einlesen von Ordnern, Ergänzen, Aufträge der Ansichten
  import { annahme } from "../stand/annahme.svelte";
  import { auftraege } from "../stand/auftraege.svelte";
  import { melde } from "../stand/meldungen.svelte";
  import { schale } from "../stand/schale.svelte";
  import Balken from "../teile/Balken.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Stationen from "../teile/Stationen.svelte";
  import Symbol from "../teile/Symbol.svelte";
  import Einleseauftrag from "./Einleseauftrag.svelte";
  import Ergaenzungsauftrag from "./Ergaenzungsauftrag.svelte";

  let leer = $derived(!annahme.laufend.length && !auftraege.laufend && !auftraege.aufgaben.length && !auftraege.ergaenzungFertig && !auftraege.eigene.length);
  let ruhig = $derived(!auftraege.einlesenLaeuft && !auftraege.ergaenzung.laeuft && (auftraege.aufgaben.length > 0 || auftraege.ergaenzungFertig));

  async function bereinigen() {
    try {
      await auftraege.bereinigen();
    } catch (e) {
      melde.schlecht(e);
    }
  }
</script>

{#each annahme.laufend as z (z.schluessel)}
  <div class="auftrag"><b>{z.name}</b><Stationen stationen={z.stationen} prozent={z.prozent} /><span class="marke-text {z.ton}"><Symbol name={z.symbol} />{z.text}</span></div>
{/each}
{#if auftraege.ergaenzung.laeuft || auftraege.ergaenzungFertig}<Ergaenzungsauftrag />{/if}
{#each auftraege.eigene as a (a.id)}
  <div class="auftrag">
    <div class="reihe"><b>{a.titel}</b>{#if a.abbrechen && a.laeuft}<span class="schiebt"><Knopf text="Anhalten" symbol="stop" klein frei onclick={a.abbrechen} /></span>{:else if !a.laeuft}<span class="schiebt"><Knopf text="Ausblenden" symbol="xmark" nur klein frei onclick={() => auftraege.entferne(a.id)} /></span>{/if}</div>
    {#if a.anteil !== null}<Balken anteil={a.anteil} name={a.titel} />{/if}
    <span class="leise zahl">{a.text}</span>
    {#if a.weg}<div><Knopf text="Anzeigen" symbol="arrow-right" klein frei href={a.weg} onclick={() => schale.schliesseAlles()} /></div>{/if}
  </div>
{/each}
{#if auftraege.aufgaben.length}<Einleseauftrag />{/if}
{#if leer}<p class="leise">Gerade läuft nichts.</p>{/if}

<div class="reihe fuss">
  <Knopf text="Alle Aufnahmen" symbol="list-check" href="/import" onclick={() => schale.schliesseAlles()} />
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
</style>
