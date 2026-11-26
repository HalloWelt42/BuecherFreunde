<script lang="ts">
  // Drei Zahlen nebeneinander, je mit Lampe: erreichbar, wiedergefunden, fehlt (oder übernommen, ohne Auszug, Fehler)
  import { zahl } from "../../lib/format";
  import type { Guete } from "../../lib/typen";

  let { werte }: { werte: [Guete | "aus", number, string][] } = $props();
</script>

<div class="ew-zaehler">
  {#each werte as [stand, n, text] (text)}
    <div class="platte ew-zaehl">
      <span class="lampe"><span class="led {stand}"></span><b class="zahl">{zahl(n)}</b></span>
      <span class="leise">{text}</span>
    </div>
  {/each}
</div>
