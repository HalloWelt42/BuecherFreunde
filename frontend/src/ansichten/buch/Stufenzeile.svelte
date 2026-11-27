<script lang="ts">
  // Die Stufe einer ISBN gegen Titel und Autor des Buchs (BF-111): Marke, worauf sie beruht, was dort steht (Abweichendes markiert),
  // warum, und Prüfen, solange keine Quelle gefragt ist
  import type { Einstufung } from "../../lib/api/books";
  import Auszug from "../../lib/teile/Auszug.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { STUFEN } from "./isbn";

  interface Eigenschaften {
    einstufung: Einstufung;
    /** offen: Knopf Prüfen; erneut: eine Quelle ruhte; fertig: ohne Knopf */
    stand?: "offen" | "erneut" | "fertig";
    prueft?: boolean;
    /** eine Quelle ruht, in Klartext mit der Folge */
    warnung?: string;
    onpruefe?: () => void;
  }
  let { einstufung: e, stand = "fertig", prueft = false, warnung = "", onpruefe = undefined }: Eigenschaften = $props();
  let marke = $derived(STUFEN[e.stufe]);
</script>

<div class="stufe">
  <span class="marke-text {marke.klasse}"><Symbol name={marke.symbol} />{marke.wort}</span>
  <span class="grund">
    <span class="basis">{e.basis}:</span>
    <Auszug text={e.was} />
    {#if e.warum}<span class="warum">{e.warum}</span>{/if}
    {#if warnung}<span class="warum marke-text warn"><Symbol name="triangle-exclamation" />{warnung}</span>{/if}
  </span>
  {#if onpruefe && stand === "offen"}<Knopf text="Prüfen" symbol="magnifying-glass" klein titel="Die Quellen zu dieser ISBN fragen" laeuft={prueft} onclick={onpruefe} />
  {:else if onpruefe && stand === "erneut"}<Knopf text="Erneut prüfen" symbol="rotate-right" klein titel="Die Quellen noch einmal fragen" laeuft={prueft} onclick={onpruefe} />{/if}
</div>
