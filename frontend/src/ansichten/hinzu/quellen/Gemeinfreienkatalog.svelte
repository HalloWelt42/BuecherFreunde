<script lang="ts">
  // Der eigene Katalog in der Karte der gemeinfreien Bücher (BF-98): solange er geholt wird, als Vorgang mit Balken; sonst eine
  // Zeile mit Anzahl, Stand und wie oft er erneuert wird, dazu "Jetzt erneuern"
  import { erneuernText, gutenberg as g, katalogauftrag, katalogzeile } from "../../../lib/stand/gutenberg.svelte";
  import Balken from "../../../lib/teile/Balken.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  let k = $derived(g.katalog);
  let auftrag = $derived(k?.laeuft ? katalogauftrag(k) : null);
</script>

{#if k && auftrag}
  <section class="mulde auftrag" aria-live="polite">
    <div class="reihe"><b>{auftrag.titel}</b><span class="leise zahl">{auftrag.text}</span></div>
    <Balken anteil={auftrag.anteil ?? 0} unbestimmt={auftrag.anteil === null} name={auftrag.titel} />
    <span class="leise">{k.da ? "Bis der neue fertig ist, gilt der bisherige." : `Einmal, danach ${erneuernText(k.erneuern_tage)}, vom Spiegel des Project Gutenberg. Bis er da ist, sucht "Bei Gutendex suchen" wie bisher.`}</span>
  </section>
{:else if k}
  <div class="katalogzeile"><Symbol name="book-bookmark" /><span>{katalogzeile(k)}</span><Knopf text={k.da ? "Jetzt erneuern" : "Jetzt holen"} symbol="rotate" klein frei onclick={() => void g.holeKatalog()} /></div>
{/if}
