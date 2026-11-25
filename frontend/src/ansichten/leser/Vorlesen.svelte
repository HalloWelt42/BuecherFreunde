<script lang="ts">
  // Vorlesen: was gelesen wird und mit welcher Stimme
  import { ladeVolltext } from "../../lib/api/metadata";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import Auswahl from "../../lib/teile/Auswahl.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  let { sitzung, onfertig = undefined }: { sitzung: Lesesitzung; onfertig?: () => void } = $props();

  let laedt = $state(false);
  let abschnitt = $derived(sitzung.griffe?.abschnittName ?? "");

  $effect(() => vorlesen.pruefe());

  async function lies(was: string, hole: () => Promise<string>) {
    vorlesen.entsperre();
    laedt = true;
    try {
      const text = await hole();
      if (!text.trim()) melde.info("Hier steht kein Text zum Vorlesen");
      else {
        vorlesen.lies(text, was);
        onfertig?.();
      }
    } catch (e) {
      melde.schlecht(e, "Vorlesen");
    } finally {
      laedt = false;
    }
  }
</script>

<div class="vorlesen">
  {#if vorlesen.aktiv}
    <div class="reihe">
      <span class="marke-text info"><Symbol name={vorlesen.wartet ? "circle-notch" : "volume-high"} dreht={vorlesen.wartet} />{vorlesen.wartet ? "Ton wird geholt" : `Liest vor: ${vorlesen.was}`}</span>
      <span class="schiebt"><Knopf text="Anhalten" symbol="stop" klein onclick={() => vorlesen.halt()} /></span>
    </div>
  {:else}
    <div class="reihe">
      {#if abschnitt}<Knopf text="{abschnitt} vorlesen" symbol="volume-low" klein gesperrt={laedt} onclick={() => void lies(abschnitt, async () => (await sitzung.griffe?.abschnitt()) ?? "")} />{/if}
      <Knopf text="Ganzes Buch vorlesen" symbol="book-open" klein laeuft={laedt} onclick={() => void lies("Ganzes Buch", async () => (await ladeVolltext(sitzung.buch.id, 1, 100000)).volltext ?? "")} />
    </div>
  {/if}
  {#if vorlesen.stimmen.length}
    <div class="stimme">
      <span class="klein">Stimme</span>
      <Auswahl name="Stimme" gruppen={vorlesen.gruppen} wert={vorlesen.stimme} onwahl={(id) => vorlesen.waehle(id)} />
      <Knopf text="Probe hören" symbol="play" nur klein gesperrt={vorlesen.aktiv} onclick={() => vorlesen.probe()} />
    </div>
  {/if}
  {#if vorlesen.hinweis}<p class="klein leise">{vorlesen.hinweis}</p>{/if}
</div>

<style>
  .vorlesen {
    display: grid;
    gap: 0.5rem;
    min-width: 0;
  }
  .stimme {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 0.5rem;
    align-items: center;
  }
</style>
