<script lang="ts">
  // Der Schnellfilter einer Ansicht bei ihren übrigen Filtern; ein Druck nimmt ihn weg
  import { schnellfilter, type Filterziel } from "../stand/schnellfilter.svelte";
  import Chip from "../teile/Chip.svelte";
  import Symbol from "../teile/Symbol.svelte";

  let { ziel }: { ziel: Filterziel } = $props();
</script>

{#if ziel.wort}
  <Chip text={ziel.wort} symbol="filter" titel="Filter wegnehmen" onclick={() => schnellfilter.leere(ziel)}><Symbol name="xmark" /></Chip>
{/if}
