<script lang="ts">
  // Eine große Sammlung als ein Band im Regal (BF-66). Sie ist kein Buch: nicht anhakbar, ohne Vorschau, Tippen öffnet ihr Regal.
  import Symbol from "../../lib/teile/Symbol.svelte";
  import type { Sammlungseintrag } from "../../lib/typen";
  import { baende, sammlungshinweis, sammlungsweg } from "./sammlungseintrag";
  import Stapel from "./Stapel.svelte";

  let { sammlung }: { sammlung: Sammlungseintrag } = $props();
</script>

<div class="band sammlungsband" data-sammlung={sammlung.id}>
  <a class="flaeche" href={sammlungsweg(sammlung.id)} aria-label="Sammlung {sammlung.name}, {baende(sammlung.anzahl)}" title={sammlungshinweis(sammlung)} draggable="false">
    <span class="stand"><Stapel {sammlung} /></span>
    <span class="boden"></span>
    <span class="schild">
      <span class="sammlungszeile"><Symbol name="layer-group" />Sammlung</span>
      <b>{sammlung.name}</b>
      <span class="wer"><span>{sammlung.autor}</span><span>{baende(sammlung.anzahl)}</span></span>
    </span>
  </a>
</div>
