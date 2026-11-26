<script lang="ts">
  import { verbindungen } from "../stand/verbindungen.svelte";
  import Lampe from "../teile/Lampe.svelte";
</script>

<!-- Zwei feste Spalten (BF-64): Punkte und Namen stehen untereinander, ein zu langer Name wird gekürzt und steht im Hinweis -->
<span class="lampen raster">
  {#each verbindungen.liste as v (v.kennung)}<Lampe stand={v.stand} text={v.name} titel="{v.name}: {v.text}" />{/each}
  {#if verbindungen.app.stand === "schlecht" || !verbindungen.liste.length}<Lampe stand={verbindungen.app.stand} text="App" titel={verbindungen.app.text} />{/if}
</span>
<span class="lampen leise">
  {#if verbindungen.fassung}<span>Version {verbindungen.fassung}</span>{/if}
  {#if verbindungen.neueFassung}<span class="marke-text info" title="Neue Version veröffentlicht">neu: {verbindungen.neueFassung}</span>{/if}
</span>

<style>
  .leise {
    font-size: 0.8125rem;
  }
</style>
