<script lang="ts">
  import { STIFTFARBEN } from "../../lib/leser/farben";
  let { wert, name, onwahl }: { wert: string; name: string; onwahl: (farbe: string) => void } = $props();
</script>

<div class="farbreihe" role="group" aria-label={name}>
  {#each STIFTFARBEN as f (f.farbe)}
    <button type="button" style:background={f.farbe} aria-label={f.name} title={f.name} aria-pressed={f.farbe.toLowerCase() === wert?.toLowerCase()} onclick={() => onwahl(f.farbe)}></button>
  {/each}
</div>
