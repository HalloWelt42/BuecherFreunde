<!-- Ein Buch im Kinderregal: großer Umschlag, darunter der Titel und auf Wunsch eine leise Zeile (etwa wann es gelesen wurde) -->
<script lang="ts">
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import type { Buch } from "../../lib/typen";

  let { buch, unter = "", onwahl }: { buch: Buch; unter?: string; onwahl: (buch: Buch) => void } = $props();
</script>

<button class="k-buch" type="button" onclick={() => onwahl(buch)}>
  <span class="k-umschlag"><Umschlag {buch} /></span>
  <span>{buch.title}{#if unter}<small>{unter}</small>{/if}</span>
</button>
