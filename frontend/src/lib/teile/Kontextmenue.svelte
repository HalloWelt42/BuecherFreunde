<script lang="ts">
  // Das eigene Kontextmenü (BF-42): die Einträge des Bausteins unter der Maus, am Punkt des Klicks; ein Eintrag kann einen
  // zweiten Schritt im selben Menü zeigen (etwa die Regale). Inhalt und Lage kommen aus lib/stand/kontextmenue.svelte.ts.
  import { kontextmenue, type Eintrag } from "../stand/kontextmenue.svelte";
  import Knopf from "./Knopf.svelte";
  import Menue from "./Menue.svelte";
  import Symbol from "./Symbol.svelte";

  let offen = $derived(kontextmenue.offen!);
  let schritt = $state<Eintrag | null>(null);

  async function waehle(e: Eintrag) {
    if (e.weiter) return void (schritt = e);
    kontextmenue.schliesse();
    await e.tun?.();
  }
</script>

<Menue anker={null} punkt={offen} name="Kontextmenü" breite={schritt ? "18rem" : "15rem"} onschliessen={() => kontextmenue.schliesse()}>
  {#if schritt?.weiter}
    {@const W = schritt.weiter.komponente}
    <div class="reihe kopf"><Knopf text="Zurück" symbol="arrow-left" nur klein frei onclick={() => (schritt = null)} /><b>{schritt.text}</b></div>
    <W {...schritt.weiter.eigenschaften} />
  {:else}
    <div class="liste" role="menu">
      {#each offen.eintraege as e (e.text)}
        <button type="button" class="punkt" role="menuitem" disabled={e.gesperrt} data-fokus={e === offen.eintraege[0] ? "" : undefined} onclick={() => void waehle(e)}>
          <Symbol name={e.symbol} /><span class="name">{e.text}</span>{#if e.weiter}<Symbol name="chevron-right" klasse="schiebt" />{/if}
        </button>
      {/each}
    </div>
  {/if}
</Menue>

<style>
  .liste {
    display: grid;
    gap: 2px;
  }
  .kopf {
    gap: 0.25rem;
    margin-bottom: 0.375rem;
  }
  .punkt:disabled {
    opacity: 0.45;
    cursor: default;
  }
</style>
