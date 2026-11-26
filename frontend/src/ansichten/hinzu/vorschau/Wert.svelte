<script lang="ts">
  // Ein Wert der Vorschau mit Zeichen davor, Zusatz darunter und seiner Herkunft dahinter
  import type { Snippet } from "svelte";
  import type { Herkunft as Herkunftsart } from "../../../lib/annahme/vorschautypen";
  import Herkunft from "./Herkunft.svelte";

  let { text, klein = "", herkunft = null, titel = undefined, zu = false, vorn = undefined, unter = undefined }: { text: string; klein?: string; herkunft?: Herkunftsart | null; titel?: string; zu?: boolean; vorn?: Snippet; unter?: Snippet } = $props();
</script>

<span class="vwert" class:zu title={titel}>
  {@render vorn?.()}
  <span class="text"><span>{text}</span>{#if klein || unter} <small>{klein}{@render unter?.()}</small>{/if}</span>
  <Herkunft {herkunft} />
</span>
