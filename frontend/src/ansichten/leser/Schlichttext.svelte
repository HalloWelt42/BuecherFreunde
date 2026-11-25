<script lang="ts">
  // Reiner Text in Blöcken statt in einem einzigen riesigen Stück: der Umbruch großer Bücher bleibt so flott
  import { inBloecke } from "../../lib/leser/text/bloecke";
  let { text, onsteht }: { text: string; onsteht: () => void } = $props();
  let bloecke = $derived(inBloecke(text));

  function gesetzt(_knoten: HTMLElement) {
    onsteht();
  }
</script>

{#each bloecke as block, n (n)}<div class="schlichttext">{block}</div>{/each}
<span hidden use:gesetzt></span>
