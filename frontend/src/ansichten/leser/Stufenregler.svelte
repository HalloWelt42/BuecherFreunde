<script lang="ts">
  // Regler mit feinen Stufen links und rechts; der Wert in der Mitte setzt auf die Vorgabe zurück
  import { klemme, type Bereich } from "../../lib/leser/darstellung";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Regler from "../../lib/teile/Regler.svelte";
  let { name, wert, bereich, anzeige, sprung = bereich.schritt, onwahl }: { name: string; wert: number; bereich: Bereich; anzeige: string; sprung?: number; onwahl: (wert: number) => void } = $props();
</script>

<div class="stufen">
  <Regler {name} {wert} von={bereich.min} bis={bereich.max} schritt={bereich.schritt} {anzeige} onwahl={(w) => onwahl(klemme(w, bereich))} />
  <div class="reihe">
    <Knopf text="{name} kleiner" symbol="minus" nur klein gesperrt={wert <= bereich.min} onclick={() => onwahl(klemme(wert - sprung, bereich))} />
    <Knopf text="{name} größer" symbol="plus" nur klein gesperrt={wert >= bereich.max} onclick={() => onwahl(klemme(wert + sprung, bereich))} />
    <Knopf text="Vorgabe" symbol="rotate-left" klein frei gesperrt={wert === bereich.vorgabe} titel="{name} zurücksetzen" onclick={() => onwahl(bereich.vorgabe)} />
  </div>
</div>

<style>
  .stufen {
    display: grid;
    gap: 0.25rem;
    width: 100%;
  }
</style>
