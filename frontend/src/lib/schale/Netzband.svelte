<script lang="ts">
  // Der Server antwortet nicht: sagen statt leerer Seite
  import { bestand } from "../stand/bestand.svelte";
  import { netz } from "../stand/netz.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Symbol from "../teile/Symbol.svelte";

  let prueft = $state(false);
  $effect(() => netz.beiWiederDa(() => bestand.geaendert()));

  async function nochmal() {
    prueft = true;
    await netz.pruefe();
    prueft = false;
  }
</script>

{#if netz.weg}
  <div class="band-netz glas dicht" role="status">
    <span class="marke-text warn"><Symbol name="plug-circle-xmark" />Keine Verbindung zur Bibliothek</span>
    <Knopf text="Erneut" symbol="rotate-right" klein laeuft={prueft} onclick={() => void nochmal()} />
  </div>
{/if}

<style>
  .band-netz {
    position: absolute;
    z-index: 66;
    left: 50%;
    top: calc(0.75rem + env(safe-area-inset-top, 0px));
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 0.75rem;
    width: max-content;
    max-width: calc(100% - 2rem);
    padding: 0.5rem 0.5rem 0.5rem 0.875rem;
  }
</style>
