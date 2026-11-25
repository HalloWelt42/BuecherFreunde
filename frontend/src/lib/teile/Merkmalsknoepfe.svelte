<script lang="ts">
  import { merkmale } from "../stand/merkmale.svelte";
  import type { Buch } from "../typen";
  import Knopf from "./Knopf.svelte";
  let { buch, onneu = undefined }: { buch: Buch; onneu?: (neu: Partial<Buch>) => void } = $props();

  async function tun(was: "favorit" | "sofa" | "gelesen") {
    const neu = await merkmale[was](buch);
    onneu?.(neu);
  }
</script>

<Knopf text="Favorit" symbol="heart" nur gedrueckt={buch.is_favorite} onclick={() => void tun("favorit")} />
<Knopf text="Lesesofa" symbol="couch" nur gedrueckt={buch.is_to_read} onclick={() => void tun("sofa")} />
<Knopf text="Gelesen" symbol="circle-check" nur gedrueckt={!!buch.last_read_at} onclick={() => void tun("gelesen")} />
