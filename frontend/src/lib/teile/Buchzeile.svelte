<script lang="ts">
  // Ein Buch als Zeile zum Anhaken (BF-67): Griff, Haken, Umschlag, Titel mit Autor, Band. Die ganze Zeile schaltet den
  // Haken; mit Griff lässt sie sich ziehen.
  import type { Buch } from "../typen";
  import Symbol from "./Symbol.svelte";
  import Umschlag from "./Umschlag.svelte";

  interface Eigenschaften {
    buch: Buch;
    an: boolean;
    onwahl: (an: boolean) => void;
    /** Was als Titel steht, etwa ohne Reihennamen; sonst der ganze */
    titel?: string;
    /** "Band 3" oder leer */
    band?: string;
    ziehbar?: boolean;
    gezogen?: boolean;
    /** Hier würde das Gezogene einsortiert */
    davor?: boolean;
    ondragstart?: (e: DragEvent) => void;
    ondragend?: (e: DragEvent) => void;
  }
  let { buch, an, onwahl, titel = undefined, band = "", ziehbar = false, gezogen = false, davor = false, ondragstart = undefined, ondragend = undefined }: Eigenschaften = $props();
</script>

<label class="zuordnungszeile" class:ohne-griff={!ziehbar} class:gewaehlt={an} class:gezogen class:davor data-buch={buch.id} draggable={ziehbar ? "true" : undefined} {ondragstart} {ondragend}>
  {#if ziehbar}<span class="griff"><Symbol name="grip-vertical" /></span>{/if}
  <input type="checkbox" checked={an} aria-label="{buch.title} auswählen" onchange={(e) => onwahl(e.currentTarget.checked)} />
  <span class="bild"><Umschlag {buch} /></span>
  <span class="titel">{titel ?? buch.title}<small>{buch.author}</small></span>
  <span class="bandnr">{band}</span>
</label>
