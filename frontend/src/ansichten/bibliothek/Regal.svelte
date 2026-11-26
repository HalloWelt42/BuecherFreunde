<script lang="ts">
  import { auswahl } from "../../lib/stand/auswahl.svelte";
  import { eintragsschluessel } from "../../lib/stand/eintraege";
  import type { Buch, Eintrag } from "../../lib/typen";
  import Band from "./Band.svelte";
  import Grossbild from "./Grossbild.svelte";
  import Sammlungsband from "./Sammlungsband.svelte";
  import type { Regalart } from "./ansicht.svelte";
  import { ziehauswahl } from "./ziehauswahl";

  /** reihe: im eigenen Regal einer Sammlung Name und Kopf der Reihe (Band und Kurztitel auf dem Schild) */
  let { eintraege, art, reihe = undefined }: { eintraege: Eintrag[]; art: Regalart; reihe?: string[] } = $props();
  let gross = $state<{ buch: Buch; an: HTMLElement } | null>(null);
  const zeige = (buch: Buch | null, an?: HTMLElement) => (gross = buch && an ? { buch, an } : null);
</script>

<div class="regal" class:gross={art === "grid-large"} class:nur={art === "covers"} use:ziehauswahl={{ an: auswahl.bearbeiten, art: "rechteck" }}>
  {#each eintraege as eintrag (eintragsschluessel(eintrag))}
    {#if eintrag.art === "sammlung"}<Sammlungsband sammlung={eintrag.sammlung} />
    {:else}<Band buch={eintrag.buch} gross={art === "grid-large"} ongross={art === "covers" ? zeige : undefined} {reihe} />{/if}
  {/each}
</div>
{#if gross}<Grossbild buch={gross.buch} an={gross.an} />{/if}
