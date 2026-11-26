<script lang="ts">
  // Ein Wert als Chip (BF-78, Entwurf Elternbereich): zeigt, was gilt; ein Tipp öffnet darunter, womit er sich ändert
  import type { Snippet } from "svelte";
  import Chip from "../../../lib/teile/Chip.svelte";
  import Menue from "../../../lib/teile/Menue.svelte";

  let { text, name, symbol = "", gesperrt = false, breite = "17rem", children }: { text: string; name: string; symbol?: string; gesperrt?: boolean; breite?: string; children: Snippet<[() => void]> } = $props();
  let offen = $state(false);
  let anker = $state<HTMLElement | null>(null);
  const zu = () => (offen = false);
</script>

<span class="wertchip" bind:this={anker}><Chip {text} {symbol} titel={name} gedrueckt={offen} {gesperrt} onclick={() => (offen = !offen)} /></span>
{#if offen}
  <Menue {anker} {name} {breite} onschliessen={zu}><div class="wertfeld">{@render children(zu)}</div></Menue>
{/if}

<style>
  .wertchip {
    display: inline-flex;
    justify-self: end;
    max-width: 100%;
  }
  .wertfeld {
    display: grid;
    gap: 0.625rem;
    grid-template-columns: minmax(0, 1fr);
  }
  /* Eine Wahl darin nimmt die ganze Breite, in gleich breiten Feldern */
  .wertfeld :global(.segment) {
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(0, 1fr);
  }
</style>
