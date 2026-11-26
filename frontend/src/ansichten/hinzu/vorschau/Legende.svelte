<script lang="ts">
  // Was die Zeichen der Herkunft heißen
  import { HERKUNFT, LEGENDE } from "../../../lib/annahme/vorschau";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  let { lage }: { lage: "oben" | "unten" } = $props();
</script>

<div class="hklegende {lage}">{#each LEGENDE as h (h)}<span><Symbol name={HERKUNFT[h].symbol} />{HERKUNFT[h].name}</span>{/each}</div>
