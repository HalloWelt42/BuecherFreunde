<script lang="ts">
  import { gleicheSchrift, SCHRIFTEN } from "../../lib/leser/darstellung";
  let { wert, mitBuch = false, onwahl }: { wert: string; mitBuch?: boolean; onwahl: (familie: string) => void } = $props();
</script>

<div class="tastenraster" style:--spalten="2" role="group" aria-label="Schrift">
  {#if mitBuch}<button type="button" class="chip" aria-pressed={!wert} onclick={() => onwahl("")}>Wie im Buch</button>{/if}
  {#each SCHRIFTEN as s (s.name)}
    <button type="button" class="chip" style:font-family={s.familie} aria-pressed={!!wert && gleicheSchrift(wert, s.familie)} onclick={() => onwahl(s.familie)}>{s.name}</button>
  {/each}
</div>
