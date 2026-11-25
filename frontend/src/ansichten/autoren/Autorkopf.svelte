<script lang="ts">
  // Steckbrief: Foto, Name, Beschreibung, Daten und Verweise
  import type { Autoreneinzeln } from "../../lib/api/authors";
  import { zahl } from "../../lib/format";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Autorbild from "./Autorbild.svelte";
  import Konfidenz from "./Konfidenz.svelte";
  import { lebensdaten } from "./angaben";

  let { autor, onbild }: { autor: Autoreneinzeln; onbild: (bild: HTMLImageElement) => void } = $props();
  let daten = $derived(lebensdaten(autor));
</script>

<section class="buchkopf autorkopf platte">
  <div><Autorbild {autor} gross {onbild} /></div>
  <div class="rechts">
    <div><h1>{autor.name}</h1>{#if autor.beschreibung}<p>{autor.beschreibung}</p>{/if}</div>
    <dl class="angaben">
      {#if daten}<dt>Lebensdaten</dt><dd class="zahl">{daten}</dd>{/if}
      {#if autor.nationality}<dt>Land</dt><dd>{autor.nationality}</dd>{/if}
      <dt>Bücher</dt><dd class="zahl">{zahl(autor.books.length)}</dd>
      {#if autor.werke.length}<dt>Werke</dt><dd class="zahl">{zahl(autor.werke.length)}</dd>{/if}
    </dl>
    <div class="reihe">
      {#if autor.wikipedia_url}<Knopf text="Wikipedia" symbol="book-atlas" klein extern href={autor.wikipedia_url} />{/if}
      {#if autor.wikidata_id}<Knopf text={autor.wikidata_id} symbol="database" klein extern href="https://www.wikidata.org/wiki/{autor.wikidata_id}" titel="Eintrag bei Wikidata" />{/if}
      {#if autor.website}<Knopf text="Website" symbol="link" klein extern href={autor.website} />{/if}
      {#if autor.konfidenz}<Konfidenz stufe={autor.konfidenz} punkte={autor.score} />{/if}
    </div>
  </div>
</section>
