<script lang="ts">
  import { verbindungen } from "../stand/verbindungen.svelte";
  import Lampe from "../teile/Lampe.svelte";
</script>

<span class="lampen">
  {#each verbindungen.liste as v (v.kennung)}<Lampe stand={v.stand} text={v.name} titel={v.text} />{/each}
  {#if verbindungen.app.stand === "schlecht" || !verbindungen.liste.length}<Lampe stand={verbindungen.app.stand} text="App" titel={verbindungen.app.text} />{/if}
  <Lampe stand={verbindungen.ki.stand} text="KI" titel={verbindungen.ki.text} />
</span>
<span class="lampen leise">
  {#if verbindungen.fassung}<span>Fassung {verbindungen.fassung}</span>{/if}
  {#if verbindungen.neueFassung}<span class="marke-text info" title="Neue Fassung veröffentlicht">neu: {verbindungen.neueFassung}</span>{/if}
</span>

<style>
  .leise {
    font-size: 0.8125rem;
  }
</style>
