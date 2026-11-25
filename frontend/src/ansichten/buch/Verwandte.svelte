<script lang="ts">
  import Karte from "../../lib/teile/Karte.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import type { Buch } from "../../lib/typen";

  let { verwandt }: { verwandt: { vom_autor: Buch[]; in_kategorie: Buch[] } } = $props();
  let gruppen = $derived(([["Vom selben Autor", verwandt.vom_autor], ["Im selben Regal", verwandt.in_kategorie]] as [string, Buch[]][]).filter(([, b]) => b.length));
</script>

{#if gruppen.length}
  <Karte titel="Verwandte Bücher" symbol="shapes" breit>
    {#each gruppen as [name, liste] (name)}
      <div>
        <p class="leise">{name}</p>
        <div class="regal nur">
          {#each liste as b (b.id)}
            <div class="band"><a class="flaeche" href="/book/{b.id}" title="{b.title}, {b.author}" aria-label={b.title}><span class="stand"><Umschlag buch={b} /></span><span class="boden"></span></a></div>
          {/each}
        </div>
      </div>
    {/each}
  </Karte>
{/if}
