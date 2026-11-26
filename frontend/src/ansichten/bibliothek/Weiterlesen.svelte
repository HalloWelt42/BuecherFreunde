<script lang="ts">
  import { zuletztGelesen } from "../../lib/api/user-data";
  import { leseAdresse, lesestand, standText } from "../../lib/lesestand";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import Balken from "../../lib/teile/Balken.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import { kontext } from "../../lib/stand/kontextmenue.svelte";
  import { buchmenue } from "./buchmenue";
  import type { Buch } from "../../lib/typen";

  let { hoechstens = 3 }: { hoechstens?: number } = $props();
  let liste = $state<Buch[]>([]);

  async function hole() {
    try {
      const alle = await zuletztGelesen(12);
      liste = alle.filter((b) => lesestand(b).angefangen && lesestand(b).anteil < 1).slice(0, hoechstens);
    } catch {
      liste = [];
    }
  }

  $effect(() => {
    void hole();
    return bestand.beiAenderung(() => void hole());
  });
</script>

{#if liste.length}
  <section class="block">
    <div class="titelzeile"><h2>Weiterlesen</h2></div>
    <div class="weiter">
      {#each liste as buch (buch.id)}
        <a class="platte" href={leseAdresse(buch.id)} use:kontext={buchmenue(buch)}>
          <Umschlag {buch} />
          <span class="text"><b>{buch.title}</b><span class="leise">{buch.author}</span><Balken anteil={lesestand(buch).anteil} name="Lesestand" /><span class="leise zahl">{standText(buch)}</span></span>
        </a>
      {/each}
    </div>
  </section>
{/if}

<style>
  .text {
    min-width: 0;
  }
</style>
