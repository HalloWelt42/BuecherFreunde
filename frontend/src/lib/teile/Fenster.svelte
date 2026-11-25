<script lang="ts">
  // Fenster über allem: hält den Fokus, Esc und ein Klick daneben schließen
  import type { Snippet } from "svelte";
  import { beiEsc } from "../flucht";
  import Knopf from "./Knopf.svelte";

  let { titel, breite = "34rem", onschliessen, children, fuss = undefined }: { titel: string; breite?: string; onschliessen: () => void; children: Snippet; fuss?: Snippet } = $props();
  let fenster: HTMLDialogElement | undefined = $state();

  $effect(() => {
    const f = fenster;
    f?.showModal?.();
    // Nicht das Schließen-Zeichen: ein markiertes Feld oder das Fenster selbst bekommt den Fokus
    (f?.querySelector<HTMLElement>("[data-fokus]") ?? f)?.focus();
    const ab = beiEsc(() => onschliessen());
    return () => {
      ab();
      f?.close?.();
    };
  });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions, a11y_autofocus -->
<dialog tabindex="-1" class="fenster glas dicht" style:--fenster={breite} bind:this={fenster} aria-label={titel} oncancel={(e) => (e.preventDefault(), onschliessen())} onclick={(e) => e.target === fenster && onschliessen()}>
  <div class="fenster-innen">
    <header class="reihe"><h2>{titel}</h2><span class="schiebt"><Knopf text="Schließen" symbol="xmark" nur klein frei onclick={onschliessen} /></span></header>
    <div class="fenster-mitte rollen">{@render children()}</div>
    {#if fuss}<footer class="reihe">{@render fuss()}</footer>{/if}
  </div>
</dialog>
