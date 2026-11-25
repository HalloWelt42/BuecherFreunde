<script lang="ts">
  import { auswahl } from "../../lib/stand/auswahl.svelte";
  import type { Buch } from "../../lib/typen";
  import Band from "./Band.svelte";
  import Grossbild from "./Grossbild.svelte";
  import type { Regalart } from "./ansicht.svelte";
  import { ziehauswahl } from "./ziehauswahl";

  let { liste, art }: { liste: Buch[]; art: Regalart } = $props();
  let gross = $state<{ buch: Buch; an: HTMLElement } | null>(null);
  const zeige = (buch: Buch | null, an?: HTMLElement) => (gross = buch && an ? { buch, an } : null);
</script>

<div class="regal" class:gross={art === "grid-large"} class:nur={art === "covers"} use:ziehauswahl={{ an: auswahl.bearbeiten, art: "rechteck" }}>
  {#each liste as buch (buch.id)}
    <Band {buch} gross={art === "grid-large"} ongross={art === "covers" ? zeige : undefined} />
  {/each}
</div>
{#if gross}<Grossbild buch={gross.buch} an={gross.an} />{/if}
