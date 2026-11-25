<script lang="ts">
  import { zahl } from "../../lib/format";
  import Knopf from "../../lib/teile/Knopf.svelte";
  let { wort, nr, gesamt, onspringe, onschliessen }: { wort: string; nr: number; gesamt: number; onspringe: (nr: number) => void; onschliessen: () => void } = $props();
</script>

<Knopf text="Voriger Treffer" symbol="chevron-up" nur frei klein onclick={() => onspringe(nr - 1)} />
<Knopf text="Nächster Treffer" symbol="chevron-down" nur frei klein onclick={() => onspringe(nr + 1)} />
<span class="klein zahl wort">{zahl(nr + 1)} von {zahl(gesamt)} für "{wort}"</span>
<span class="schiebt"><Knopf text="Treffer ausblenden" symbol="xmark" nur frei klein onclick={onschliessen} /></span>

<style>
  .wort {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
