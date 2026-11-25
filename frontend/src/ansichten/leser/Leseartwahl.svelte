<script lang="ts">
  import type { Leseart } from "../../lib/leser/fluss/fluss";
  import { LESEARTEN } from "../../lib/leser/leseart.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  let { art, onart }: { art: Leseart; onart: (art: Leseart) => void } = $props();
</script>

<Segment name="Blättern oder Scrollen" werte={LESEARTEN} wert={art} onwahl={onart} />
