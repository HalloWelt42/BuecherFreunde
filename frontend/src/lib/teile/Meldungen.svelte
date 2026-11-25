<script lang="ts">
  import { melde } from "../stand/meldungen.svelte";
  import Symbol from "./Symbol.svelte";
  const zeichen = { gut: "circle-check", schlecht: "circle-xmark", info: "circle-info", warn: "triangle-exclamation" };
</script>

<div class="meldungen" aria-live="polite">
  {#each melde.liste as m (m.id)}
    <button type="button" class="meldung glas dicht" title="Schließen" onclick={() => melde.schliesse(m.id)}><span class="marke-text {m.art}"><Symbol name={zeichen[m.art]} /></span><span>{m.text}</span></button>
  {/each}
</div>
