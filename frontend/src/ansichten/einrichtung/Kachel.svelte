<script lang="ts">
  // Eine Kachel im Raster der Einrichtung: die ganze Kachel ist die Taste (Ausgangslagen, Katalog, Wege der Originale)
  import Katalogzeichen from "../../lib/teile/Katalogzeichen.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";

  interface Eigenschaften {
    symbol: string;
    farbe: string;
    titel: string;
    text: string;
    marke?: string;
    /** Ein Pfeil, wenn die Kachel weiterführt; ohne wählt sie (dann mit `gedrueckt`) */
    pfeil?: boolean;
    gedrueckt?: boolean;
    gesperrt?: boolean;
    onclick: () => void;
  }
  let { symbol, farbe, titel, text, marke = "", pfeil = true, gedrueckt = undefined, gesperrt = false, onclick }: Eigenschaften = $props();
</script>

<button type="button" class="katalogweg platte ew-kachel" aria-pressed={gedrueckt} disabled={gesperrt} {onclick}>
  <span class="wegkopf">
    <Katalogzeichen name={symbol} {farbe} groesse="gross" />
    <b>{titel}</b>
    {#if marke}<span class="katalogmarke">{marke}</span>{/if}
    {#if pfeil}<span class="ew-pfeil"><Symbol name="chevron-right" /></span>{/if}
  </span>
  <p>{text}</p>
</button>
