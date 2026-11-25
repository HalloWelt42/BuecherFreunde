<script lang="ts">
  import { ladeVolltext } from "../../lib/api/metadata";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { NICHT_DA, schweige, sprich, vorlesen } from "../../lib/stand/vorlesen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  let { sitzung, onfertig = undefined }: { sitzung: Lesesitzung; onfertig?: () => void } = $props();

  let laedt = $state(false);
  let abschnitt = $derived(sitzung.griffe?.abschnittName ?? "");

  async function lies(was: string, hole: () => Promise<string>) {
    laedt = true;
    try {
      const text = await hole();
      if (!text.trim()) melde.info("Hier steht kein Text zum Vorlesen");
      else if (!(await sprich(text, was))) melde.warn(NICHT_DA);
      onfertig?.();
    } catch (e) {
      melde.schlecht(e, "Vorlesen");
    } finally {
      laedt = false;
    }
  }
</script>

<div class="reihe">
  {#if vorlesen.aktiv}
    <span class="marke-text info">Liest vor: {vorlesen.was}</span>
    <Knopf text="Anhalten" symbol="stop" klein onclick={() => schweige()} />
  {:else}
    {#if abschnitt}<Knopf text="{abschnitt} vorlesen" symbol="volume-low" klein gesperrt={laedt} onclick={() => void lies(abschnitt, async () => (await sitzung.griffe?.abschnitt()) ?? "")} />{/if}
    <Knopf text="Ganzes Buch vorlesen" symbol="book-open" klein laeuft={laedt} onclick={() => void lies("Ganzes Buch", async () => (await ladeVolltext(sitzung.buch.id, 1, 100000)).volltext ?? "")} />
  {/if}
</div>
