<script lang="ts">
  // Regler mit feinen Stufen links und rechts, ganz rechts zurück auf die Vorgabe
  import { klemme, type Bereich } from "../../lib/leser/darstellung";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Regler from "../../lib/teile/Regler.svelte";
  let { name, wert, bereich, anzeige, sprung = bereich.schritt, onwahl }: { name: string; wert: number; bereich: Bereich; anzeige: string; sprung?: number; onwahl: (wert: number) => void } = $props();
</script>

<div class="stufen">
  <Knopf text="{name} kleiner" symbol="minus" nur klein gesperrt={wert <= bereich.min} onclick={() => onwahl(klemme(wert - sprung, bereich))} />
  <Regler {name} {wert} von={bereich.min} bis={bereich.max} schritt={bereich.schritt} {anzeige} onwahl={(w) => onwahl(klemme(w, bereich))} />
  <Knopf text="{name} größer" symbol="plus" nur klein gesperrt={wert >= bereich.max} onclick={() => onwahl(klemme(wert + sprung, bereich))} />
  <Knopf text="{name} zurücksetzen" symbol="rotate-left" nur klein frei gesperrt={wert === bereich.vorgabe} onclick={() => onwahl(bereich.vorgabe)} />
</div>

<style>
  .stufen {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto auto;
    align-items: end;
    gap: 0.375rem;
    width: 100%;
  }
  /* Der Name steht über der ganzen Reihe, der Regler mittig zwischen den Tasten */
  .stufen :global(.regler) {
    display: contents;
  }
  .stufen :global(.regler-kopf) {
    grid-column: 1 / -1;
    grid-row: 1;
  }
  .stufen :global(.regler input) {
    align-self: center;
  }
</style>
