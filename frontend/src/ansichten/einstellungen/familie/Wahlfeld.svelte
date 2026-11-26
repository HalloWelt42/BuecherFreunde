<script lang="ts" generics="W extends string">
  // Eine Wahl aus wenigen im Elternbereich (BF-88, Entwurf kinder-7 Abschnitt 5): das Segment der App in gleich breiten Feldern,
  // schmal neben ihrer Zeile oder über die ganze Breite des Felds
  import Segment from "../../../lib/teile/Segment.svelte";

  let { name, werte, wert, breit = false, gesperrt = false, onwahl }: { name: string; werte: [W, string][]; wert: W; breit?: boolean; gesperrt?: boolean; onwahl: (w: W) => void } = $props();
</script>

<span class="wahlfeld" class:breit style:--n={werte.length}><Segment {name} {werte} {wert} {gesperrt} {onwahl} /></span>

<style>
  .wahlfeld {
    display: inline-grid;
    justify-self: end;
    width: calc(var(--n) * 5rem);
    max-width: 100%;
  }
  .wahlfeld.breit {
    display: grid;
    width: 100%;
  }
  .wahlfeld :global(.segment) {
    display: grid;
    grid-template-columns: repeat(var(--n), minmax(0, 1fr));
  }
  .wahlfeld :global(.segment button) {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    text-align: center;
  }
</style>
